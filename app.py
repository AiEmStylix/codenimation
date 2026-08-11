import streamlit as st
import ast
import os
import subprocess
import sys
import re
import json
import unicodedata
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from langfuse.openai import OpenAI
from dotenv import load_dotenv
from generators import (
    generate_script,
    generate_manim_code,
    analyze_lesson,
    analyze_solution,
    design_pedagogy,
    plan_storyboard,
    plan_animation,
    write_voiceover,
    synthesize_voiceover_segments,
    build_video_sync_manifest,
)
from generators.code_repairer import repair_manim_code
from validators.review_engine import run_review_cycle
from validators.render_engine import parse_manim_render_error
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
    subprocess.run(command, check=True, capture_output=True, text=True)


def attach_audio_to_video(video_path: str | Path, audio_path: str | Path, output_path: str | Path) -> Path:
    """Ghép audio WAV/MP3 vào video MP4 bằng ffmpeg."""
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video: {video_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Không tìm thấy audio: {audio_path}")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


MIN_VIDEO_DURATION = 60.0
MAX_VIDEO_DURATION = 90.0


def validate_python_syntax(filename: str) -> tuple[bool, str]:
    """Kiểm tra cú pháp Python trước khi render để tránh lỗi render do bộ mã không hợp lệ."""
    command = [sys.executable, "-m", "py_compile", filename]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr or result.stdout


def extend_manim_duration(code_text: str, extension_seconds: float) -> str:
    """Tăng thời lượng video bằng cách điều chỉnh hoặc thêm câu lệnh self.wait()."""
    if extension_seconds <= 0:
        return code_text

    try:
        tree = ast.parse(code_text)
    except SyntaxError:
        return code_text

    class_node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MathProblemScene"), None)
    if class_node is None:
        return code_text
    construct_node = next((n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name == "construct"), None)
    if construct_node is None:
        return code_text

    last_wait = None
    for stmt in reversed(construct_node.body):
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self" and func.attr == "wait":
                last_wait = stmt
                break

    if last_wait:
        args = last_wait.value.args
        if len(args) == 1 and isinstance(args[0], ast.Constant) and isinstance(args[0].value, (int, float)):
            args[0].value += extension_seconds
            return ast.unparse(tree)

    wait_call = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="wait", ctx=ast.Load()),
            args=[ast.Constant(value=extension_seconds)],
            keywords=[],
        )
    )
    construct_node.body.append(wait_call)
    return ast.unparse(tree)


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

with col2:
    st.subheader("📘 2. Lời giải chi tiết (tùy chọn)")
    solution_input = st.text_area(
        "Nếu bạn đã có lời giải chi tiết, dán vào đây để AI viết lời giảng theo đúng hướng đó:",
        value="",
        height=150
    )

start_btn = st.button("🚀 Bắt Đầu Tạo Video", type="primary", use_container_width=True)

video_path = None
session_dir = None
timings_path = Path(__file__).resolve().parent / "math_scene_timings.json"

