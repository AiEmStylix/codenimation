import os
from pathlib import Path
import streamlit as st

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt_from_file(filename: str) -> str:
    """Đọc nội dung từ file Markdown trong thư mục prompts."""
    prompt_path = PROMPT_DIR / filename
    if not prompt_path.exists():
        st.error(f"❌ Không tìm thấy file `{prompt_path}`. Vui lòng tạo file này trong thư mục `prompts/`.")
        st.stop()
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
