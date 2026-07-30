import ast
import re
from typing import Optional
from .prompt_loader import load_prompt_from_file


def _contains_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _split_tex_and_text_segments(tex_string: str):
    pattern = re.compile(r"(\\text\{[^}]*\})")
    parts = pattern.split(tex_string)
    result = []
    for part in parts:
        if not part:
            continue
        if part.startswith(r"\text{") and part.endswith("}"):
            result.append(("text", part[6:-1]))
        else:
            result.append(("math", part))
    return result


def _sanitize_mathtex_call(source: str, node: ast.Call) -> Optional[str]:
    if not isinstance(node.func, ast.Name) or node.func.id != "MathTex":
        return None

    math_kwargs = []
    for kw in node.keywords:
        kw_src = ast.get_source_segment(source, kw)
        if kw_src:
            math_kwargs.append(kw_src)
    kwargs_code = ", ".join(math_kwargs)

    elements = []
    has_vietnamese_text = False

    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            segments = _split_tex_and_text_segments(arg.value)
            for seg_type, seg_value in segments:
                if seg_type == "text":
                    if _contains_non_ascii(seg_value):
                        has_vietnamese_text = True
                        elements.append(f'Text({repr(seg_value)}, font="Noto Sans")')
                    else:
                        elements.append(
                            f'MathTex({repr(seg_value)}{", " + kwargs_code if kwargs_code else ""})'
                        )
                else:
                    if seg_value.strip() == "":
                        continue
                    elements.append(
                        f'MathTex({repr(seg_value)}{", " + kwargs_code if kwargs_code else ""})'
                    )
        else:
            arg_src = ast.get_source_segment(source, arg)
            if arg_src is not None:
                elements.append(arg_src)

    if not has_vietnamese_text:
        return None

    if not elements:
        return None

    if len(elements) == 1:
        return elements[0]

    return "VGroup(" + ", ".join(elements) + ").arrange(RIGHT, buff=0.15)"


def sanitize_manim_code(raw_code: str) -> str:
    try:
        tree = ast.parse(raw_code)
    except SyntaxError:
        return raw_code

    replacements = []

    class SanitizeVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            replacement = _sanitize_mathtex_call(raw_code, node)
            if replacement:
                replacements.append(
                    (
                        node.lineno - 1,
                        node.col_offset,
                        node.end_lineno - 1,
                        node.end_col_offset,
                        replacement,
                    )
                )
            self.generic_visit(node)

    SanitizeVisitor().visit(tree)

    if not replacements:
        return raw_code

    lines = raw_code.splitlines(keepends=True)
    line_offsets = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    sanitized = raw_code
    for start_line, start_col, end_line, end_col, replacement in sorted(
        replacements,
        key=lambda item: (item[0], item[1]),
        reverse=True,
    ):
        start_idx = line_offsets[start_line] + start_col
        end_idx = line_offsets[end_line] + end_col
        sanitized = sanitized[:start_idx] + replacement + sanitized[end_idx:]

    return sanitized


def generate_manim_code(script: str, client) -> str:
    system_instruction = load_prompt_from_file("CODE_GENERATOR.md")

    response = client.chat.completions.create(
        model="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": (
                    f"Viết code Manim cho kịch bản sau:\n{script}\n"
                    "- Chỉ dùng MathTex cho các công thức toán học. "
                    "Nếu có chữ tiếng Việt, hãy dùng Text(font='Noto Sans') riêng biệt. "
                    r"Không để chữ tiếng Việt trong MathTex hoặc trong \text{...}."
                )
            }
        ],
        temperature=0.2,
    )

    raw_code = response.choices[0].message.content

    # Xử lý an toàn: Xóa các thẻ markdown
    raw_code = re.sub(r"^```python\s*", "", raw_code, flags=re.MULTILINE)
    raw_code = re.sub(r"^```\s*", "", raw_code, flags=re.MULTILINE)
    raw_code = re.sub(r"\s*```$", "", raw_code, flags=re.MULTILINE)

    raw_code = sanitize_manim_code(raw_code)

    return raw_code
