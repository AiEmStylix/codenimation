from .prompt_utils import run_llm_json


def plan_storyboard(problem: str, pedagogy_design: dict, client, extra_instructions: str | None = None) -> dict:
    user_content = (
        "Dưới đây là đề bài toán và kế hoạch giảng dạy:\n"
        f"Đề bài:\n{problem}\n\n"
        f"Kế hoạch giảng dạy:\n{pedagogy_design}\n\n"
        "Hãy thiết kế storyboard cho một video giáo dục. Trả về JSON gồm nhiều scene."
    )
    if extra_instructions:
        user_content += "\n\nLƯU Ý THÊM TỪ NGƯỜI DÙNG:\n" + extra_instructions
    return run_llm_json(client, "STORYBOARD_PLANNER.md", user_content)
