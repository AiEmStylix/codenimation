import os
import streamlit as st


def load_prompt_from_file(filename: str) -> str:
    """Đọc nội dung từ file Markdown."""
    if not os.path.exists(filename):
        st.error(f"❌ Không tìm thấy file `{filename}`. Vui lòng tạo file này cùng thư mục với `app.py`.")
        st.stop()
    
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()
