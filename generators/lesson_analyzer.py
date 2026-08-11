from .prompt_utils import run_llm_json


def analyze_lesson(problem: str, lesson_content: str | None, teacher_solution: str | None, client) -> dict:
    user_content = [
        "Dưới đây là dữ liệu đầu vào của bài toán toán học:",
        f"Đề bài:\n{problem}",
    ]
    if lesson_content:
        user_content.append(f"\nNội dung bài học:\n{lesson_content}")
    if teacher_solution:
        user_content.append(f"\nLời giải giáo viên:\n{teacher_solution}")
    user_input = "\n\n".join(user_content)
    return run_llm_json(client, "LESSON_ANALYSIS.md", user_input)
