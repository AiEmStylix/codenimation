from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from typing import Any

KNOWN_MANIM_MOBJECTS = {
    "Circle",
    "Square",
    "Rectangle",
    "RoundedRectangle",
    "SurroundingRectangle",
    "SurroundingCircle",
    "Dot",
    "Line",
    "Arrow",
    "MathTex",
    "Tex",
    "Text",
    "TextBox",
    "DecimalNumber",
    "Integer",
    "NumberLine",
    "Axes",
    "VGroup",
    "HGroup",
    "Group",
    "Brace",
    "BraceLabel",
    "Polygon",
    "Ellipse",
    "AnnularSector",
    "Arrow",
    "Square",
    "Circle",
}

KNOWN_MANIM_ANIMATIONS = {
    "Create",
    "Write",
    "FadeIn",
    "FadeOut",
    "Transform",
    "ReplacementTransform",
    "Indicate",
    "GrowFromCenter",
    "ShowCreation",
    "Uncreate",
    "AnimationGroup",
    "LaggedStart",
    "FadeInFrom",
    "FadeOutTo",
    "Animate",
}

VIETNAMESE_UNICODE_PATTERN = re.compile(r"[ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯàáâãèéêìíòóôõùúăđĩũơưẠ-ỹ]")
MATH_TEXT_PATTERN = re.compile(r"MathTex\(r?([\"'])(.*?)\1\)")
IMPORT_REPLACEMENTS = {
    "SurroundingRect": "SurroundingRectangle",
    "TextMobject": "Text",
    "TexMobject": "Tex",
    "OldTex": "Tex",
}


@dataclass
class ReviewIssue:
    error_code: str
    category: str
    severity: str
    message: str
    location: dict[str, Any]
    cause: str
    fix_strategy: str
    original: str
    fixed: str | None
    regenerate_scene: bool
    auto_fixable: bool
    start_index: int | None = None
    end_index: int | None = None
    replacement: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("start_index", None)
        data.pop("end_index", None)
        data.pop("replacement", None)
        return data


def _get_source_lines(source: str) -> list[str]:
    return source.splitlines(keepends=True)


def _linecol_to_index(source: str, lineno: int, col_offset: int) -> int:
    lines = _get_source_lines(source)
    if lineno <= 0 or lineno > len(lines):
        return len(source)
    return sum(len(line) for line in lines[: lineno - 1]) + col_offset


def _extract_source_segment(source: str, node: ast.AST) -> str:
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        return ""
    start = _linecol_to_index(source, node.lineno, node.col_offset)
    end = _linecol_to_index(source, node.end_lineno, node.end_col_offset)
    return source[start:end]


def _replace_range(source: str, start: int, end: int, replacement: str) -> str:
    return source[:start] + replacement + source[end:]


def _get_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _get_name(node.func)
    return ""


def _is_self_play(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Attribute):
        if call.func.attr == "play":
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "self":
                return True
    return False


def _is_animation_call(node: ast.Call) -> bool:
    name = _get_name(node.func)
    return name in KNOWN_MANIM_ANIMATIONS


def _is_mobject_constructor(node: ast.Call) -> bool:
    name = _get_name(node.func)
    return name in KNOWN_MANIM_MOBJECTS and name not in KNOWN_MANIM_ANIMATIONS


def _build_issue(
    error_code: str,
    category: str,
    severity: str,
    message: str,
    file: str,
    node: ast.AST,
    cause: str,
    fix_strategy: str,
    original: str,
    fixed: str | None,
    regenerate_scene: bool,
    auto_fixable: bool,
    replacement: str | None = None,
) -> ReviewIssue:
    line = getattr(node, "lineno", 0)
    column = getattr(node, "col_offset", 0)
    start = _linecol_to_index(original_source_cache["source"], line, column) if original_source_cache.get("source") else None
    end = None
    if hasattr(node, "end_lineno") and hasattr(node, "end_col_offset") and original_source_cache.get("source"):
        end = _linecol_to_index(original_source_cache["source"], node.end_lineno, node.end_col_offset)
    location = {"file": file, "line": line, "column": column}
    return ReviewIssue(
        error_code=error_code,
        category=category,
        severity=severity,
        message=message,
        location=location,
        cause=cause,
        fix_strategy=fix_strategy,
        original=original,
        fixed=fixed,
        regenerate_scene=regenerate_scene,
        auto_fixable=auto_fixable,
        start_index=start,
        end_index=end,
        replacement=replacement,
    )


