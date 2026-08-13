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

ALLOWED_IMPORTS = {"manim", "typing", "__future__"}

FOREIGN_IMPORT_HINTS = {
    "numpy": "thay bằng DecimalNumber/NumberLine hoặc tính trực tiếp trong scene",
    "math": "tính trực tiếp trong scene, Manim đã có sẵn các hàm số học cơ bản",
    "random": "không dùng dữ liệu ngẫu nhiên, dựng nội dung tĩnh theo storyboard",
    "PIL": "dựng hình hoàn toàn bằng Mobject của Manim",
    "Image": "dựng hình hoàn toàn bằng Mobject của Manim",
    "sympy": "tính toán thủ công bằng Python thuần trong scene",
    "os": "không thao tác hệ thống trong Scene",
    "sys": "không thao tác hệ thống trong Scene",
    "pathlib": "không đọc/ghi file trong Scene",
    "subprocess": "cấm chạy lệnh ngoài trong Scene",
    "requests": "cấm gọi network trong Scene",
    "json": "không cần đọc/gửi JSON trong Scene",
    "cv2": "xử lý hình bằng Mobject của Manim, không dùng OpenCV",
    "matplotlib": "vẽ bằng Mobject của Manim, không dùng matplotlib",
    "pandas": "không dùng pandas trong Scene",
    "datetime": "không cần thời gian hệ thống trong Scene",
}

LEGACY_API_REPLACEMENTS = dict(IMPORT_REPLACEMENTS)


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


def _line_end_index(source: str, lineno: int) -> int:
    """Index cuối của nội dung dòng `lineno` (bỏ ký tự xuống dòng)."""
    lines = _get_source_lines(source)
    if lineno <= 0 or lineno > len(lines):
        return len(source)
    return sum(len(line) for line in lines[: lineno - 1]) + len(lines[lineno - 1].rstrip("\r\n"))


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


def _find_foreign_import_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Phát hiện import ngoài ManimCE (numpy, PIL, random, os, ...).

    Scene Manim chỉ nên import `manim` (+ `typing`/`__future__`). Import ngoài
    thường là dấu hiệu LLM sinh code không thuộc Manim → render fail. Auto-fix
    bằng cách xoá dòng import; nếu code còn dùng biến từ module đó, vòng repair
    render sẽ xử lý tiếp.
    """
    issues: list[ReviewIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in ALLOWED_IMPORTS:
                continue
            module_top = (node.module or "").split(".")[0]
        elif isinstance(node, ast.Import):
            tops = {alias.name.split(".")[0] for alias in node.names}
            if tops and tops <= ALLOWED_IMPORTS:
                continue
            module_top = next(iter(tops - ALLOWED_IMPORTS)) if tops - ALLOWED_IMPORTS else ""
        else:
            continue

        original = _extract_source_segment(source, node)
        if not original.strip():
            continue

        hint = FOREIGN_IMPORT_HINTS.get(module_top, "chỉ được import ManimCE")
        start = _linecol_to_index(source, node.lineno, 0)
        end = _line_end_index(source, node.end_lineno)
        issues.append(ReviewIssue(
            error_code="IMP-007",
            category="Import",
            severity="ERROR",
            message=f"Import ngoài ManimCE: {original.strip()}",
            location={"file": filename, "line": node.lineno, "column": 0},
            cause=(
                "Scene Manim chỉ được import 'manim'. Import ngoài ManimCE sẽ gây "
                f"lỗi render. Gợi ý: {hint}."
            ),
            fix_strategy="REMOVE_FOREIGN_IMPORT",
            original=original,
            fixed="",
            regenerate_scene=False,
            auto_fixable=True,
            start_index=start,
            end_index=end,
            replacement="\n",
        ))
    return issues


def _find_legacy_api_usage_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Thay tên API Manim cũ/hợp lệ bằng API ManimCE chuẩn (vd TextMobject -> Text)."""
    issues: list[ReviewIssue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name):
            continue
        corrected = LEGACY_API_REPLACEMENTS.get(node.id)
        if not corrected or node.id == corrected:
            continue
        original = _extract_source_segment(source, node)
        if not original.strip():
            continue
        start = _linecol_to_index(source, node.lineno, node.col_offset)
        end = _linecol_to_index(source, node.end_lineno, node.end_col_offset)
        issues.append(ReviewIssue(
            error_code="IMP-008",
            category="Import",
            severity="ERROR",
            message=f"API Manim cũ: {node.id} -> {corrected}.",
            location={"file": filename, "line": node.lineno, "column": node.col_offset},
            cause=f"{node.id} không phải API hợp lệ của ManimCE; dùng {corrected}.",
            fix_strategy="REPLACE_API",
            original=original,
            fixed=corrected,
            regenerate_scene=False,
            auto_fixable=True,
            start_index=start,
            end_index=end,
            replacement=corrected,
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
                severity="ERROR",
                message="MathTex chứa Unicode tiếng Việt hoặc văn bản không phù hợp — sẽ render vỡ dấu khiến học sinh khó đọc.",
                location={"file": filename, "line": source[: match.start()].count("\n") + 1, "column": match.start() - source.rfind("\n", 0, match.start()) - 1},
                cause="MathTex chỉ nên chứa công thức toán thuần túy; chữ tiếng Việt (kể cả \\text{...}) phải tách ra ngoài.",
                fix_strategy="Tách văn bản tiếng Việt ra khỏi MathTex, dùng Text('...', font='Arial') riêng rồi ghép VGroup; MathTex(r'...') chỉ giữ công thức LaTeX.",
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
    """Kiểm tra xem một AST node có chứa thao tác index chained/cắt slice hay không.

    Bắt 2 dạng highlight không đáng tin trên Mobject:
    - Slice: obj[0][-5:], obj[:2], ...
    - Chained integer index: obj[0][2] (chỉ mục bên trong lại là một Subscript khác).
    """
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Subscript):
            continue
        if isinstance(sub.slice, ast.Slice):
            return True
        if isinstance(sub.value, ast.Subscript):
            return True
    return False


def _find_outermost_slice_subscript(node: ast.AST) -> ast.Subscript | None:
    """Tìm Subscript ngoài cùng (đầu tiên theo DFS) có slice là Slice hoặc value là Subscript.

    Vd n_set[0][-5:] (Slice) hoặc n_set[0][2] (chained integer index).
    """
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Subscript):
            if isinstance(current.slice, ast.Slice) or isinstance(current.value, ast.Subscript):
                return current
        for child in reversed(list(ast.iter_child_nodes(current))):
            stack.append(child)
    return None


