from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import re
import html
import wave
from pathlib import Path
from typing import Any

try:
    from vieneu import Vieneu
except ImportError:  # pragma: no cover - optional dependency path
    Vieneu = None

DEFAULT_VOICE = "Trúc Ly"
DEFAULT_SAMPLE_RATE = 22050
DEFAULT_CHANNELS = 1
DEFAULT_SAMPWIDTH = 2
MAX_TTS_CHARS = 220


class VieneuTTS:
    """Wrapper nhẹ cho thư viện Vieneu để sinh audio theo từng đoạn."""

    def __init__(self, voice: str | None = None) -> None:
        self.voice = voice or DEFAULT_VOICE
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            if Vieneu is None:
                raise RuntimeError("Thư viện vieneu chưa được cài đặt")
            self._engine = Vieneu()
        return self._engine

    def synthesize_text(
        self,
        text: str,
        output_path: str | Path,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 0.0,
        style: str | None = None,
        temperature: float | None = None,
        silence_p: float | None = None,
        pause_before: float = 0.0,
        pause_after: float = 0.0,
    ) -> dict[str, Any]:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not text or not text.strip():
            raise ValueError("Text không được để trống")

        engine = self._get_engine()
        voice_name = voice or self.voice

        try:
            infer_kwargs: dict[str, Any] = {}
            if style:
                infer_kwargs["style"] = style
            if temperature is not None:
                infer_kwargs["temperature"] = float(temperature)
            if silence_p is not None:
                infer_kwargs["silence_p"] = float(silence_p)

            chunks = _split_text_for_tts(text, max_chars=MAX_TTS_CHARS)
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                tmp_dir = Path(tmp_dir_name)
                chunk_files: list[Path] = []
                for chunk_index, chunk_text in enumerate(chunks, start=1):
                    chunk_path = tmp_dir / f"chunk_{chunk_index}.wav"
                    audio = engine.infer(chunk_text, voice=voice_name, **infer_kwargs)
                    engine.save(audio, str(chunk_path))
                    if speed != 1.0:
                        chunk_path = _apply_playback_speed(chunk_path, speed)
                    if pitch != 0.0:
                        chunk_path = _apply_pitch_shift(chunk_path, pitch)
                    chunk_files.append(chunk_path)

                if len(chunk_files) == 1:
                    shutil.copyfile(chunk_files[0], output_path)
                else:
                    _concat_wav_files(chunk_files, output_path)

            return {
                "status": "ok",
                "output_file": str(output_path),
                "text": text,
                "voice": voice_name,
                "speed": speed,
                "pitch": pitch,
                "pause_before": pause_before,
                "pause_after": pause_after,
            }
        except Exception as exc:  # pragma: no cover - runtime dependency path
            self._write_placeholder(output_path)
            return {
                "status": "fallback",
                "output_file": str(output_path),
                "text": text,
                "voice": voice_name,
                "speed": speed,
                "pitch": pitch,
                "pause_before": pause_before,
                "pause_after": pause_after,
                "error": str(exc),
            }

    @staticmethod
    def _write_placeholder(output_path: Path) -> None:
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(DEFAULT_CHANNELS)
            wf.setsampwidth(DEFAULT_SAMPWIDTH)
            wf.setframerate(DEFAULT_SAMPLE_RATE)
            wf.writeframes(b"\x00" * int(DEFAULT_SAMPLE_RATE * 0.2 * DEFAULT_CHANNELS * DEFAULT_SAMPWIDTH))


def _normalize_numeric_string(value: str) -> str:
    return value.replace(",", ".")