def _extract_issues_from_play(call: ast.Call, source: str, filename: str) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if not _is_self_play(call):
        return issues

    for arg in call.args:
        if isinstance(arg, ast.Call) and _is_mobject_constructor(arg):
            original = _extract_source_segment(source, call)
            fixed_arg = "Create(" + _extract_source_segment(source, arg) + ")"
            fixed = original.replace(_extract_source_segment(source, arg), fixed_arg, 1)
            issues.append(_build_issue(
                error_code="MAN-001",
                category="Manim API",
                severity="ERROR",
                message="Mobject được truyền trực tiếp vào self.play().",
                file=filename,
                node=call,
                cause="self.play() chỉ nhận Animation hoặc phương thức animate(), không nhận Mobject trực tiếp.",
                fix_strategy="WRAP_WITH_CREATE",
                original=original,
                fixed=fixed,
                regenerate_scene=False,
                auto_fixable=True,
                replacement=fixed,
            ))
        elif isinstance(arg, (ast.Name, ast.Attribute)):
            original = _extract_source_segment(source, call)
            arg_text = _extract_source_segment(source, arg)
            if arg_text.strip():
                fixed_arg = f"Write({arg_text})"
                fixed = original.replace(arg_text, fixed_arg, 1)
                issues.append(_build_issue(
                    error_code="MAN-001",
                    category="Manim API",
                    severity="ERROR",
                    message="Mobject hoặc Text được truyền trực tiếp vào self.play().",
                    file=filename,
                    node=call,
                    cause="self.play() cần một animation, không được truyền biến Mobject trực tiếp.",
                    fix_strategy="WRAP_WITH_WRITE",
                    original=original,
                    fixed=fixed,
                    regenerate_scene=False,
                    auto_fixable=True,
                    replacement=fixed,
                ))
    return issues


def _find_import_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "manim":
            for alias in node.names:
                if alias.name in IMPORT_REPLACEMENTS:
                    original = _extract_source_segment(source, node)
                    corrected_name = IMPORT_REPLACEMENTS[alias.name]
                    fixed = original.replace(alias.name, corrected_name)
                    issues.append(_build_issue(
                        error_code="IMP-006",
                        category="Import",
                        severity="ERROR",
                        message=f"Import Manim sai tên: {alias.name}.",
                        file=filename,
                        node=node,
                        cause=f"{alias.name} không phải API hợp lệ của ManimCE.",
                        fix_strategy="REPLACE_API",
                        original=original,
                        fixed=fixed,
                        regenerate_scene=False,
                        auto_fixable=True,
                        replacement=fixed,
                    ))
    return issues


def _find_mathtx_issues(source: str, filename: str) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for match in MATH_TEXT_PATTERN.finditer(source):
        content = match.group(2)
        if VIETNAMESE_UNICODE_PATTERN.search(content):
            original = match.group(0)
            issues.append(ReviewIssue(
                error_code="LATEX-005",
                category="LaTeX",
                severity="WARNING",
                message="MathTex chứa Unicode tiếng Việt hoặc văn bản không phù hợp.",
                location={"file": filename, "line": source[: match.start()].count("\n") + 1, "column": match.start() - source.rfind("\n", 0, match.start()) - 1},
                cause="MathTex chỉ nên chứa công thức toán thuần túy, không chứa tiếng Việt trực tiếp.",
                fix_strategy="FIX_LATEX_ESCAPE",
                original=original,
                fixed=None,
                regenerate_scene=False,
                auto_fixable=False,
            ))
    return issues


