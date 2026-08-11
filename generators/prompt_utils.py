import json
import re
from typing import Any
from .prompt_loader import load_prompt_from_file


def _extract_json_block(text: str) -> str:
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if code_block:
        return code_block.group(1).strip()
    return text.strip()


def _clean_json_text(text: str) -> str:
    text = _extract_json_block(text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text.strip()


def run_llm_json(client: Any, prompt_file: str, user_content: str, temperature: float = 0.2) -> dict:
    prompt = load_prompt_from_file(prompt_file)
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=temperature,
    )
    raw = response.choices[0].message.content or ""
    cleaned = _clean_json_text(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Nếu cleanup không thành công, thử parse trực tiếp raw response.
        raw_text = raw.strip()
        if raw_text.startswith("{") or raw_text.startswith("["):
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                pass
        raise ValueError(
            "LLM không trả về JSON hợp lệ.\n"
            f"Prompt file: {prompt_file}\n"
            f"Raw response:\n{raw}\n"
            f"Cleaned text:\n{cleaned}\n"
            f"JSON error: {str(exc)}"
        ) from exc


def run_llm_text(client: Any, prompt_file: str, user_content: str, temperature: float = 0.2) -> str:
    prompt = load_prompt_from_file(prompt_file)
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content