def _find_emphasis_slice_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Cảnh báo khi highlight bằng cách cắt index của MathTex (n_set[0][-5:], n_set[0][2]) — dễ nhấn nhầm đối tượng."""
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
                    message="Nhấn mạnh bằng cách cắt index của MathTex (vd n_set[0][2] hoặc n_set[0][-5:]) — dễ highlight nhầm đối tượng.",
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


def _get_numeric_value(node: ast.AST) -> float | None:
    """Lấy giá trị số từ AST node (Constant hoặc UnaryOp âm)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _get_numeric_value(node.operand)
        return -inner if inner is not None else None
    return None


MAX_SINGLE_WAIT_SECONDS = 2.0
MAX_SINGLE_RUN_TIME_SECONDS = 2.0


def _find_pacing_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Bắt nhịp độ gây 'video đứng hình': self.wait() quá dài hoặc run_time quá lớn.

    Đây là lớp kiểm tra quyết định (deterministic) bù cho các quy tắc chỉ nằm
    trong prompt LLM (CODE_GENERATOR.md) mà model hay bỏ qua. Lỗi không auto-fix
    vì giải pháp đúng là THÊM nội dung diễn giải + hiệu ứng, không hạ con số xuống.
    """
    issues: list[ReviewIssue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            continue
        func_attr = node.func.attr

        if func_attr == "wait":
            value: float | None = None
            if node.args:
                value = _get_numeric_value(node.args[0])
            elif node.keywords:
                for kw in node.keywords:
                    if kw.arg in ("duration", None):
                        value = _get_numeric_value(kw.value)
                        if value is not None:
                            break
            if value is not None and value > MAX_SINGLE_WAIT_SECONDS:
                original = _extract_source_segment(source, node)
                issues.append(_build_issue(
                    error_code="PACE-001",
                    category="Pacing",
                    severity="ERROR",
                    message=(
                        f"self.wait({value:g}) quá dài (tối đa {MAX_SINGLE_WAIT_SECONDS:g}s) — "
                        "video đứng hình khiến học sinh mất tập trung."
                    ),
                    file=filename,
                    node=node,
                    cause="Chờ tĩnh dài không có nội dung/hoạt động trên màn hình.",
                    fix_strategy=(
                        "Thay self.wait() dài bằng nội dung diễn giải (giải thích 'vì sao', liên hệ bài trước) "
                        "cùng hiệu ứng animation (Transform/TransformMatchingTex, Indicate...) để lấp thời gian; "
                        "mỗi self.wait() ≤ 2.0s."
                    ),
                    original=original,
                    fixed=None,
                    regenerate_scene=False,
                    auto_fixable=False,
                ))

        if func_attr == "play":
            run_time: float | None = None
            for kw in node.keywords:
                if kw.arg == "run_time":
                    run_time = _get_numeric_value(kw.value)
                    break
            if run_time is not None and run_time > MAX_SINGLE_RUN_TIME_SECONDS:
                original = _extract_source_segment(source, node)
                issues.append(_build_issue(
                    error_code="PACE-002",
                    category="Pacing",
                    severity="ERROR",
                    message=(
                        f"run_time={run_time:g} quá lớn (tối đa {MAX_SINGLE_RUN_TIME_SECONDS:g}s) — "
                        "hiệu ứng kéo dài khiến video ì ạch."
                    ),
                    file=filename,
                    node=node,
                    cause="Một animation đơn lẻ chạy quá lâu.",
                    fix_strategy="Chia hiệu ứng thành nhiều self.play() ngắn (0.5–1.0s) hoặc dùng LaggedStart.",
                    original=original,
                    fixed=None,
                    regenerate_scene=False,
                    auto_fixable=False,
                ))
    return issues


_INTRO_ANIMATIONS = {"Write", "FadeIn", "Create", "GrowFromCenter", "DrawBorderThenFill"}
_FADEOUT_ANIMATIONS = {"FadeOut", "Uncreate", "FadeOutTo"}
_GROUP_CONSTRUCTORS = {"VGroup", "Group", "HGroup"}
# Các Mobject "bám theo" đối tượng khác (tự đặt vị trí quanh mục tiêu) — không thể gây chồng lấn trung tâm.
_ATTACHED_MOBJECTS = {
    "SurroundingRectangle", "SurroundingCircle", "Brace", "BraceLabel",
    "Line", "Arrow", "DoubleArrow",
}
_POSITION_METHODS = {
    "arrange", "next_to", "to_edge", "to_corner", "move_to", "shift", "align_to",
    "scale", "scale_to_fit_width", "scale_to_fit_height",
    "stretch_to_fit_width", "stretch_to_fit_height", "surround", "shift_onto_screen",
}
_SCENE_MARKER_RE = re.compile(r"#\s*\[SCENE\s*\d+\]", re.IGNORECASE)


def _find_construct_method(tree: ast.Module) -> ast.FunctionDef | None:
    """Tìm phương thức construct() đầu tiên trong mọi class của file."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef) and stmt.name == "construct":
                    return stmt
    return None


