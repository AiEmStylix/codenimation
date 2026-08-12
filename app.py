import streamlit as st
import ast
import os
import subprocess
import sys
import re
import json
import html
import unicodedata
import shutil
import hashlib
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
    verify_solution,
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
    """Render Manim scene thành video chất lượng cao hơn vào media_dir nếu có."""
    command = ["manim", "-qm", filename, scene_name]
    if media_dir is not None:
        command.extend(["--media_dir", str(media_dir)])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=RENDER_TIMEOUT_SECONDS,
    )


def _probe_media_duration(media_path: str | Path) -> float:
    """Đọc thời lượng media (video/audio) bằng ffprobe, fallback sang wave."""
    media_path = Path(media_path)
    if not media_path.exists():
        return 0.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    if media_path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(media_path), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            pass
    return 0.0


def attach_audio_to_video(video_path: str | Path, audio_path: str | Path, output_path: str | Path) -> Path:
    """Ghép audio WAV/MP3 vào video MP4 bằng ffmpeg.

    Nguyên tắc audio-first: nếu audio dài hơn video, tăng tốc video để khớp độ dài
    audio (không bao giờ cắt đuôi lời giảng). Nếu audio ngắn hơn, giữ video nguyên
    và để audio kết thúc tự nhiên (mux theo độ dài video).
    """
    video_path = Path(video_path)
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video: {video_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Không tìm thấy audio: {audio_path}")

    video_duration = _probe_media_duration(video_path)
    audio_duration = _probe_media_duration(audio_path)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
    ]

    if audio_duration > video_duration and video_duration > 0:
        speed_factor = video_duration / audio_duration
        command += [
            "-filter:v",
            f"setpts=PTS/{speed_factor}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
        ]
    else:
        command += ["-c:v", "copy", "-shortest"]

    command.append(str(output_path))
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    return output_path


MIN_VIDEO_DURATION = 90.0
MAX_VIDEO_DURATION = 180.0
RENDER_TIMEOUT_SECONDS = 1800


def validate_python_syntax(filename: str) -> tuple[bool, str]:
    """Kiểm tra cú pháp Python trước khi render để tránh lỗi render do bộ mã không hợp lệ."""
    command = [sys.executable, "-m", "py_compile", filename]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode == 0:
        return True, ""
    return False, result.stderr or result.stdout


def _log_pipeline_failure(stage: str, detail: str, payload: dict[str, Any] | None = None) -> None:
    log_dir = RESULTS_ROOT / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{stage}.json"
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump({"stage": stage, "detail": detail, "payload": payload or {}}, fh, ensure_ascii=False, indent=2)


def _cache_key(math_value: str, solution_value: str | None) -> str:
    data = f"{math_value}\n---\n{solution_value or ''}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _get_scene_names(data: dict[str, Any], key: str) -> list[str]:
    items = data.get(key, []) if isinstance(data, dict) else []
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                scene_id = str(item.get("scene_id") or "").strip()
                name = str(item.get("scene_name") or item.get("name") or "").strip()
                if scene_id:
                    names.append(scene_id)
                elif name:
                    names.append(name)
    return names


