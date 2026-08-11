from .prompt_utils import run_llm_json


def analyze_solution(solution_text: str | None, problem: str, client) -> dict:
    if solution_text:
        user_input = (
            "Dưới đây là lời giải hoặc hướng dẫn đã có:\n"
            f"{solution_text}\n\n"
            "Hãy phân tích lời giải này theo các yêu cầu: tính đúng, tính logic, tính sư phạm, bước nhảy tư duy, bước thừa, thiếu giải thích, ký hiệu toán học, lỗi trình bày."
        )
    else:
        user_input = (
            "Không có lời giải giáo viên. Dựa trên đề bài sau, hãy đề xuất một lời giải chi tiết và phân tích nó theo các yêu cầu: "
            "tính đúng, tính logic, tính sư phạm, bước nhảy tư duy, bước thừa, thiếu giải thích, ký hiệu toán học, lỗi trình bày.\n"
            f"Đề bài:\n{problem}"
        )
    return run_llm_json(client, "SOLUTION_ANALYSIS.md", user_input)


def verify_solution(solution_text: str, problem: str, client) -> dict:
    user_input = (
        "Hãy kiểm tra độc lập tính đúng sai của lời giải sau so với đề bài. "
        "Nếu có bước sai, thiếu điều kiện, nhảy bước, hoặc kết luận mâu thuẫn, hãy đánh dấu is_correct = false.\n\n"
        f"Đề bài:\n{problem}\n\n"
        f"Lời giải cần kiểm tra:\n{solution_text}\n\n"
        "Trả về JSON đúng schema trong prompt."
    )
    return run_llm_json(client, "SOLUTION_VERIFICATION.md", user_input)
