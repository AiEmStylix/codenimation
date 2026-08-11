from .prompt_utils import run_llm_json


def write_voiceover(pedagogy_design: dict, storyboard: dict, solution_text: str | None, client) -> dict:
    user_content = [
        "Dưới đây là kế hoạch giảng dạy và storyboard của video:",
        f"{pedagogy_design}",
        "",
        f"Storyboard:\n{storyboard}",
    ]
    if solution_text:
        user_content.extend([
            "",
            "Đây là lời giải chi tiết mà người dùng đã cung cấp:",
            f"{solution_text}",
            ""
        ])
    else:
        user_content.extend([
            "",
            "Người dùng chỉ cung cấp đề bài, hãy sinh lời giảng đầy đủ dựa trên storyboard và đề bài đó.",
            ""
        ])
    user_content.append(
        "Hãy viết lời giảng cho mỗi scene theo cấu trúc: giáo viên giảng bài → học sinh nhìn hình ảnh animation → Manim phải làm gì → giữ hình bao lâu."
    )
    user_content.append(
        "Mỗi scene phải gồm: scene_name, script, prompt_question, emphasis_line, pause_timing, stress_words, reading_speed, emotion, animation_instruction, hold_duration."
    )
    user_content.append(
        "Giọng đọc cần tự nhiên, thân thiện, như giáo viên thật sự đang giải thích trước lớp: dùng câu ngắn, nhấn nhá từ khóa, và thêm pause khi chuyển ý."
    )
    user_content.append(
        "Nếu storyboard hoặc teaching plan có điểm nhấn, common_errors hoặc emphasis, hãy tạo hiệu ứng nhấn mạnh rõ ràng trong animation_instruction."
    )
    return run_llm_json(client, "VOICEOVER_PROMPT.md", "\n\n".join(user_content))
