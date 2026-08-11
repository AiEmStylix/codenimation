import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from .prompt_loader import load_prompt_from_file
from .model_config import DEFAULT_LLM_MODEL


LLM_LOG_DIR = Path(__file__).resolve().parent.parent / "results" / "_logs"


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


def _log_llm_failure(kind: str, prompt_file: str, raw: str, cleaned: str, detail: str) -> None:
    try:
        LLM_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LLM_LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{kind}.json"
        payload = {
            "kind": kind,
            "prompt_file": prompt_file,
            "detail": detail,
            "raw": raw,
            "cleaned": cleaned,
        }
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_llm_json(client: Any, prompt_file: str, user_content: str, temperature: float = 0.2, max_retries: int = 2) -> dict:
    prompt = load_prompt_from_file(prompt_file)
    retry_user_content = user_content
    last_error: str | None = None

    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": retry_user_content}
            ],
            temperature=temperature if attempt == 0 else 0.0,
        )
        raw = response.choices[0].message.content or ""
        cleaned = _clean_json_text(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raw_text = raw.strip()
            if raw_text.startswith("{") or raw_text.startswith("["):
                try:
                    return json.loads(raw_text)
                except json.JSONDecodeError:
                    pass

            last_error = (
                "LLM không trả về JSON hợp lệ.\n"
                f"Prompt file: {prompt_file}\n"
                f"Attempt: {attempt + 1}/{max_retries + 1}\n"
                f"Raw response:\n{raw}\n"
                f"Cleaned text:\n{cleaned}\n"
                f"JSON error: {str(exc)}"
            )
            _log_llm_failure("json_failure", prompt_file, raw, cleaned, str(exc))
            if attempt >= max_retries:
                break

            retry_user_content = (
                f"{user_content}\n\n"
                "Phản hồi trước đó không hợp lệ về JSON. Hãy trả lại đúng JSON thuần, không bọc markdown, không thêm giải thích.\n"
                f"Lỗi parser: {str(exc)}\n"
                f"Nội dung phản hồi lỗi trước đó:\n{raw}"
            )

    raise ValueError(last_error or f"LLM không trả về JSON hợp lệ từ {prompt_file}")


def run_llm_text(client: Any, prompt_file: str, user_content: str, temperature: float = 0.2) -> str:
    prompt = load_prompt_from_file(prompt_file)
    try:
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as exc:
        _log_llm_failure("text_failure", prompt_file, "", user_content, str(exc))
        raise
