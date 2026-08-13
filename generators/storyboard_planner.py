from .prompt_utils import run_llm_json


def plan_storyboard(problem: str, pedagogy_design: dict, client, solution_text: str | None = None, extra_instructions: str | None = None) -> dict:
    user_content = (
        "Dưới đây là đề bài toán và kế hoạch giảng dạy:\n"
        f"Đề bài:\n{problem}\n\n"
        f"Kế hoạch giảng dạy:\n{pedagogy_design}\n\n"
        "Hãy thiết kế storyboard cho một video giáo dục. Trả về JSON gồm nhiều scene."
    )
    if solution_text:
        user_content += (
            "\n\nLỜI GIẢI MẪU CỦA GIÁO VIÊN (mọi scene 'GV làm mẫu' PHẢI tách đúng và đi theo "
            "phương pháp, thứ tự từng bước, cách trình bày của lời giải này; không tự sáng tạo cách giải khác):\n"
            f"{solution_text}"
        )
    if extra_instructions:
        user_content += "\n\nLƯU Ý THÊM TỪ NGƯỜI DÙNG:\n" + extra_instructions
    return run_llm_json(client, "STORYBOARD_PLANNER.md", user_content)
