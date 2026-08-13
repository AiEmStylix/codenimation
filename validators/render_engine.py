from __future__ import annotations

import re
from typing import Any

RENDER_ERROR_PATTERNS = [
    (re.compile(r"SyntaxError:\s*(.*)\n.*File.*line\s*(\d+)"), "PY-001", "Python syntax error during Manim render."),
    (re.compile(r"IndentationError:\s*(.*)\n.*File.*line\s*(\d+)"), "PY-002", "Python indentation error during Manim render."),
    (re.compile(r"ModuleNotFoundError: No module named '(.*?)'"), "IMP-001", "Imported module không tồn tại."),
    (re.compile(r"ImportError:\s*(.*?)"), "IMP-003", "Import lỗi khi render — chỉ được import manim."),
    (re.compile(r"cannot import name '(.*?)'"), "IMP-002", "Import sai tên hoặc API không tồn tại."),
    (re.compile(r"NameError:\s*(.*?)"), "PY-007", "Thiếu biến/hàm — thường do xoá import ngoài ManimCE mà code vẫn dùng."),
    (re.compile(r"has no attribute '(.*?)'"), "MAN-008", "Manim API không tồn tại."),
    (re.compile(r"TypeError: (.*?)"), "PY-005", "Type error trong quá trình render."),
    (re.compile(r"AttributeError: (.*?)"), "PY-006", "Attribute error trong quá trình render."),
]


def parse_manim_render_error(stderr: str, filename: str = "math_scene.py") -> dict[str, Any]:
    error_message = stderr.strip()
    for pattern, error_code, summary in RENDER_ERROR_PATTERNS:
        match = pattern.search(error_message)
        if match:
            line = None
            if match.lastindex and match.lastindex >= 1:
                try:
                    line_val = int(match.group(match.lastindex))
                    line = line_val
                except (ValueError, TypeError):
                    line = 0
            return {
                "error_code": error_code,
                "category": "Render",
                "severity": "ERROR" if error_code not in ("PY-001", "PY-002") else "CRITICAL",
                "message": summary,
                "location": {"file": filename, "line": line or 0, "column": 0},
                "cause": error_message,
                "fix_strategy": "FIX_RENDER_ERROR",
                "original": "",
                "fixed": None,
                "regenerate_scene": False,
                "auto_fixable": False,
            }
    return {
        "error_code": "FF-007",
        "category": "Render",
        "severity": "ERROR",
        "message": "Lỗi render không xác định từ Manim.",
        "location": {"file": filename, "line": 0, "column": 0},
        "cause": error_message,
        "fix_strategy": "FIX_RENDER_ERROR",
        "original": "",
        "fixed": None,
        "regenerate_scene": False,
        "auto_fixable": False,
    }