def _validate_scene_alignment(storyboard: dict[str, Any], animation_plan: dict[str, Any], voiceover: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    storyboard_names = _get_scene_names(storyboard, "scenes")
    animation_names = _get_scene_names(animation_plan, "animations")
    voiceover_names = _get_scene_names(voiceover, "voiceover")

    if storyboard_names and animation_names and len(storyboard_names) != len(animation_names):
        raise ValueError(f"Storyboard và animation_plan lệch số scene: {len(storyboard_names)} != {len(animation_names)}")
    if storyboard_names and voiceover_names and len(storyboard_names) != len(voiceover_names):
        raise ValueError(f"Storyboard và voiceover lệch số scene: {len(storyboard_names)} != {len(voiceover_names)}")

    if storyboard_names and animation_names and storyboard_names != animation_names:
        raise ValueError("Storyboard và animation_plan lệch nội dung scene")
    if storyboard_names and voiceover_names and storyboard_names != voiceover_names:
        raise ValueError("Storyboard và voiceover lệch nội dung scene")

    return storyboard_names, animation_names, voiceover_names


def _count_scene_markers(code_text: str) -> int:
    return len(re.findall(r"#\s*\[SCENE\s*\d+\]", code_text, flags=re.IGNORECASE))


def _resolve_rendered_video_path(media_dir: Path, scene_name: str) -> Path:
    candidates = sorted(media_dir.glob("videos/**/*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if candidate.name == f"{scene_name}.mp4":
            return candidate
    for candidate in candidates:
        if candidate.suffix.lower() == ".mp4":
            return candidate
    raise FileNotFoundError(f"Không tìm thấy video render trong {media_dir}")


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

    def format_seconds(value: float) -> str:
        value_text = f"{value:.3f}".rstrip("0").rstrip(".")
        return value_text or "0"

    numeric_wait_pattern = re.compile(r"self\.wait\(\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*\)")
    empty_wait_pattern = re.compile(r"self\.wait\(\s*\)")

    last_numeric_wait = None
    for match in numeric_wait_pattern.finditer(code_text):
        last_numeric_wait = match
    if last_numeric_wait:
        current_value = float(last_numeric_wait.group("value"))
        new_value = format_seconds(current_value + extension_seconds)
        return (
            code_text[: last_numeric_wait.start("value")]
            + new_value
            + code_text[last_numeric_wait.end("value"):]
        )

    last_empty_wait = None
    for match in empty_wait_pattern.finditer(code_text):
        last_empty_wait = match
    if last_empty_wait:
        new_wait = f"self.wait({format_seconds(extension_seconds)})"
        return code_text[: last_empty_wait.start()] + new_wait + code_text[last_empty_wait.end():]

    lines = code_text.splitlines()
    if construct_node.body:
        last_stmt = construct_node.body[-1]
        source_line = lines[last_stmt.lineno - 1] if 0 <= last_stmt.lineno - 1 < len(lines) else ""
        indent_match = re.match(r"^(\s*)", source_line)
        body_indent = indent_match.group(1) if indent_match else "        "
    else:
        source_line = lines[construct_node.lineno - 1] if 0 <= construct_node.lineno - 1 < len(lines) else ""
        indent_match = re.match(r"^(\s*)", source_line)
        body_indent = (indent_match.group(1) if indent_match else "    ") + "    "

    insert_line = getattr(construct_node, "end_lineno", len(lines))
    lines.insert(insert_line, f"{body_indent}self.wait({format_seconds(extension_seconds)})")
    result = "\n".join(lines)
    if code_text.endswith("\n"):
        result += "\n"
    return result


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


def add_scene_ids_to_storyboard(storyboard: dict[str, Any]) -> dict[str, Any]:
    scenes = storyboard.get("scenes") if isinstance(storyboard, dict) else None
    if not isinstance(scenes, list):
        return storyboard

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        if scene.get("scene_id"):
            continue
        base_text = str(scene.get("scene_name") or scene.get("name") or scene.get("objective") or f"scene_{index}").strip()
        scene["scene_id"] = f"scene_{index}_{make_safe_slug(base_text)}"
    return storyboard


_SUBQUESTION_LETTER_RE = re.compile(r"(?<![A-Za-zÀ-ỹ])([a-c])\s*[).：:]", re.IGNORECASE)


def _extract_subquestion_letters(problem: str) -> list[str]:
    """Tìm các câu a/b/c xuất hiện trong đề bài (vd 'a)', 'b.', 'c)')."""
    letters = sorted({match.group(1).lower() for match in _SUBQUESTION_LETTER_RE.finditer(problem)})
    return [letter for letter in letters if letter in ("a", "b", "c")]


def _check_subquestion_coverage(problem: str, storyboard: dict[str, Any]) -> list[str]:
    """Trả về các câu (a/b/c) trong đề KHÔNG có scene 'GV làm mẫu' (phase 4) riêng."""
    letters = _extract_subquestion_letters(problem)
    if len(letters) < 2:
        return []

    scenes = storyboard.get("scenes") if isinstance(storyboard, dict) else []
    if not isinstance(scenes, list):
        return letters

    solved: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        try:
            if int(scene.get("phase") or 0) != 4:
                continue
        except (TypeError, ValueError):
            continue
        blob = " ".join(
            str(scene.get(key) or "") for key in ("scene_id", "scene_name", "objective", "visuals", "dialogue")
        )
        for letter in letters:
            if re.search(rf"(?<![A-Za-zÀ-ỹ]){letter}[).：:\s]", blob, re.IGNORECASE) or re.search(
                rf"(?:_|^){letter}(?:_|$)", scene.get("scene_id") or ""
            ):
                solved.add(letter)

    return [letter for letter in letters if letter not in solved]


if start_btn:
        if not api_key or not client:
            st.error("❌ Thiếu API Key. Vui lòng thiết lập biến môi trường `BEEKNOEE_API_KEY`.")
            st.stop()
            
        with st.status("🔄 Đang xử lý bằng Gemini 2.5 Pro...", expanded=True) as status:
            try:
                # Giải mã HTML entity (&lt; &gt; &amp; ...) mà LLM/input có thể mang theo
                # trước khi đưa vào pipeline, tránh nó lọt vào code LaTeX (vd "&lt;" trong MathTex).
                math_input = html.unescape(math_input or "")
                solution_input = html.unescape(solution_input or "")

                pipeline_key = _cache_key(math_input, solution_input if solution_input else None)
                pipeline_cache = st.session_state.setdefault("pipeline_cache", {})
                cached_run = pipeline_cache.get(pipeline_key, {}) if isinstance(pipeline_cache.get(pipeline_key, {}), dict) else {}

                # Tạo session riêng cho mỗi lần chạy
                topic_slug = make_safe_slug(math_input)
                session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + topic_slug
                session_dir = RESULTS_ROOT / session_id
                session_dir.mkdir(parents=True, exist_ok=True)

                # Bước 1: Phân tích bài học
                st.write("⏳ Đang phân tích bài học...")
                lesson_analysis = cached_run.get("lesson_analysis") or analyze_lesson(math_input, None, solution_input or None, client)
                cached_run["lesson_analysis"] = lesson_analysis
                with st.expander("📘 Kết quả phân tích bài học"):
                    st.json(lesson_analysis)

                # Bước 2: Sinh kịch bản
                st.write("⏳ Đang sinh kịch bản...")
                script = cached_run.get("script") or generate_script(math_input, client)
                cached_run["script"] = script
                with st.expander("📝 Kịch bản được tạo"):
                    st.text(script)

                # Bước 3: Tạo lời giải và phân tích lời giải
                st.write("⏳ Đang phân tích lời giải...")
                solution_analysis = cached_run.get("solution_analysis") or analyze_solution(solution_input if solution_input else None, math_input, client)
                cached_run["solution_analysis"] = solution_analysis
                with st.expander("🧮 Phân tích lời giải"):
                    st.json(solution_analysis)

                # Bước 4: Thiết kế sư phạm
                st.write("⏳ Đang thiết kế sư phạm...")
                pedagogy_design = cached_run.get("pedagogy_design") or design_pedagogy(math_input, solution_analysis, lesson_analysis, client)
                cached_run["pedagogy_design"] = pedagogy_design
                with st.expander("🎯 Kế hoạch sư phạm"):
                    st.json(pedagogy_design)

                # Bước 5: Lập storyboard
                st.write("⏳ Đang lập storyboard...")
                storyboard = cached_run.get("storyboard") or plan_storyboard(math_input, pedagogy_design, client)
                missing_parts = _check_subquestion_coverage(math_input, storyboard)
                if missing_parts:
                    st.warning(
                        f"⚠️ Storyboard chưa có scene 'GV làm mẫu' riêng cho câu {', '.join(missing_parts)}. "
                        "Đang lập lại storyboard để bổ sung..."
                    )
                    extra_instructions = (
                        "Storyboard trước đó THIẾU scene làm mẫu (phase 4) cho câu "
                        + ", ".join(f"'{letter}'" for letter in missing_parts)
                        + " của đề bài. Hãy bổ sung ĐỦ một scene 'GV làm mẫu' riêng cho MỖI câu "
                        + ", ".join(f"{letter}" for letter in missing_parts)
                        + " (scene_id chứa tên câu, vd scene_x_mau_a). Không biến câu trong đề thành bài tập vận dụng."
                    )
                    storyboard = plan_storyboard(math_input, pedagogy_design, client, extra_instructions=extra_instructions)
                storyboard = add_scene_ids_to_storyboard(storyboard)
                cached_run["storyboard"] = storyboard
                with st.expander("📋 Storyboard"):
                    st.json(storyboard)

                storyboard_names = _get_scene_names(storyboard, "scenes")

                # Bước 6: Lập animation plan
                st.write("⏳ Đang lập animation plan...")
                animation_plan = cached_run.get("animation_plan") or plan_animation(storyboard, client)
                cached_run["animation_plan"] = animation_plan
                with st.expander("✨ Animation Plan"):
                    st.json(animation_plan)

                # Bước 7: Sinh lời giảng
                st.write("⏳ Đang sinh lời giảng...")
                voiceover = cached_run.get("voiceover") or write_voiceover(
                    pedagogy_design,
                    storyboard,
                    solution_input if solution_input else None,
                    client,
                    scene_names=storyboard_names,
                )
                cached_run["voiceover"] = voiceover
                with st.expander("🎙️ Lời giảng"):
                    st.json(voiceover)

                storyboard_names, animation_names, voiceover_names = _validate_scene_alignment(storyboard, animation_plan, voiceover)
                if storyboard_names:
                    st.write(f"✅ Scene alignment: {len(storyboard_names)} scene(s)")

                # Bước 8: Sinh Code Manim
                st.write("⏳ Đang dịch kịch bản sang code Python & đọc file `CODE_GENERATOR.md`...")
                code = generate_manim_code(
                    script,
                    client,
                    storyboard=storyboard,
                    animation_plan=animation_plan,
                    voiceover=voiceover,
                    scene_names=storyboard_names,
                )

                if storyboard_names and _count_scene_markers(code) < len(storyboard_names):
                    repair_error = {
                        "error_code": "SCENE-ALIGN",
                        "message": "Code thiếu comment scene marker hoặc số scene không khớp storyboard.",
                        "cause": "Code generator phải giữ nguyên số lượng scene và chèn # [SCENE N] cho từng scene.",
                        "location": {"file": "math_scene.py", "line": 0, "column": 0},
                    }
                    code = repair_manim_code(code, repair_error, "Missing scene markers / scene count mismatch", client)

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

                if solution_input:
                    st.write("🔎 Đang kiểm tra độc lập tính đúng của lời giải trước khi render...")
                    solution_verification = verify_solution(solution_input, math_input, client)
                    with st.expander("🔍 Kết quả kiểm tra lời giải"):
                        st.json(solution_verification)
                    if not solution_verification.get("is_correct", False):
                        st.error("❌ Lời giải đầu vào có dấu hiệu sai hoặc chưa đủ chắc chắn. Pipeline dừng để tránh sinh video sai.")
                        st.stop()

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
                        video_path = _resolve_rendered_video_path(media_dir, "MathProblemScene")
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
                if total_duration > MAX_VIDEO_DURATION:
                    st.error(f"❌ Video vượt quá giới hạn tối đa {MAX_VIDEO_DURATION:.0f}s (hiện tại {total_duration:.1f}s). Hãy rút gọn storyboard/voiceover.")
                    _log_pipeline_failure("duration_over_max", "Video duration exceeded maximum", {"total_duration": total_duration, "max": MAX_VIDEO_DURATION})
                    st.stop()
                if total_duration < MIN_VIDEO_DURATION:
                    st.warning(f"⚠️ Video hiện tại ngắn hơn mục tiêu ({total_duration:.1f}s < {MIN_VIDEO_DURATION:.0f}s). Pipeline sẽ giữ nguyên nội dung và dựa vào voiceover/hold_duration để điều chỉnh thời gian hiển thị thay vì chèn self.wait() mù.")

                # Bước 9: TTS + đồng bộ timeline
                st.write("🎙️ Đang sinh audio bằng Vieneu và đồng bộ timeline...")
                tts_output_dir = session_dir / "tts"
                tts_manifest = synthesize_voiceover_segments(voiceover, tts_output_dir, target_duration=total_duration, scene_timings=timings_dict)
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
                pipeline_cache[pipeline_key] = cached_run
                st.session_state["pipeline_cache"] = pipeline_cache

                status.update(label="🎉 Hoàn tất Pipeline!", state="complete", expanded=False)

            except subprocess.CalledProcessError as e:
                status.update(label="❌ Lỗi khi render Manim", state="error", expanded=True)
                st.error("Manim Engine gặp lỗi khi biên dịch đoạn code được tạo.")
                st.code(e.stderr, language="bash")
                _log_pipeline_failure("render_error", e.stderr or str(e), {"code": e.returncode})
                st.stop()
            except FileNotFoundError:
                status.update(label="❌ Không tìm thấy Manim", state="error", expanded=True)
                st.error("Không tìm thấy lệnh `manim`. Vui lòng cài đặt Manim và đảm bảo nó có trong PATH.")
                _log_pipeline_failure("missing_binary", "Manim or ffmpeg binary not found")
                st.stop()
            except Exception as e:
                status.update(label="❌ Có lỗi hệ thống", state="error", expanded=True)
                st.error(f"Chi tiết: {str(e)}")
                _log_pipeline_failure("system_error", str(e))
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