def _parse_float(value: Any, default: float = 1.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = _normalize_numeric_string(value)
        matches = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
        if matches:
            return float(matches[0])
    return default


def _parse_pause(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = _normalize_numeric_string(value)
        matches = re.findall(r"\d+(?:\.\d+)?", normalized)
        if matches:
            return float(matches[0])
    return default


def _parse_duration(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = _normalize_numeric_string(value)
        matches = re.findall(r"\d+(?:\.\d+)?", normalized)
        if matches:
            return float(matches[0])
    return default


def _estimate_text_duration_seconds(text: str) -> float:
    """Ước lượng thời lượng lời nói theo số từ và ký tự."""
    if not text:
        return 0.0
    words = len(re.findall(r"\w+", text))
    chars = len(text)
    return max(0.4, words * 0.35 + chars * 0.01)


def _split_text_for_tts(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    chunks: list[str] = []
    current = ""

    def flush_current() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            flush_current()
            words = sentence.split()
            nested = ""
            for word in words:
                candidate = f"{nested} {word}".strip()
                if len(candidate) <= max_chars:
                    nested = candidate
                else:
                    if nested:
                        chunks.append(nested)
                    nested = word
            if nested:
                chunks.append(nested)
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            flush_current()
            current = sentence

    flush_current()
    return chunks or [text]


def _build_atempo_filter(speed: float) -> str:
    if speed <= 0:
        raise ValueError("speed phải lớn hơn 0")

    remaining = speed
    pieces: list[str] = []
    while remaining > 2.0:
        pieces.append("2.0")
        remaining /= 2.0
    while remaining < 0.5:
        pieces.append("0.5")
        remaining /= 0.5
    if not math.isclose(remaining, 1.0):
        pieces.append(f"{remaining:.6f}".rstrip("0").rstrip("."))
    return ",".join(f"atempo={piece}" for piece in pieces)


def _apply_playback_speed(audio_path: Path, speed: float) -> Path:
    if math.isclose(speed, 1.0):
        return audio_path

    filtered_path = audio_path.with_name(f"{audio_path.stem}_speed{audio_path.suffix}")
    filter_chain = _build_atempo_filter(speed)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-filter:a",
        filter_chain,
        "-vn",
        str(filtered_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return filtered_path


def _apply_pitch_shift(audio_path: Path, pitch: float) -> Path:
    if math.isclose(pitch, 0.0):
        return audio_path

    _, _, sample_rate = _get_wav_params(audio_path)
    pitch_factor = 2 ** (pitch / 12.0)
    filtered_path = audio_path.with_name(f"{audio_path.stem}_pitch{audio_path.suffix}")
    filter_chain = f"asetrate={sample_rate * pitch_factor},{_build_atempo_filter(1.0 / pitch_factor)}"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-filter:a",
        filter_chain,
        "-ar",
        str(sample_rate),
        str(filtered_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return filtered_path


def _concat_wav_files(input_files: list[Path], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not input_files:
        _write_silence_wav(output_path, 0.2)
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        list_path = Path(handle.name)
        for file_path in input_files:
            handle.write(f"file '{file_path.as_posix()}'\n")

    try:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except Exception:
            pass


def build_tts_segments_from_voiceover(voiceover_payload: dict[str, Any], default_voice: str = DEFAULT_VOICE) -> list[dict[str, Any]]:
    """Chuyển cấu trúc lời giảng thành danh sách các đoạn TTS."""
    items = voiceover_payload.get("voiceover", []) if isinstance(voiceover_payload, dict) else voiceover_payload
    segments: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        text = html.unescape(str(item.get("script", ""))).strip()
        if not text:
            continue

        pause_timing = str(item.get("pause_timing", "0"))
        pause_value = _parse_pause(pause_timing, default=0.15)
        # Giữ pause ngắn để lời giảng liền mạch (không quá 0.5s giữa các câu/cảnh).
        pause_value = max(0.0, min(0.5, pause_value))
        hold_duration = _parse_duration(item.get("hold_duration", 0.0), default=0.0)

        speed = _parse_float(item.get("reading_speed"), default=1.0)
        # Giữ tốc độ trung bình nếu input không hợp lệ; cho phép audio tự nhiên hơn với một chút variation.
        if speed < 0.85:
            speed = 0.9
        elif speed > 1.2:
            speed = 1.15

        scene_id = item.get("scene_id") or ""
        scene_name = item.get("scene_name") or _derive_scene_name_from_id(scene_id) or f"scene_{index}"
        scene_label = item.get("scene_label") or _scene_label_from_id(scene_id, scene_name, index)

        segments.append(
            {
                "index": index,
                "scene_id": scene_id or scene_name,
                "scene_label": scene_label,
                "scene_name": scene_name,
                "text": text,
                "voice": item.get("voice") or default_voice,
                "speed": speed,
                "pitch": 0.0,
                "pause_before": pause_value,
                "pause_after": pause_value,
                "hold_duration": hold_duration,
                "animation_instruction": item.get("animation_instruction", ""),
                "prompt_question": item.get("prompt_question", ""),
                "emphasis_line": item.get("emphasis_line", ""),
                "stress_words": item.get("stress_words", ""),
                "emotion": item.get("emotion", "") or "",
            }
        )

    return segments


def _scene_label_from_id(scene_id: str, scene_name: str, index: int) -> str:
    """Suy ra nhãn cảnh dạng [SCENE N] từ scene_id / scene_name / thứ tự."""
    for value in (scene_id, scene_name):
        m = re.search(r"\[SCENE\s*(\d+)\]", value or "", re.IGNORECASE)
        if m:
            return f"[SCENE {int(m.group(1))}]"
    for value in (scene_id, scene_name):
        m = re.search(r"scene[_-]?(\d+)", value or "", re.IGNORECASE)
        if m:
            return f"[SCENE {int(m.group(1))}]"
    return f"[SCENE {index}]"


def _derive_scene_name_from_id(scene_id: str) -> str:
    """Suy ra tên cảnh đọc được từ scene_id khi LLM quên cung cấp scene_name.

    vd "scene_4_mau_a" -> "Scene 4 mau a". Đủ dùng cho phụ đề/manifest khi thiếu.
    """
    scene_id = (scene_id or "").strip()
    if not scene_id:
        return ""
    cleaned = re.sub(r"[_-]+", " ", scene_id)
    return cleaned.strip().title()


def _build_scene_start_lookup(scene_timings: dict[str, Any] | None) -> dict[str, float]:
    """Map từ nhãn cảnh chuẩn hoá -> thời điểm bắt đầu (giây) theo timeline animation."""
    lookup: dict[str, float] = {}
    if not scene_timings:
        return lookup

    blocks = scene_timings.get("tts_blocks") or []
    for block in blocks:
        label = str(block.get("scene_label") or "").strip().lower()
        start = block.get("start_time")
        if label and isinstance(start, (int, float)):
            lookup[label] = float(start)
    return lookup


def _resolve_scene_start(segment: dict[str, Any], scene_starts: dict[str, float]) -> float | None:
    label = str(segment.get("scene_label") or "").strip().lower()
    return scene_starts.get(label)


def _get_wav_duration(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def _get_wav_params(audio_path: Path) -> tuple[int, int, int]:
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnchannels(), wf.getsampwidth(), wf.getframerate()


def synthesize_voiceover_segments(
    voiceover_payload: dict[str, Any],
    output_dir: str | Path,
    default_voice: str = DEFAULT_VOICE,
    target_duration: float | None = None,
    scene_timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sinh audio cho từng đoạn và tạo file tổng hợp cùng manifest JSON, căn theo thời lượng mục tiêu nếu có.

    scene_timings: dict có key "tts_blocks" (từ extract_animation_timings). Mỗi block có
    scene_label + start_time. Dùng để căn lề từng đoạn narration vào đúng thời điểm cảnh
    xuất hiện (audio-first: không để lời giảng trôi lệch khỏi animation).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = build_tts_segments_from_voiceover(voiceover_payload, default_voice=default_voice)
    engine = VieneuTTS(voice=default_voice)

    scene_starts = _build_scene_start_lookup(scene_timings)

    manifest_segments: list[dict[str, Any]] = []
    input_files: list[Path] = []

    current_time = 0.0
    for segment in segments:
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", segment["scene_name"]).strip("_") or f"segment_{segment['index']}"
        audio_path = output_dir / f"{safe_name}_{segment['index']}.wav"

        effective_speed = segment["speed"]

        # map emotion to style hint (best-effort)
        emotion = (segment.get("emotion") or "").lower()
        style_hint = None
        if "thân" in emotion or "tự nhiên" in emotion:
            style_hint = "tu_nhien"
        elif "hài" in emotion:
            style_hint = "hai_huoc"
        elif "nhấn" in emotion or "mạnh" in emotion:
            style_hint = "chan_chac"

        # set temperature and silence probability heuristics
        temperature = max(0.55, min(1.1, 0.8 + (effective_speed - 1.0) * 0.1))
        silence_p = 0.12 + max(0.0, (1.0 - effective_speed) * 0.08)

        result = engine.synthesize_text(
            text=segment["text"],
            output_path=audio_path,
            voice=segment["voice"],
            speed=effective_speed,
            pitch=segment["pitch"],
            style=style_hint,
            temperature=temperature,
            silence_p=silence_p,
            pause_before=0.0,
            pause_after=0.0,
        )

        voice_sample_rate = DEFAULT_SAMPLE_RATE
        if audio_path.exists():
            _, _, voice_sample_rate = _get_wav_params(audio_path)

        # Căn lề narration vào thời điểm cảnh bắt đầu (audio-first). Pause tự nhiên
        # và khoảng cách để khớp scene đều do silence WAV bên ngoài quản lý, không
        # nhúng trong engine → tránh đếm pause 2 lần và audio trôi lệch.
        target_start = _resolve_scene_start(segment, scene_starts)
        lead_in = 0.0
        if target_start is not None and current_time < target_start:
            lead_in = target_start - current_time
        elif lead_in <= 0:
            lead_in = float(segment["pause_before"])

        if lead_in > 0:
            pause_before_path = output_dir / f"{safe_name}_{segment['index']}_pause_before.wav"
            _write_silence_wav(pause_before_path, lead_in, sample_rate=voice_sample_rate)
            input_files.append(pause_before_path)
        pause_before_used = lead_in

        input_files.append(Path(result["output_file"]))

        segment_silence_after = float(segment["pause_after"])
        audio_duration = _get_wav_duration(audio_path) if audio_path.exists() else 0.0
        if segment.get("hold_duration", 0.0) > 0:
            hold_duration = float(segment["hold_duration"])
            if audio_duration + segment_silence_after < hold_duration:
                extra_silence = hold_duration - (audio_duration + segment_silence_after)
                segment_silence_after += extra_silence

        if segment_silence_after > 0:
            pause_after_path = output_dir / f"{safe_name}_{segment['index']}_pause_after.wav"
            _write_silence_wav(pause_after_path, segment_silence_after, sample_rate=voice_sample_rate)
            input_files.append(pause_after_path)

        segment_total_duration = audio_duration + pause_before_used + segment_silence_after
        segment_start = current_time
        segment_end = current_time + segment_total_duration
        current_time = segment_end

        manifest_segments.append(
            {
                "index": segment["index"],
                "scene_id": segment["scene_id"],
                "scene_label": segment["scene_label"],
                "scene_name": segment["scene_name"],
                "text": segment["text"],
                "voice": segment["voice"],
                "speed": effective_speed,
                "pitch": segment["pitch"],
                "pause_before": round(pause_before_used, 4),
                "pause_after": segment_silence_after,
                "hold_duration": segment.get("hold_duration", 0.0),
                "animation_instruction": segment.get("animation_instruction", ""),
                "prompt_question": segment.get("prompt_question", ""),
                "emphasis_line": segment.get("emphasis_line", ""),
                "audio_file": str(audio_path),
                "audio_duration": round(audio_duration, 4),
                "segment_duration": round(segment_total_duration, 4),
                "start_time": round(segment_start, 4),
                "end_time": round(segment_end, 4),
                "status": result["status"],
                "error": result.get("error"),
                "stress_words": segment["stress_words"],
            }
        )

    combined_path = output_dir / "combined_audio.wav"
    _combine_wav_files(input_files, combined_path)

    if target_duration is not None:
        _trim_or_pad_audio(combined_path, target_duration)

    return {
        "segments": manifest_segments,
        "combined_audio_file": str(combined_path),
        "output_dir": str(output_dir),
    }


def _write_silence_wav(output_path: str | Path, duration_seconds: float, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(DEFAULT_CHANNELS)
        wf.setsampwidth(DEFAULT_SAMPWIDTH)
        wf.setframerate(sample_rate)
        total_frames = int(duration_seconds * sample_rate)
        wf.writeframes(b"\x00" * total_frames * DEFAULT_CHANNELS * DEFAULT_SAMPWIDTH)


def _combine_wav_files(input_files: list[Path], output_path: str | Path) -> None:
    output_path = Path(output_path)
    if not input_files:
        _write_silence_wav(output_path, 0.2)
        return

    existing = [path for path in input_files if path.exists()]
    if not existing:
        _write_silence_wav(output_path, 0.2)
        return

    _concat_wav_files(existing, output_path)


def _trim_or_pad_audio(audio_path: str | Path, target_duration: float) -> None:
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return

    with wave.open(str(audio_path), "rb") as wf:
        params = wf.getparams()
        frame_rate = params.framerate
        n_frames = wf.getnframes()
        current_duration = n_frames / frame_rate

    if current_duration <= 0:
        return

    if current_duration < target_duration:
        pad_frames = int((target_duration - current_duration) * frame_rate)
        if pad_frames > 0:
            with wave.open(str(audio_path), "rb") as wf:
                existing_frames = wf.readframes(wf.getnframes())
            with wave.open(str(audio_path), "wb") as wf:
                wf.setparams(params)
                wf.writeframes(existing_frames)
                wf.writeframes(b"\x00" * pad_frames * params.nchannels * params.sampwidth)