def _find_layout_issues(tree: ast.Module, source: str, filename: str) -> list[ReviewIssue]:
    """Bắt bố cục bị đè lên nhau (lỗi phổ biến nhất khiến video rối).

    - LAY-002: scene hiện nội dung mới nhưng scene TRƯỚC có nội dung mà không bao giờ
      FadeOut → chữ/cảnh cũ vẫn nằm trên màn hình, nội dung mới đè lên.
    - LAY-001: trong cùng một scene, >= 2 nội dung được giới thiệu riêng lẻ mà không
      được định vị (.arrange/.next_to/.move_to/...) và không nằm trong nhóm đã sắp xếp
      → các object xếp chồng tại tâm màn hình.
    """
    issues: list[ReviewIssue] = []
    construct = _find_construct_method(tree)
    if construct is None:
        return issues

    marker_lines: list[int] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _SCENE_MARKER_RE.search(line):
            marker_lines.append(lineno)

    def scene_index(lineno: int) -> int:
        idx = 0
        for mline in marker_lines:
            if mline <= lineno:
                idx += 1
            else:
                break
        return idx  # 0 = preamble (khung bảng, icon giáo viên, tiêu đề cố định)

    scenes: dict[int, dict[str, Any]] = {}
    for stmt in construct.body:
        lineno = getattr(stmt, "lineno", 0)
        si = scene_index(lineno)
        sc = scenes.setdefault(
            si,
            {"introduced": set(), "positioned": set(), "grouped": set(), "attached": set(),
             "had_fadeout": False, "line": lineno},
        )

        # (1) Gán biến: ánh xạ ĐÚNG tên biến được định vị / nằm trong nhóm / bám theo.
        if isinstance(stmt, ast.Assign):
            target_names = {_get_name(t) for t in stmt.targets if _get_name(t)}
            value = stmt.value
            if isinstance(value, ast.Call) and _get_name(value.func) in _ATTACHED_MOBJECTS:
                sc["attached"].update(target_names)
            for sub in ast.walk(value):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func
                if isinstance(fn, ast.Attribute) and fn.attr in _POSITION_METHODS:
                    sc["positioned"].update(target_names)
                if _get_name(fn) in _GROUP_CONSTRUCTORS:
                    for arg in sub.args:
                        member = _get_name(arg)
                        if member:
                            sc["grouped"].add(member)

        # (2) Lệnh gọi đứng riêng: scene_content.arrange(...) trên dòng riêng.
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Attribute) and fn.attr in _POSITION_METHODS:
                target = _get_name(fn.value)
                if target:
                    sc["positioned"].add(target)

        # (3) Lệnh self.play(): ghi nhận nội dung được giới thiệu và FadeOut.
        for sub in ast.walk(stmt):
            if not isinstance(sub, ast.Call) or not _is_self_play(sub):
                continue
            for arg in sub.args:
                if not isinstance(arg, ast.Call):
                    continue
                an = _get_name(arg.func)
                if an in _INTRO_ANIMATIONS:
                    inner = _get_name(arg.args[0]) if arg.args else None
                    if inner:
                        sc["introduced"].add(inner)
                elif an in _FADEOUT_ANIMATIONS:
                    sc["had_fadeout"] = True
            if not sc["had_fadeout"]:
                for inner in ast.walk(sub):
                    if (
                        isinstance(inner, ast.Call)
                        and _get_name(inner.func) in _FADEOUT_ANIMATIONS
                    ):
                        sc["had_fadeout"] = True

    for si, sc in sorted(scenes.items()):
        if si == 0 or not sc["introduced"]:
            continue
        prev = scenes.get(si - 1)
        if prev is not None and prev["introduced"] and not prev["had_fadeout"]:
            issues.append(ReviewIssue(
                error_code="LAY-002",
                category="Layout",
                severity="ERROR",
                message=(
                    "Scene trước có nội dung nhưng không FadeOut trước khi scene này hiện "
                    "nội dung mới — chữ/cảnh cũ bị đè lên nội dung mới."
                ),
                location={"file": filename, "line": sc["line"], "column": 0},
                cause="Nội dung scene cũ chưa được ẩn (thiếu FadeOut/Uncreate) trước khi dựng scene mới.",
                fix_strategy=(
                    "Cuối MỖI scene phải self.play(FadeOut(scene_content)) để ẩn nội dung cũ; "
                    "chỉ giữ tiêu đề/khung/icon. Đầu scene mới kiểm tra màn hình đã sạch trước khi Write/FadeIn."
                ),
                original="",
                fixed=None,
                regenerate_scene=False,
                auto_fixable=False,
            ))

        unplaced = [
            name for name in sc["introduced"]
            if name not in sc["positioned"]
            and name not in sc["grouped"]
            and name not in sc["attached"]
        ]
        if len(unplaced) >= 2:
            issues.append(ReviewIssue(
                error_code="LAY-001",
                category="Layout",
                severity="ERROR",
                message=(
                    "Có " + ", ".join(sorted(unplaced)) + " được hiện riêng lẻ nhưng không được "
                    "sắp xếp (arrange/next_to) — các nội dung này sẽ xếp chồng lên nhau tại giữa màn hình."
                ),
                location={"file": filename, "line": sc["line"], "column": 0},
                cause="Nhiều Mobject được Write/FadeIn/Create riêng rẽ mà không qua VGroup().arrange() hoặc .next_to().",
                fix_strategy=(
                    "Gom các nội dung vào một scene_content = VGroup(...).arrange(DOWN/UP/RIGHT/LEFT, buff=0.25~0.4) "
                    "rồi viết cả nhóm bằng một self.play(); hoặc dùng .next_to() có buff rõ ràng cho từng đối tượng."
                ),
                original="",
                fixed=None,
                regenerate_scene=False,
                auto_fixable=False,
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
    issues.extend(_find_foreign_import_issues(tree, code_text, filename))
    issues.extend(_find_import_issues(tree, code_text, filename))
    issues.extend(_find_legacy_api_usage_issues(tree, code_text, filename))
    issues.extend(_find_mathtx_issues(code_text, filename))
    issues.extend(_find_emphasis_slice_issues(tree, code_text, filename))
    issues.extend(_find_dark_color_issues(code_text, filename))
    issues.extend(_find_pacing_issues(tree, code_text, filename))
    issues.extend(_find_layout_issues(tree, code_text, filename))

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
