"""
extract_animation_timings.py
────────────────────────────
Phân tích tĩnh (AST) một file Python chứa Manim scene để trích xuất
thời lượng (duration) của từng animation và self.wait().

Kết quả được lưu thành JSON gồm:
  - scene_name   : tên class Scene
  - total_duration : tổng thời gian (giây) ước tính
  - segments     : danh sách từng animation với:
      * index        : thứ tự (1-based)
      * scene_label  : nhãn [SCENE X] nếu có comment trước đó
      * type         : "animation" | "wait"
      * call         : chuỗi lệnh (vd "self.play(Write(title))")
      * duration     : thời lượng (giây, float)
      * run_time     : run_time nếu được truyền tường minh

Dùng:
    python extract_animation_timings.py math_scene.py -o timings.json
"""

import ast
import json
import argparse
import os
import re
from pathlib import Path
from typing import Optional

# ─── Thời lượng mặc định của từng loại Animation trong ManimCE ────────────────
DEFAULT_ANIM_DURATION: float = 1.0   # self.play() không có run_time tường minh
DEFAULT_WAIT_DURATION: float = 1.0   # self.wait() không có argument


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_numeric_value(node: ast.expr) -> Optional[float]:
    """Cố gắng lấy giá trị số từ một AST node (Constant, UnaryOp âm, v.v.)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _get_numeric_value(node.operand)
        return -inner if inner is not None else None
    return None


def _extract_run_time(call_node: ast.Call) -> Optional[float]:
    """Lấy giá trị run_time từ keyword arguments của ast.Call."""
    for kw in call_node.keywords:
        if kw.arg == "run_time":
            return _get_numeric_value(kw.value)
    return None


def _call_to_str(node: ast.Call) -> str:
    """Chuyển ast.Call thành chuỗi đơn giản để hiển thị."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unknown call>"


