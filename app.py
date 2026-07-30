import streamlit as st
import os
import subprocess
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
from generators import generate_script, generate_manim_code
from extract_animation_timings import extract_timings, build_tts_blocks
from collect_results import collect_session_results

load_dotenv()
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
# 2. CÁC HÀM PIPELINE (OPENAI COMPATIBLE)
# ==========================================
def render_video(filename="math_scene.py", scene_name="MathProblemScene"):
    """Render Manim scene thành video (-ql: 480p 15fps)."""
    command = ["manim", "-ql", filename, scene_name]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def extract_and_save_timings(manim_file: str, include_tts_blocks: bool = True) -> tuple[dict, str]:
    """
    Phân tích file Manim và lưu timings.json cạnh file đó.
    Trả về (timings_dict, đường dẫn file json).
    """
    timings = extract_timings(manim_file)
    if include_tts_blocks:
        timings["tts_blocks"] = build_tts_blocks(timings)
    out_path = os.path.splitext(manim_file)[0] + "_timings.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(timings, fh, ensure_ascii=False, indent=2)
    return timings, out_path

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
                script = generate_script(math_input, client)
                with st.expander("📝 Xem kịch bản được tạo"):
                    st.text(script)

                # Bước 2: Sinh Code Manim
                st.write("⏳ Đang dịch kịch bản sang code Python & đọc file `CODE_GENERATOR.md`...")
                code = generate_manim_code(script, client)
                with st.expander("💻 Xem code Python"):
                    st.code(code, language="python")

                # Bước 3: Lưu file
                st.write("⏳ Đang lưu file hệ thống...")
                manim_file = "math_scene.py"
                with open(manim_file, "w", encoding="utf-8") as f:
                    f.write(code)

                # Bước 4: Render
                st.write("🎞️ Đang đưa vào Manim Engine để render video...")
                render_video(manim_file, "MathProblemScene")

                # Bước 5: Trích xuất timing animation → JSON
                st.write("⏱️ Đang trích xuất thời lượng animation...")
                timings_dict, timings_path = extract_and_save_timings(manim_file)
                st.session_state["timings"] = timings_dict
                with st.expander("🕐 Xem Animation Timings"):
                    st.json(timings_dict)

                # Bước 6: Thu gom kết quả vào thư mục results/
                st.write("📦 Đang lưu kết quả vào thư mục `results/`...")
                session_dir = collect_session_results(
                    topic=math_input,
                    script_text=script,
                    code_file=manim_file,
                    video_file=video_path,
                    timings_dict=timings_dict,
                )
                st.session_state["session_dir"] = str(session_dir)

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

        col_dl, col_json = st.columns(2)
        with col_dl:
            with open(video_path, "rb") as v_file:
                st.download_button(
                    label="📥 Tải Video MP4",
                    data=v_file,
                    file_name="math_animation.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        # Nút tải timings JSON (nếu đã có)
        timings_path = os.path.join(cwd, "math_scene_timings.json")
        with col_json:
            if os.path.exists(timings_path):
                with open(timings_path, "rb") as tj:
                    st.download_button(
                        label="⏱️ Tải Timings JSON",
                        data=tj,
                        file_name="math_scene_timings.json",
                        mime="application/json",
                        use_container_width=True
                    )

    # Hiển thị đường dẫn thư mục kết quả nếu có
    if "session_dir" in st.session_state:
        st.info(f"📁 Kết quả đã được lưu tại: `{st.session_state['session_dir']}`")