DARK_COLOR_PATTERN = re.compile(r"(?P<name>\b[A-Za-z_][A-Za-z_0-9]*)\s*=\s*(?P<value>[A-Za-z0-9_#.\"']+)", re.IGNORECASE)
DARK_COLORS = {
    "black", "#000000", "#000", "#0a0a0a", "#0a0a0a", "#111111", "#111",
    "#1a1a1a", "#222222", "#222", "#1e3d36", "darkgreen", "darkblue",
    "darkred", "darkgrey", "darkgray", "#333333", "#2b2b2b",
}


def _find_dark_color_issues(source: str, filename: str) -> list[ReviewIssue]:
    """Cảnh báo màu tối gán cho nội dung (chữ/hình) — mất hút trên nền tối #1E3D36."""
    issues: list[ReviewIssue] = []
    for match in DARK_COLOR_PATTERN.finditer(source):
        name = match.group("name").lower()
        if name in {"background_color", "self.camera.background_color"}:
            continue
        value = match.group("value").strip().strip("'\"").lower()
        value_display = match.group("value").strip()
        if value in DARK_COLORS:
            issues.append(ReviewIssue(
                error_code="EMPH-004",
                category="Emphasis",
                severity="WARNING",
                message=f"Gán màu tối {value_display} cho nội dung — sẽ mất hút trên nền #1E3D36.",
                location={"file": filename, "line": source[: match.start()].count("\n") + 1, "column": match.start() - source.rfind("\n", 0, match.start()) - 1},
                cause="Video dùng nền tối, màu tối sẽ làm chữ/hình không đọc được.",
                fix_strategy="Thay bằng màu sáng trong bảng màu ngữ nghĩa (trắng, #7FD8E8, #FFD166, #5CE1A0, #FF6B6B).",
                original=match.group(0),
                fixed=None,
                regenerate_scene=False,
                auto_fixable=False,
            ))
    return issues


def _has_index_slice(node: ast.AST) -> bool:
    """Kiểm tra xem một AST node có chứa thao tác cắt index kiểu obj[0][-5:] hay không."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Slice):
            return True
    return False


def _find_outermost_slice_subscript(node: ast.AST) -> ast.Subscript | None:
    """Tìm Subscript ngoài cùng (đầu tiên theo DFS) có slice là Slice, ví dụ n_set[0][-5:]."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Subscript) and isinstance(current.slice, ast.Slice):
            return current
        for child in reversed(list(ast.iter_child_nodes(current))):
            stack.append(child)
    return None