def _find_scene_class(tree: ast.Module) -> Optional[ast.ClassDef]:
    """Tìm class kế thừa Scene (hoặc bất kỳ *Scene nào)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = ast.unparse(base) if hasattr(ast, "unparse") else ""
                if "Scene" in base_name:
                    return node
    return None


def _find_construct(class_def: ast.ClassDef) -> Optional[ast.FunctionDef]:
    """Tìm phương thức construct() trong class."""
    for node in class_def.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "construct":
                return node
    return None


# ─── Lấy comment gần nhất ở trên (scene label) ────────────────────────────────

def _collect_scene_info(source: str) -> list[tuple[int, dict[str, Optional[str]]]]:
    """
    Quét toàn bộ source, trả về danh sách (line_number, scene_info) cho MỌI dòng
    chứa comment dạng # [SCENE X] (không phụ thuộc dòng liền kề).

    VD code có:
        # [SCENE 1]
        k_text = MathTex(...)          # dòng gán ở giữa
        self.play(Write(k_text))
    vẫn phải gắn "[SCENE 1]" cho self.play ở dòng sau đó.
    """
    labeled: list[tuple[int, dict[str, Optional[str]]]] = []
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            info = _extract_scene_info(stripped)
            if info:
                labeled.append((i, info))
    return labeled


def _scene_info_for_line(lineno: int, labeled: list[tuple[int, dict[str, Optional[str]]]]) -> Optional[dict[str, Optional[str]]]:
    """Trả về scene_info của comment [SCENE X] gần nhất nằm TRÊN dòng lineno."""
    current: Optional[dict[str, Optional[str]]] = None
    for line_no, info in labeled:
        if line_no > lineno:
            break
        current = info
    return current


_SCENE_LABEL_RE = re.compile(r"\[SCENE\s*\d+\]", re.IGNORECASE)
_SCENE_ID_RE = re.compile(r"scene_id\s*[:=]\s*([A-Za-z0-9_\-]+)", re.IGNORECASE)


def _extract_scene_info(comment: Optional[str]) -> Optional[dict[str, Optional[str]]]:
    if not comment:
        return None
    text = comment.strip()
    if text.startswith("#"):
        text = text.lstrip("#").strip()
    label = None
    scene_id = None

    m = _SCENE_LABEL_RE.search(text)
    if m:
        label = m.group(0)

    m_id = _SCENE_ID_RE.search(text)
    if m_id:
        scene_id = m_id.group(1)
    else:
        rest = text.replace(label or "", "", 1).strip()
        rest = re.sub(r"^scene_id\s*[:=]\s*", "", rest, flags=re.IGNORECASE)
        rest = re.sub(r"^#\s*", "", rest)
        tokens = re.split(r"\s+", rest.strip())
        if tokens:
            candidate = tokens[0].strip("[](){}")
            if candidate and candidate != "#":
                scene_id = candidate

    if label is None and scene_id is None:
        return None

    return {"scene_label": label, "scene_id": scene_id}


# ─── Core extractor ───────────────────────────────────────────────────────────

def extract_timings(source_path: str) -> dict:
    """
    Phân tích file Manim và trả về dict chứa thông tin timing.
    """
    source_path = str(source_path)
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()

    tree = ast.parse(source, filename=source_path)
    labeled_scene_info = _collect_scene_info(source)

    # Tìm class Scene
    scene_class = _find_scene_class(tree)
    scene_name = scene_class.name if scene_class else "UnknownScene"

    construct = _find_construct(scene_class) if scene_class else None
    if construct is None:
        return {
            "source_file": os.path.basename(source_path),
            "scene_name": scene_name,
            "total_duration": 0.0,
            "segments": [],
            "warning": "Không tìm thấy phương thức construct()"
        }

    segments = []
    index = 1

    relevant_calls = [stmt for stmt in ast.walk(construct) if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)]
    relevant_calls.sort(key=lambda node: getattr(node, "lineno", 0))

    for stmt in relevant_calls:
        call = stmt.value
        lineno = getattr(call, "lineno", None)

        current_scene_info = _scene_info_for_line(lineno, labeled_scene_info) if lineno else None

        call_str = _call_to_str(call)

        # ── self.play(...) ───────────────────────────────────────────────────
        if call_str.startswith("self.play("):
            run_time = _extract_run_time(call)
            duration = run_time if run_time is not None else DEFAULT_ANIM_DURATION

            segments.append({
                "index": index,
                "line": lineno,
                "scene_label": current_scene_info.get("scene_label") if current_scene_info else None,
                "scene_id": current_scene_info.get("scene_id") if current_scene_info else None,
                "type": "animation",
                "call": call_str,
                "run_time": run_time,
                "duration": round(duration, 4),
            })
            index += 1

        # ── self.wait(...) ───────────────────────────────────────────────────
        elif call_str.startswith("self.wait("):
            wait_duration = DEFAULT_WAIT_DURATION
            # self.wait() có thể có positional arg
            if call.args:
                v = _get_numeric_value(call.args[0])
                if v is not None:
                    wait_duration = v
            elif call.keywords:
                for kw in call.keywords:
                    if kw.arg in ("duration", None):  # None = **kwargs unpack
                        v = _get_numeric_value(kw.value)
                        if v is not None:
                            wait_duration = v

            segments.append({
                "index": index,
                "line": lineno,
                "scene_label": current_scene_info.get("scene_label") if current_scene_info else None,
                "scene_id": current_scene_info.get("scene_id") if current_scene_info else None,
                "type": "wait",
                "call": call_str,
                "run_time": None,
                "duration": round(wait_duration, 4),
            })
            index += 1

    # Sắp xếp theo thứ tự dòng
    segments.sort(key=lambda s: (s.get("line") or 0))
    # Re-index sau khi sort
    for i, seg in enumerate(segments, start=1):
        seg["index"] = i

    total = round(sum(s["duration"] for s in segments), 4)

    return {
        "source_file": os.path.basename(source_path),
        "scene_name": scene_name,
        "total_duration": total,
        "segments": segments,
    }


# ─── TTS helper: gộp các segment liên tiếp theo scene_label ──────────────────

def build_tts_blocks(timings: dict) -> list[dict]:
    """
    Nhóm các segment theo scene_label để tạo ra các block TTS.
    Mỗi block có:
        - scene_label : nhãn cảnh (hoặc null)
        - start_time  : giây bắt đầu
        - end_time    : giây kết thúc
        - duration    : tổng thời lượng
        - segment_indices : danh sách chỉ số segment trong block này
    Hữu ích để căn chỉnh audio TTS với từng cảnh.
    """
    blocks: list[dict] = []
    segments = timings["segments"]
    scene_key_candidates = [seg.get("scene_id") or seg.get("scene_label") for seg in segments]
    if not any(scene_key_candidates):
        elapsed = 0.0
        for seg in segments:
            duration = float(seg.get("duration", 0.0))
            blocks.append({
                "scene_label": None,
                "scene_id": None,
                "start_time": round(elapsed, 4),
                "end_time": round(elapsed + duration, 4),
                "duration": round(duration, 4),
                "segment_indices": [seg["index"]],
            })
            elapsed += duration
        return blocks

    current_key: Optional[str] = None
    current_scene_label: Optional[str] = None
    current_start: float = 0.0
    current_indices: list[int] = []
    elapsed: float = 0.0

    for seg in segments:
        scene_key = seg.get("scene_id") or seg.get("scene_label")
        if scene_key and scene_key != current_key:
            if current_indices:
                blocks.append({
                    "scene_label": current_scene_label,
                    "scene_id": current_key,
                    "start_time": round(current_start, 4),
                    "end_time": round(elapsed, 4),
                    "duration": round(elapsed - current_start, 4),
                    "segment_indices": current_indices,
                })
            current_key = scene_key
            current_scene_label = seg.get("scene_label")
            current_start = elapsed
            current_indices = []

        current_indices.append(seg["index"])
        elapsed += float(seg.get("duration", 0.0))

    # Flush block cuối
    if current_indices:
        blocks.append({
            "scene_label": current_scene_label,
            "scene_id": current_key,
            "start_time": round(current_start, 4),
            "end_time": round(elapsed, 4),
            "duration": round(elapsed - current_start, 4),
            "segment_indices": current_indices,
        })

    return blocks


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Trích xuất thời lượng animation từ file Manim Python → JSON"
    )
    parser.add_argument("manim_file", help="Đường dẫn đến file .py chứa Manim scene")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Đường dẫn file JSON đầu ra (mặc định: <tên_file>_timings.json)"
    )
    parser.add_argument(
        "--tts-blocks",
        action="store_true",
        help="Bao gồm thêm mảng tts_blocks được nhóm theo scene_label"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Format JSON đẹp (mặc định: bật)"
    )
    args = parser.parse_args()

    manim_path = Path(args.manim_file)
    if not manim_path.exists():
        print(f"❌ Không tìm thấy file: {manim_path}")
        return 1

    print(f"🔍 Đang phân tích: {manim_path.name} ...")
    timings = extract_timings(str(manim_path))

    if args.tts_blocks:
        timings["tts_blocks"] = build_tts_blocks(timings)

    output_path = args.output or manim_path.stem + "_timings.json"
    indent = 2 if args.pretty else None
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(timings, fh, ensure_ascii=False, indent=indent)

    n = len(timings["segments"])
    total = timings["total_duration"]
    print(f"✅ Đã lưu {n} segments | Tổng thời lượng: {total}s → {output_path}")

    if args.tts_blocks:
        nb = len(timings.get("tts_blocks", []))
        print(f"   📦 TTS blocks: {nb} cảnh")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