def make_safe_slug(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
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

                # Bước 1: Phân tích bài học
                st.write("⏳ Đang phân tích bài học...")
                lesson_analysis = analyze_lesson(math_input, None, None, client)
                with st.expander("📘 Kết quả phân tích bài học"):
                    st.json(lesson_analysis)

                # Bước 2: Sinh kịch bản
                st.write("⏳ Đang sinh kịch bản...")
                script = generate_script(math_input, client)
                with st.expander("📝 Kịch bản được tạo"):
                    st.text(script)

                # Bước 3: Tạo lời giải và phân tích lời giải
                st.write("⏳ Đang phân tích lời giải...")
                solution_analysis = analyze_solution(solution_input if solution_input else None, math_input, client)
                with st.expander("🧮 Phân tích lời giải"):
                    st.json(solution_analysis)

                # Bước 4: Thiết kế sư phạm
                st.write("⏳ Đang thiết kế sư phạm...")
                pedagogy_design = design_pedagogy(solution_analysis, lesson_analysis, client)
                with st.expander("🎯 Kế hoạch sư phạm"):
                    st.json(pedagogy_design)

                # Bước 5: Lập storyboard
                st.write("⏳ Đang lập storyboard...")
                storyboard = plan_storyboard(math_input, pedagogy_design, client)
                with st.expander("📋 Storyboard"):
                    st.json(storyboard)

                # Bước 6: Lập animation plan
                st.write("⏳ Đang lập animation plan...")
                animation_plan = plan_animation(storyboard, client)
                with st.expander("✨ Animation Plan"):
                    st.json(animation_plan)

                # Bước 7: Sinh lời giảng
                st.write("⏳ Đang sinh lời giảng...")
                voiceover = write_voiceover(pedagogy_design, storyboard, solution_input if solution_input else None, client)
                with st.expander("🎙️ Lời giảng"):
                    st.json(voiceover)

                # Bước 8: Sinh Code Manim
                st.write("⏳ Đang dịch kịch bản sang code Python & đọc file `CODE_GENERATOR.md`...")
                code = generate_manim_code(
                    script,
                    client,
                    storyboard=storyboard,
                    animation_plan=animation_plan,
                    voiceover=voiceover,
                )

                # Bước 8.1: Review code và auto-fix trước khi lưu
                review_result = run_review_cycle(code)
                fixed_code = review_result["fixed_code"]
                has_issues = bool(review_result["issues"])
                if fixed_code != code:
                    st.write("🛠️ Code đã được tự động sửa theo validator.")
                with st.expander("🧾 Kết quả Code Review"):
                    st.json(review_result)

                if has_issues:
                    blocking = [issue for issue in review_result["issues"] if issue["severity"] in ("CRITICAL", "ERROR")]
                    if blocking:
                        st.error("❌ Code có lỗi nghiêm trọng sau khi review. Vui lòng kiểm tra chi tiết và sửa thủ công trước khi render.")
                        st.stop()

                with st.expander("💻 Xem code Python"):
                    st.code(fixed_code, language="python")

                # Bước 8: Lưu file vào thư mục session
                st.write("⏳ Đang lưu file code vào session riêng...")
                manim_file = session_dir / "math_scene.py"
                with open(manim_file, "w", encoding="utf-8") as f:
                    f.write(fixed_code)

                # Bước 9: Render với vòng auto-fix nếu cần
                render_attempts = 0
                max_render_attempts = 3
                video_path = None
                render_errors: list[dict[str, Any]] = []
                while render_attempts < max_render_attempts:
                    render_attempts += 1

                    syntax_ok, compile_error = validate_python_syntax(str(manim_file))
                    if not syntax_ok:
                        error_info = parse_manim_render_error(compile_error, filename=str(manim_file))
                        render_errors.append(error_info)
                        st.warning(f"⚠️ Kiểm tra cú pháp trước render thất bại lần {render_attempts}.")
                        with st.expander(f"🧯 Lỗi cú pháp lần {render_attempts}"):
                            st.json(error_info)
                            st.code(compile_error, language="bash")
                        if render_attempts >= max_render_attempts:
                            st.error("❌ Đã đạt giới hạn số lần thử render. Dừng pipeline.")
                            break
                        st.write("🔄 Thử sửa mã bằng AI theo lỗi cú pháp trước khi render lại...")
                        fixed_code = repair_manim_code(fixed_code, error_info, compile_error, client)
                        review_result = run_review_cycle(fixed_code)
                        fixed_code = review_result["fixed_code"]
                        with st.expander("🧾 Kết quả review sau khi sửa cú pháp"):
                            st.json(review_result)
                        with open(manim_file, "w", encoding="utf-8") as f:
                            f.write(fixed_code)
                        continue

                    try:
                        st.write(f"🎞️ Đang render lần {render_attempts}...")
                        media_dir = session_dir / "media"
                        render_video(str(manim_file), "MathProblemScene", media_dir=media_dir)
                        video_path = media_dir / "videos" / "math_scene" / "480p15" / "MathProblemScene.mp4"
                        break
                    except subprocess.CalledProcessError as e:
                        stderr = e.stderr or ""
                        error_info = parse_manim_render_error(stderr, filename=str(manim_file))
                        render_errors.append(error_info)
                        st.warning(f"⚠️ Render thất bại lần {render_attempts}.")
                        with st.expander(f"🧯 Lỗi render lần {render_attempts}"):
                            st.json(error_info)
                            st.code(stderr, language="bash")
                        if render_attempts >= max_render_attempts:
                            st.error("❌ Đã đạt giới hạn số lần thử render. Dừng pipeline.")
                            break
                        st.write("🔄 Thử sửa mã bằng AI theo khi render lỗi...")
                        fixed_code = repair_manim_code(fixed_code, error_info, stderr, client)
                        review_result = run_review_cycle(fixed_code)
                        fixed_code = review_result["fixed_code"]
                        with st.expander("🧾 Kết quả review sau khi sửa lỗi render"):
                            st.json(review_result)
                        with open(manim_file, "w", encoding="utf-8") as f:
                            f.write(fixed_code)

                if video_path is None:
                    st.error("❌ Render Manim không thành công. Vui lòng kiểm tra lỗi và sửa thủ công.")
                    st.stop()

                # Bước 5: Trích xuất timing animation → JSON
                st.write("⏱️ Đang trích xuất thời lượng animation...")
                timings_dict, timings_path = extract_and_save_timings(str(manim_file))
                st.session_state["timings"] = timings_dict
                with st.expander("🕐 Xem Animation Timings"):
                    st.json(timings_dict)

                total_duration = float(timings_dict.get("total_duration", 0.0))
                if total_duration < MIN_VIDEO_DURATION:
                    extension = MIN_VIDEO_DURATION - total_duration
                    st.warning(f"⚠️ Video hiện tại quá ngắn ({total_duration:.1f}s). Tự động kéo dài thêm {extension:.1f}s để đạt tối thiểu {MIN_VIDEO_DURATION:.0f}s.")
                    with open(manim_file, "r", encoding="utf-8") as f:
                        code_text = f.read()
                    new_code = extend_manim_duration(code_text, extension)
                    with open(manim_file, "w", encoding="utf-8") as f:
                        f.write(new_code)

                    syntax_ok, compile_error = validate_python_syntax(str(manim_file))
                    if not syntax_ok:
                        error_info = parse_manim_render_error(compile_error, filename=str(manim_file))
                        st.error("❌ Không thể tự động mở rộng đoạn mã video vì lỗi cú pháp sau khi chỉnh sửa.")
                        st.json(error_info)
                        st.code(compile_error, language="bash")
                        st.stop()

                    timings_dict, timings_path = extract_and_save_timings(str(manim_file))
                    total_duration = float(timings_dict.get("total_duration", 0.0))
                    st.write(f"✅ Đã kéo dài video. Tổng thời lượng hiện tại: {total_duration:.1f}s.")
                    with st.expander("🕐 Xem Animation Timings sau khi kéo dài"):
                        st.json(timings_dict)

                # Bước 9: TTS + đồng bộ timeline
                st.write("🎙️ Đang sinh audio bằng Vieneu và đồng bộ timeline...")
                tts_output_dir = session_dir / "tts"
                target_duration = total_duration
                tts_manifest = synthesize_voiceover_segments(voiceover, tts_output_dir, target_duration=target_duration)
                sync_manifest = build_video_sync_manifest(timings_dict, tts_manifest, session_dir / "sync")
                with st.expander("🗣️ Kết quả TTS"):
                    st.json(tts_manifest)
                with st.expander("🧭 Sync manifest"):
                    st.json(sync_manifest)

                audio_path = Path(tts_manifest.get("combined_audio_file", "")) if tts_manifest.get("combined_audio_file") else None
                if audio_path and audio_path.exists():
                    final_video_path = session_dir / "video_with_audio.mp4"
                    video_path = attach_audio_to_video(video_path, audio_path, final_video_path)
                    st.write("✅ Đã ghép audio vào video thành công")
                else:
                    st.warning("⚠️ Không tìm thấy file audio tổng hợp để ghép vào video")

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

with col2:
    if video_path and video_path.exists():
        st.success("Video hoạt hình của bạn đã sẵn sàng với âm thanh!")
        st.video(str(video_path))

        col_dl, col_json = st.columns(2)
        with col_dl:
            with open(video_path, "rb") as v_file:
                st.download_button(
                    label="📥 Tải Video MP4 có âm thanh",
                    data=v_file,
                    file_name="math_animation_with_audio.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        with col_json:
            if session_dir:
                audio_path = session_dir / "tts" / "combined_audio.wav"
                if audio_path.exists():
                    with open(audio_path, "rb") as audio_file:
                        st.download_button(
                            label="🎧 Tải file audio",
                            data=audio_file,
                            file_name="voiceover.wav",
                            mime="audio/wav",
                            use_container_width=True
                        )

        # Nút tải timings JSON (nếu đã có)
        timings_path = session_dir / "math_scene_timings.json" if session_dir else None
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
