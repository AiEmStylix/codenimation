from .prompt_loader import load_prompt_from_file
from .model_config import DEFAULT_LLM_MODEL
from .prompt_utils import _log_llm_failure

def generate_script(math_problem: str, client, solution_text: str | None = None) -> str:
    system_instruction = load_prompt_from_file("SCRIPT_GENERATOR.md")
    user_content = f"Tạo kịch bản cho bài toán sau:\n{math_problem}"
    if solution_text:
        user_content += (
            "\n\nLỜI GIẢI MẪU CỦA GIÁO VIÊN (kịch bản PHẢI bám sát 100% phương pháp, "
            "thứ tự các bước và cách trình bày của lời giải này, không tự đổi cách giải):\n"
            f"{solution_text}"
        )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as exc:
        _log_llm_failure("text_failure", "SCRIPT_GENERATOR.md", "", user_content, str(exc))
        raise