def _find_emphasis_slice_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Cảnh báo khi highlight bằng cách cắt index của MathTex (n_set[0][-5:]) — dễ nhấn nhầm đối tượng."""
    issues: list[ReviewIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_self_play(node):
            for arg in node.args:
                if not _has_index_slice(arg):
                    continue
                target = _find_outermost_slice_subscript(arg)
                if target is None:
                    continue
                original = _extract_source_segment(source, target)
                if not original.strip():
                    continue
                base = _extract_source_segment(source, target.value)
                start = _linecol_to_index(source, target.lineno, target.col_offset)
                end = _linecol_to_index(source, target.end_lineno, target.end_col_offset)
                inside_animation = isinstance(arg, ast.Call)
                issues.append(ReviewIssue(
                    error_code="EMPH-003",
                    category="Emphasis",
                    severity="ERROR" if inside_animation else "WARNING",
                    message="Nhấn mạnh bằng cách cắt index của MathTex (vd n_set[0][-5:]) — dễ highlight nhầm đối tượng.",
                    location={"file": filename, "line": target.lineno, "column": target.col_offset},
                    cause="Index slicing trên Mobject không ổn định giữa các bản Manim và khó khớp với đối tượng cần nhấn.",
                    fix_strategy="Tách MathTex/Text riêng cho ký hiệu cần highlight rồi ghép VGroup; nếu tạm thời thì highlight cả đối tượng gốc.",
                    original=original,
                    fixed=base if inside_animation else None,
                    regenerate_scene=False,
                    auto_fixable=inside_animation,
                    replacement=base if inside_animation else None,
                    start_index=start if inside_animation else None,
                    end_index=end if inside_animation else None,
                ))
    return issues


def _collect_review_issues(code_text: str, filename: str = "math_scene.py") -> list[ReviewIssue]:
    global original_source_cache
    original_source_cache = {"source": code_text}
    try:
        tree = ast.parse(code_text)
    except SyntaxError as exc:
        location = {"file": filename, "line": exc.lineno or 0, "column": exc.offset or 0}
        original_line = ""
        if exc.lineno and 1 <= exc.lineno <= len(code_text.splitlines()):
            original_line = code_text.splitlines()[exc.lineno - 1]
        return [ReviewIssue(
            error_code="PY-001" if not isinstance(exc, IndentationError) else "PY-002",
            category="Python",
            severity="CRITICAL",
            message=str(exc).replace("\n", " "),
            location=location,
            cause="Lỗi cú pháp Python trong mã nguồn.",
            fix_strategy="FIX_SYNTAX",
            original=original_line,
            fixed=None,
            regenerate_scene=False,
            auto_fixable=False,
        )]

    issues: list[ReviewIssue] = []
    issues.extend(_find_import_issues(tree, code_text, filename))
    issues.extend(_find_mathtx_issues(code_text, filename))
    issues.extend(_find_emphasis_slice_issues(tree, code_text, filename))
    issues.extend(_find_dark_color_issues(code_text, filename))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_self_play(node):
            issues.extend(_extract_issues_from_play(node, code_text, filename))

    return issues


def _apply_fixes(code_text: str, issues: list[ReviewIssue]) -> tuple[str, list[ReviewIssue]]:
    fixable = [issue for issue in issues if issue.auto_fixable and issue.replacement and issue.start_index is not None and issue.end_index is not None]
    if not fixable:
        return code_text, []

    fixable_sorted = sorted(fixable, key=lambda issue: issue.start_index or 0, reverse=True)
    new_code = code_text
    fixed_issues: list[ReviewIssue] = []
    for issue in fixable_sorted:
        if issue.start_index is None or issue.end_index is None or issue.replacement is None:
            continue
        new_code = _replace_range(new_code, issue.start_index, issue.end_index, issue.replacement)
        fixed_issue = ReviewIssue(**{**asdict(issue), "fixed": issue.replacement})
        fixed_issues.append(fixed_issue)

    return new_code, fixed_issues


def run_review_cycle(code_text: str, filename: str = "math_scene.py", max_iterations: int = 3) -> dict[str, Any]:
    review_code = code_text
    history: list[dict[str, Any]] = []
    for iteration in range(1, max_iterations + 1):
        issues = _collect_review_issues(review_code, filename)
        issues_data = [issue.to_dict() for issue in issues]
        has_fixable = any(issue.auto_fixable for issue in issues)
        history.append({"iteration": iteration, "issues": issues_data})

        if not has_fixable:
            return {
                "status": "complete",
                "fixed_code": review_code,
                "issues": issues_data,
                "iterations": iteration,
                "auto_fixed": iteration > 1,
                "history": history,
            }

        review_code, fixed_issues = _apply_fixes(review_code, issues)
        if not fixed_issues:
            return {
                "status": "complete",
                "fixed_code": review_code,
                "issues": issues_data,
                "iterations": iteration,
                "auto_fixed": False,
                "history": history,
            }

    final_issues = _collect_review_issues(review_code, filename)
    return {
        "status": "complete",
        "fixed_code": review_code,
        "issues": [issue.to_dict() for issue in final_issues],
        "iterations": max_iterations,
        "auto_fixed": True,
        "history": history,
    }


def analyze_code(code_text: str, filename: str = "math_scene.py") -> dict[str, Any]:
    issues = _collect_review_issues(code_text, filename)
    return {
        "issues": [issue.to_dict() for issue in issues],
        "issue_count": len(issues),
    }
