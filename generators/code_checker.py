from validators.review_engine import analyze_code


def review_code(code_text: str, client=None) -> dict:
    """Review code bằng validator nội bộ, không cần LLM nếu đã có logic cố định."""
    return analyze_code(code_text)
