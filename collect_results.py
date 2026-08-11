"""
collect_results.py
──────────────────
Thu gom toàn bộ kết quả của một lần chạy pipeline (LLM script, Manim Python,
video render, timing JSON) vào một thư mục output có tổ chức.

Cấu trúc thư mục đầu ra:
    results/
    └── <session_id>/          ← timestamp + slug từ tên bài toán
        ├── script.md          ← kịch bản do LLM sinh (script_generator)
        ├── scene.py           ← code Manim do LLM sinh (code_generator)
        ├── timings.json       ← thời lượng animation (extract_animation_timings)
        └── video.mp4          ← video render từ Manim (copy/symlink)

Dùng CLI:
    python collect_results.py \\
        --script  "kịch bản text" \\
        --code    math_scene.py \\
        --video   media/videos/math_scene/480p15/MathProblemScene.mp4 \\
        --timings math_scene_timings.json \\
        --topic   "Phương trình bậc hai"

Hoặc dùng như module Python:
    from collect_results import collect_session_results
"""

import os
import shutil
import json
import argparse
import re
import textwrap
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Thư mục gốc chứa tất cả kết quả ─────────────────────────────────────────
RESULTS_ROOT = Path(__file__).parent / "results"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    """Chuyển chuỗi tuỳ ý thành slug ASCII an toàn cho tên thư mục."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = text[:max_len].strip("_")
    return text or "session"


def _make_session_id(topic: str) -> str:
    """Tạo session ID theo dạng: YYYYMMDD_HHMMSS_<slug>."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    slug = _slugify(topic)
    return f"{ts}_{slug}"


def _write_manifest(session_dir: Path, manifest: dict) -> None:
    """Ghi file manifest.json vào thư mục session."""
    manifest_path = session_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)


# ─── Hàm chính ────────────────────────────────────────────────────────────────

def collect_session_results(
    *,
    topic: str,
    script_text: Optional[str] = None,
    script_file: Optional[str] = None,
    code_file: Optional[str] = None,
    video_file: Optional[str] = None,
    timings_file: Optional[str] = None,
    timings_dict: Optional[dict] = None,
    results_root: Optional[str] = None,
    session_id: Optional[str] = None,
    copy_video: bool = True,
) -> Path:
    """
    Thu gom kết quả vào thư mục results/<session_id>/.

    Parameters
    ----------
    topic         : Tên/tiêu đề bài toán (dùng để tạo session_id)
    script_text   : Nội dung kịch bản dạng string
    script_file   : Đường dẫn file kịch bản có sẵn (ưu tiên sau script_text)
    code_file     : Đường dẫn file Python Manim
    video_file    : Đường dẫn video .mp4 đã render
    timings_file  : Đường dẫn file JSON timings có sẵn
    timings_dict  : Dict timings (nếu không có file)
    results_root  : Thư mục gốc (mặc định: ./results)
    session_id    : ID session (mặc định: tự tạo)
    copy_video    : True = copy video (False = chỉ ghi symlink nếu lớn)

    Returns
    -------
    Path          : Đường dẫn thư mục session vừa tạo
    """
    root = Path(results_root) if results_root else RESULTS_ROOT
    sid = session_id or _make_session_id(topic)
    session_dir = root / sid
    session_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    warnings: list[str] = []

    # ── 1. Kịch bản (script.md) ────────────────────────────────────────────
    if script_text:
        dest = session_dir / "script.md"
        dest.write_text(script_text, encoding="utf-8")
        copied_files.append("script.md")
    elif script_file and Path(script_file).exists():
        shutil.copy2(script_file, session_dir / "script.md")
        copied_files.append("script.md")
    else:
        warnings.append("script: không có nội dung hoặc file")

    # ── 2. Code Manim (scene.py) ────────────────────────────────────────────
    if code_file and Path(code_file).exists():
        shutil.copy2(code_file, session_dir / "scene.py")
        copied_files.append("scene.py")
    else:
        warnings.append(f"code_file: '{code_file}' không tồn tại")

    # ── 3. Timings JSON ─────────────────────────────────────────────────────
    if timings_file and Path(timings_file).exists():
        shutil.copy2(timings_file, session_dir / "timings.json")
        copied_files.append("timings.json")
    elif timings_dict:
        dest = session_dir / "timings.json"
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(timings_dict, fh, ensure_ascii=False, indent=2)
        copied_files.append("timings.json")
    else:
        warnings.append("timings: không có file hoặc dict")

    # ── 4. Video ────────────────────────────────────────────────────────────
    if video_file and Path(video_file).exists():
        dest = session_dir / "video.mp4"
        if copy_video:
            shutil.copy2(video_file, dest)
        else:
            dest.symlink_to(Path(video_file).resolve())
        copied_files.append("video.mp4")
    else:
        warnings.append(f"video_file: '{video_file}' không tồn tại")

    # ── 5. Manifest ─────────────────────────────────────────────────────────
    manifest = {
        "session_id": sid,
        "topic": topic,
        "created_at": datetime.now().isoformat(),
        "files": copied_files,
        "warnings": warnings,
    }
    _write_manifest(session_dir, manifest)

    return session_dir


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Thu gom kết quả pipeline Manim vào thư mục results/<session>/"
    )
    parser.add_argument("--topic",   required=True, help="Tên bài toán / tiêu đề")
    parser.add_argument("--script",  default=None,  help="Nội dung kịch bản (string)")
    parser.add_argument("--script-file", dest="script_file", default=None,
                        help="Đường dẫn file kịch bản")
    parser.add_argument("--code",    default=None,  help="Đường dẫn file Python Manim")
    parser.add_argument("--video",   default=None,  help="Đường dẫn video .mp4")
    parser.add_argument("--timings", default=None,  help="Đường dẫn file JSON timings")
    parser.add_argument("--output-dir", dest="output_dir", default=None,
                        help="Thư mục gốc chứa results (mặc định: ./results)")
    parser.add_argument("--no-copy-video", dest="copy_video",
                        action="store_false", default=True,
                        help="Dùng symlink thay vì copy video")
    args = parser.parse_args()

    session_dir = collect_session_results(
        topic=args.topic,
        script_text=args.script,
        script_file=args.script_file,
        code_file=args.code,
        video_file=args.video,
        timings_file=args.timings,
        results_root=args.output_dir,
        copy_video=args.copy_video,
    )

    print(f"✅ Đã lưu session vào: {session_dir}")
    manifest = json.loads((session_dir / "manifest.json").read_text())
    print(f"   📄 Files: {manifest['files']}")
    if manifest["warnings"]:
        for w in manifest["warnings"]:
            print(f"   ⚠️  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
