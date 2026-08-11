from .prompt_loader import load_prompt_from_file
from .model_config import DEFAULT_LLM_MODEL
from .prompt_utils import _log_llm_failure

def generate_script(math_problem: str, client) -> str:
    system_instruction = load_prompt_from_file("SCRIPT_GENERATOR.md")
    user_content = f"Tạo kịch bản cho bài toán sau:\n{math_problem}"

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
