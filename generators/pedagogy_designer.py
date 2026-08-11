from .prompt_utils import run_llm_json


def design_pedagogy(solution_analysis: dict, lesson_analysis: dict, client) -> dict:
    user_content = (
        "Dưới đây là phân tích bài học và lời giải:\n"
        f"{lesson_analysis}\n\n"
        f"{solution_analysis}\n\n"
        "Hãy thiết kế sư phạm cho video giảng dạy, chia lời giải thành từng bước nhỏ và trả về kết quả theo định dạng JSON."
    )
    return run_llm_json(client, "PEDAGOGY_DESIGN.md", user_content)
