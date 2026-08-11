import re
from typing import Any
from .prompt_utils import run_llm_text


def _strip_code_blocks(text: str) -> str:
    text = re.sub(r"^```(?:python)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    return text.strip()


def repair_manim_code(code_text: str, error_info: dict[str, Any], raw_error: str, client) -> str:
    """Sửa mã Manim bằng AI dựa trên thông báo lỗi cụ thể và trả về mã Python thuần."""
    prompt_data = {
        "error_code": error_info.get("error_code", "UNKNOWN"),
        "message": error_info.get("message", ""),
        "cause": error_info.get("cause", ""),
        "location": error_info.get("location", {}),
        "raw_error": raw_error,
    }
    user_content = (
        "Dưới đây là mã Python sinh ra cho Manim và thông báo lỗi khi render hoặc kiểm tra cú pháp:\n\n"
        f"Error code: {prompt_data['error_code']}\n"
        f"Error message: {prompt_data['message']}\n"
        f"Cause: {prompt_data['cause']}\n"
        f"Location: {prompt_data['location']}\n\n"
        "Raw error:\n"
        f"{prompt_data['raw_error']}\n\n"
        "Mã hiện tại:\n"
        f"{code_text}\n\n"
        "Hãy sửa lại mã bằng cách sửa đúng chỗ lỗi và chỉ sửa những phần cần thiết. Trả về nguyên mã Python hoàn chỉnh, KHÔNG bọc trong markdown code block, KHÔNG thêm giải thích.")
    repaired = run_llm_text(client, "CODE_REPAIR.md", user_content, temperature=0.2)
    return _strip_code_blocks(repaired)
