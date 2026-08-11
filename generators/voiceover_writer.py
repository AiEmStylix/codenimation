from .prompt_utils import run_llm_json


def write_voiceover(pedagogy_design: dict, storyboard: dict, solution_text: str | None, client, scene_names: list[str] | None = None) -> dict:
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
        "Mỗi scene phải gồm: scene_id, scene_label, scene_name, script, prompt_question, emphasis_line, pause_timing, stress_words, reading_speed, emotion, animation_instruction, hold_duration."
    )
    user_content.append(
        "BẮT BUỘC: mỗi segment phải có đủ scene_id (giống storyboard), scene_label dạng '[SCENE n]' (n = số thứ tự cảnh) và scene_name tiếng Việt đầy đủ (vd 'GV làm mẫu câu a'). KHÔNG để scene_name trống hoặc dùng 'scene_4'."
    )
    user_content.append(
        "Giọng đọc cần tự nhiên, thân thiện, như giáo viên thật sự đang giải thích trước lớp: dùng câu ngắn, nhấn nhá từ khóa, và thêm pause khi chuyển ý."
    )
    user_content.append(
        "Nếu storyboard hoặc teaching plan có điểm nhấn, common_errors hoặc emphasis, hãy tạo hiệu ứng nhấn mạnh rõ ràng trong animation_instruction."
    )
    if scene_names:
        user_content.append(
            "Danh sách scene bắt buộc giữ nguyên thứ tự và số lượng sau đây, không được thêm/bớt scene: " + ", ".join(scene_names)
        )
    user_content.append(
        "reading_speed và hold_duration phải là số thập phân cụ thể, không dùng khoảng, không dùng chữ, không dùng đơn vị kèm theo."
    )
    user_content.append(
        "emotion chỉ chọn một trong các nhãn: thân thiện, nhấn mạnh, chắc chắn, nhẹ nhàng, khơi gợi, cảnh báo."
    )
    return run_llm_json(client, "VOICEOVER_PROMPT.md", "\n\n".join(user_content))
