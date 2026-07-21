import streamlit as st
import os
import subprocess
import re
from openai import OpenAI

# ==========================================
# 1. CẤU HÌNH API TRUNG GIAN (BEEKNOEE)
# ==========================================
# Lấy API Key từ biến môi trường (Ví dụ đặt tên là BEEKNOEE_API_KEY)
api_key = os.getenv("BEEKNOEE_API_KEY", "")

# Khởi tạo OpenAI client trỏ về endpoint của Beeknoee
client = OpenAI(
    api_key=api_key,
    base_url="https://platform.beeknoee.com/v1"
) if api_key else None

# ==========================================
# 2. HÀM ĐỌC FILE PROMPT
# ==========================================
def load_prompt_from_file(filename: str) -> str:
    """Đọc nội dung từ file Markdown."""
    if not os.path.exists(filename):
        st.error(f"❌ Không tìm thấy file `{filename}`. Vui lòng tạo file này cùng thư mục với `app.py`.")
        st.stop()
    
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# ==========================================
# 3. CÁC HÀM PIPELINE (OPENAI COMPATIBLE)
# ==========================================
def generate_script(math_problem: str) -> str:
    system_instruction = load_prompt_from_file("SCRIPT_GENERATOR.md")
    
    response = client.chat.completions.create(
        model="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Tạo kịch bản cho bài toán sau:\n{math_problem}"}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def generate_manim_code(script: str) -> str:
    system_instruction = load_prompt_from_file("CODE_GENERATOR.md")
    
    response = client.chat.completions.create(
        model="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Viết code Manim cho kịch bản sau:\n{script}"}
        ],
        temperature=0.2
    )
    
    raw_code = response.choices[0].message.content
    
    # Xử lý an toàn: Xóa các thẻ markdown
    raw_code = re.sub(r"^```python\s*", "", raw_code)
    raw_code = re.sub(r"^```\s*", "", raw_code)
    raw_code = re.sub(r"\s*```$", "", raw_code)
    
    return raw_code

def render_video(filename="math_scene.py", scene_name="MathProblemScene"):
    # Lệnh chạy Manim (-ql: 480p 15fps)
    command = ["manim", "-ql", filename, scene_name]
    subprocess.run(command, check=True, capture_output=True, text=True)

# ==========================================
# 4. GIAO DIỆN STREAMLIT WEB APP
# ==========================================
st.set_page_config(page_title="AI Math Animator", page_icon="🎬", layout="wide")

st.title("🎬 AI Math Animator - Biến bài toán thành Video")
st.caption("Sử dụng Gemini 2.5 Pro (via Beeknoee API) để tự động hóa Manim.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 1. Nhập Bài Toán")
    math_input = st.text_area(
        "Nhập đề bài toán (hoặc phương trình):",
        value="Giải phương trình bậc hai: x^2 - 5x + 6 = 0",
        height=150
    )
    
    start_btn = st.button("🚀 Bắt Đầu Tạo Video", type="primary", use_container_width=True)

with col2:
    st.subheader("📺 2. Kết Quả")
    
    # Dùng đường dẫn tương đối để tránh lỗi
    cwd = os.getcwd()
    video_path = os.path.join(cwd, "media", "videos", "math_scene", "480p15", "MathProblemScene.mp4")
    
    if start_btn:
        if not api_key or not client:
            st.error("❌ Thiếu API Key. Vui lòng thiết lập biến môi trường `BEEKNOEE_API_KEY`.")
            st.stop()
            
        with st.status("🔄 Đang xử lý bằng Gemini 2.5 Pro...", expanded=True) as status:
            try:
                # Bước 1: Sinh kịch bản
                st.write("⏳ Đang phân tích bài toán & đọc file `SCRIPT_GENERATOR.md`...")
                script = generate_script(math_input)
                with st.expander("📝 Xem kịch bản được tạo"):
                    st.text(script)
                
                # Bước 2: Sinh Code Manim
                st.write("⏳ Đang dịch kịch bản sang code Python & đọc file `CODE_GENERATOR.md`...")
                code = generate_manim_code(script)
                with st.expander("💻 Xem code Python"):
                    st.code(code, language="python")
                
                # Bước 3: Lưu file
                st.write("⏳ Đang lưu file hệ thống...")
                with open("math_scene.py", "w", encoding="utf-8") as f:
                    f.write(code)
                
                # Bước 4: Render
                st.write("🎞️ Đang đưa vào Manim Engine để render video...")
                render_video("math_scene.py", "MathProblemScene")
                
                status.update(label="🎉 Hoàn tất Pipeline!", state="complete", expanded=False)
                
            except subprocess.CalledProcessError as e:
                status.update(label="❌ Lỗi khi render Manim", state="error", expanded=True)
                st.error("Manim Engine gặp lỗi khi biên dịch đoạn code được tạo.")
                st.code(e.stderr, language="bash")
                st.stop()
            except Exception as e:
                status.update(label="❌ Có lỗi hệ thống", state="error", expanded=True)
                st.error(f"Chi tiết: {str(e)}")
                st.stop()

    if os.path.exists(video_path):
        st.success("Video hoạt hình của bạn đã sẵn sàng!")
        st.video(video_path)
        
        with open(video_path, "rb") as v_file:
            st.download_button(
                label="📥 Tải Video MP4",
                data=v_file,
                file_name="math_animation.mp4",
                mime="video/mp4",
                use_container_width=True
            )
