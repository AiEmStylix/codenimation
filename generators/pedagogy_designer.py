from .prompt_utils import run_llm_json


def design_pedagogy(problem: str, solution_analysis: dict, lesson_analysis: dict, client) -> dict:
    user_content = (
        "Dưới đây là ĐỀ BÀI CHÍNH XÁC cần giảng dạy, cùng phân tích bài học và lời giải:\n\n"
        f"ĐỀ BÀI (phải bám sát, KHÔNG được đổi, thêm bớt hay sáng tạo lại đề):\n{problem}\n\n"
        "Phân tích bài học:\n"
        f"{lesson_analysis}\n\n"
        "Phân tích lời giải:\n"
        f"{solution_analysis}\n\n"
        "Hãy thiết kế sư phạm cho video giảng dạy ĐÚNG đề bài trên, chia lời giải thành từng bước nhỏ và trả về kết quả theo định dạng JSON."
    )
    return run_llm_json(client, "PEDAGOGY_DESIGN.md", user_content)
