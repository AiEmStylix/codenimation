import streamlit as st
import os
import subprocess
import re
import json
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from generators import generate_script, generate_manim_code
from extract_animation_timings import extract_timings, build_tts_blocks
from collect_results import collect_session_results

RESULTS_ROOT = Path(__file__).resolve().parent / "results"

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
def render_video(filename="math_scene.py", scene_name="MathProblemScene", media_dir: str | Path | None = None):
    """Render Manim scene thành video (-ql: 480p 15fps) vào media_dir nếu có."""
    command = ["manim", "-ql", filename, scene_name]
    if media_dir is not None:
        command.extend(["--media_dir", str(media_dir)])
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
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
    
    cwd = Path(__file__).resolve().parent
    session_dir = None
    video_path = None
    timings_path = cwd / "math_scene_timings.json"

    def make_safe_slug(text: str, max_len: int = 40) -> str:
        text = text.lower()
        text = text.replace("\r", " ").replace("\n", " ")
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "_", text)
        text = text.strip("_")[:max_len]
        return text or "session"

    if start_btn:
        if not api_key or not client:
            st.error("❌ Thiếu API Key. Vui lòng thiết lập biến môi trường `BEEKNOEE_API_KEY`.")
            st.stop()
            
        with st.status("🔄 Đang xử lý bằng Gemini 2.5 Pro...", expanded=True) as status:
            try:
                # Tạo session riêng cho mỗi lần chạy
                topic_slug = make_safe_slug(math_input)
                session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + topic_slug
                session_dir = RESULTS_ROOT / session_id
                session_dir.mkdir(parents=True, exist_ok=True)

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

                # Bước 3: Lưu file vào thư mục session
                st.write("⏳ Đang lưu file code vào session riêng...")
                manim_file = session_dir / "math_scene.py"
                with open(manim_file, "w", encoding="utf-8") as f:
                    f.write(code)

                # Bước 4: Render
                st.write("🎞️ Đang đưa vào Manim Engine để render video...")
                media_dir = session_dir / "media"
                render_video(str(manim_file), "MathProblemScene", media_dir=media_dir)
                video_path = media_dir / "videos" / "math_scene" / "480p15" / "MathProblemScene.mp4"

                # Bước 5: Trích xuất timing animation → JSON
                st.write("⏱️ Đang trích xuất thời lượng animation...")
                timings_dict, timings_path = extract_and_save_timings(str(manim_file))
                st.session_state["timings"] = timings_dict
                with st.expander("🕐 Xem Animation Timings"):
                    st.json(timings_dict)

                # Bước 6: Thu gom kết quả vào thư mục results/
                st.write("📦 Đang lưu kết quả vào thư mục `results/`...")
                session_dir = collect_session_results(
                    topic=math_input,
                    script_text=script,
                    code_file=str(manim_file),
                    video_file=str(video_path),
                    timings_dict=timings_dict,
                    session_id=session_id,
                )
                st.session_state["session_dir"] = str(session_dir)

                status.update(label="🎉 Hoàn tất Pipeline!", state="complete", expanded=False)

            except subprocess.CalledProcessError as e:
                status.update(label="❌ Lỗi khi render Manim", state="error", expanded=True)
                st.error("Manim Engine gặp lỗi khi biên dịch đoạn code được tạo.")
                st.code(e.stderr, language="bash")
                st.stop()
            except FileNotFoundError:
                status.update(label="❌ Không tìm thấy Manim", state="error", expanded=True)
                st.error("Không tìm thấy lệnh `manim`. Vui lòng cài đặt Manim và đảm bảo nó có trong PATH.")
                st.stop()
            except Exception as e:
                status.update(label="❌ Có lỗi hệ thống", state="error", expanded=True)
                st.error(f"Chi tiết: {str(e)}")
                st.stop()

    if video_path and video_path.exists():
        st.success("Video hoạt hình của bạn đã sẵn sàng!")
        st.video(str(video_path))

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
        timings_path = session_dir / "math_scene_timings.json" if session_dir else None
        with col_json:
            if timings_path and timings_path.exists():
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
