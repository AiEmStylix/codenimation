from .prompt_utils import run_llm_json


def plan_animation(storyboard: dict, client) -> dict:
    user_content = (
        "Dưới đây là storyboard cho video giáo dục dưới dạng JSON:\n"
        f"{storyboard}\n\n"
        "Hãy thiết kế animation cho từng scene. Trả về JSON gồm danh sách scene với thông tin animation rõ ràng."
    )
    return run_llm_json(client, "ANIMATION_PLANNER.md", user_content)
