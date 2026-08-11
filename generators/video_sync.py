from __future__ import annotations

import json
import re
import wave
from pathlib import Path
from typing import Any


def build_video_sync_manifest(timings: dict[str, Any], tts_manifest: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Tạo metadata đồng bộ audio – animation – subtitle."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    blocks = timings.get("tts_blocks") or []
    segments = timings.get("segments") or []
    tts_segments = tts_manifest.get("segments", [])

    blocks_by_label: dict[str, dict[str, Any]] = {}
    for block in blocks:
        label = normalize_label(block.get("scene_label"))
        if label:
            blocks_by_label.setdefault(label, block)

    def normalize_label(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower()

    tts_by_label: dict[str, dict[str, Any]] = {}
    tts_by_name: dict[str, dict[str, Any]] = {}
    tts_by_id: dict[str, dict[str, Any]] = {}
    for seg in tts_segments:
        label = normalize_label(seg.get("scene_label"))
        name = normalize_label(seg.get("scene_name"))
        scene_id = normalize_label(seg.get("scene_id"))
        if label:
            tts_by_label[label] = seg
        if name:
            tts_by_name[name] = seg
        if scene_id:
            tts_by_id[scene_id] = seg

    sync_items: list[dict[str, Any]] = []

    if blocks:
        for index, block in enumerate(blocks, start=1):
            block_label = normalize_label(block.get("scene_label"))
            tts_segment = None
            if block_label and block_label in tts_by_label:
                tts_segment = tts_by_label[block_label]
            elif block_label and block_label in tts_by_name:
                tts_segment = tts_by_name[block_label]
            elif block_label and block_label in tts_by_id:
                tts_segment = tts_by_id[block_label]
            elif index <= len(tts_segments):
                tts_segment = tts_segments[index - 1]

            sync_items.append(
                {
                    "index": index,
                    "scene_label": block.get("scene_label"),
                    "scene_id": _fallback_scene_id(tts_segment, block, block_label, blocks_by_label),
                    "scene_name": tts_segment.get("scene_name") if tts_segment else None,
                    "start_time": block.get("start_time", 0.0),
                    "end_time": block.get("end_time", 0.0),
                    "duration": block.get("duration", 0.0),
                    "audio_file": tts_segment.get("audio_file") if tts_segment else None,
                    "subtitle": tts_segment.get("text") if tts_segment else "",
                    "stress_words": tts_segment.get("stress_words") if tts_segment else "",
                    "tts_segment_index": tts_segment.get("index") if tts_segment else None,
                }
            )
    else:
        for index, segment in enumerate(segments, start=1):
            tts_segment = None
            if index <= len(tts_segments):
                tts_segment = tts_segments[index - 1]

            start_time = 0.0
            end_time = segment.get("duration", 0.0)
            if tts_segment and isinstance(tts_segment.get("start_time"), (int, float)):
                start_time = tts_segment.get("start_time", 0.0)
                end_time = tts_segment.get("end_time", segment.get("duration", 0.0))

            sync_items.append(
                {
                    "index": index,
                    "scene_label": segment.get("scene_label"),
                    "scene_id": tts_segment.get("scene_id") if tts_segment else None,
                    "scene_name": tts_segment.get("scene_name") if tts_segment else None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time if tts_segment else segment.get("duration", 0.0),
                    "audio_file": tts_segment.get("audio_file") if tts_segment else None,
                    "subtitle": tts_segment.get("text") if tts_segment else "",
                    "stress_words": tts_segment.get("stress_words") if tts_segment else "",
                    "tts_segment_index": tts_segment.get("index") if tts_segment else None,
                }
            )

    subtitle_path = output_dir / "subtitles.srt"
    _scale_times_to_audio(sync_items, timings, tts_manifest)
    _write_subtitles(sync_items, subtitle_path)
    manifest_path = output_dir / "sync_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "combined_audio_file": tts_manifest.get("combined_audio_file"),
                "sync_items": sync_items,
                "subtitle_file": str(subtitle_path),
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "combined_audio_file": tts_manifest.get("combined_audio_file"),
        "sync_items": sync_items,
        "subtitle_file": str(subtitle_path),
        "manifest_file": str(manifest_path),
    }


def _fallback_scene_id(
    tts_segment: dict[str, Any] | None,
    block: dict[str, Any],
    block_label: str,
    blocks_by_label: dict[str, dict[str, Any]],
) -> Any:
    """Lấy scene_id từ TTS segment; nếu thiếu thì fallback sang timings block."""
    if tts_segment and tts_segment.get("scene_id"):
        return tts_segment.get("scene_id")
    if block.get("scene_id"):
        return block.get("scene_id")
    fallback_block = blocks_by_label.get(block_label)
    if fallback_block and fallback_block.get("scene_id"):
        return fallback_block.get("scene_id")
    return None


def _write_subtitles(sync_items: list[dict[str, Any]], output_path: Path) -> None:
    lines: list[str] = []
    for index, item in enumerate(sync_items, start=1):
        start_ms = int(float(item.get("start_time", 0.0)) * 1000)
        end_ms = int(float(item.get("end_time", 0.0)) * 1000)
        subtitle_text = str(item.get("subtitle", "")).strip() or f"Scene {index}"
        lines.append(str(index))
        lines.append(f"{_ms_to_srt_time(start_ms)} --> {_ms_to_srt_time(end_ms)}")
        lines.append(subtitle_text)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _scale_times_to_audio(sync_items: list[dict[str, Any]], timings: dict[str, Any], tts_manifest: dict[str, Any]) -> None:
    """Nếu audio tổng hợp dài hơn video, timeline phụ đề được scale theo hệ số tăng tốc video.

    Hệ số scale = audio_duration / video_duration (đúng bằng tốc độ tăng tốc video
    trong attach_audio_to_video), nhờ đó phụ đề khớp chính xác với cảnh sau khi speed-up.
    """
    video_duration = float(timings.get("total_duration", 0.0) or 0.0)
    audio_path = tts_manifest.get("combined_audio_file")
    audio_duration = 0.0
    if audio_path:
        audio_path = Path(audio_path)
        if audio_path.exists():
            try:
                with wave.open(str(audio_path), "rb") as wf:
                    audio_duration = wf.getnframes() / wf.getframerate()
            except Exception:
                pass

    scale = 1.0
    if audio_duration > video_duration and video_duration > 0:
        scale = audio_duration / video_duration

    if scale <= 1.0:
        return

    for item in sync_items:
        if isinstance(item.get("start_time"), (int, float)):
            item["start_time"] = round(float(item["start_time"]) * scale, 4)
        if isinstance(item.get("end_time"), (int, float)):
            item["end_time"] = round(float(item["end_time"]) * scale, 4)
        if isinstance(item.get("duration"), (int, float)):
            item["duration"] = round(float(item["duration"]) * scale, 4)


def _ms_to_srt_time(total_ms: int) -> str:
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, milliseconds = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
