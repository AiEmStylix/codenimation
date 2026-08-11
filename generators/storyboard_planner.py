from .prompt_utils import run_llm_json


def plan_storyboard(problem: str, pedagogy_design: dict, client) -> dict:
    user_content = (
        "Dưới đây là đề bài toán và kế hoạch giảng dạy:\n"
        f"Đề bài:\n{problem}\n\n"
        f"Kế hoạch giảng dạy:\n{pedagogy_design}\n\n"
        "Hãy thiết kế storyboard cho một video giáo dục. Trả về JSON gồm nhiều scene."
    )
    return run_llm_json(client, "STORYBOARD_PLANNER.md", user_content)
