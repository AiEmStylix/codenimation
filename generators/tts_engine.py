from __future__ import annotations

import audioop
import re
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
            # forward speed/pitch as hints if backend supports them
            infer_kwargs["speed"] = float(speed)
            infer_kwargs["pitch"] = float(pitch)

            audio = engine.infer(text, voice=voice_name, **infer_kwargs)
            engine.save(audio, str(output_path))
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


def _parse_float(value: Any, default: float = 1.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return default


def _parse_pause(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return default


def _parse_duration(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return default


def _estimate_text_duration_seconds(text: str) -> float:
    """Ước lượng thời lượng lời nói theo số từ và ký tự."""
    if not text:
        return 0.0
    words = len(re.findall(r"\w+", text))
    chars = len(text)
    return max(0.4, words * 0.35 + chars * 0.01)


def _db_to_linear(db: float) -> float:
    """Convert dB to linear amplitude factor relative to full scale (1.0)."""
    return 10 ** (db / 20.0)


def _normalize_wav(audio_path: Path, target_db: float = -18.0) -> None:
    """Normalize WAV file RMS to target dBFS (approximate, destructive edit)."""
    with wave.open(str(audio_path), "rb") as wf:
        params = wf.getparams()
        nch = params.nchannels
        sampw = params.sampwidth
        fr = params.framerate
        frames = wf.readframes(wf.getnframes())

    # compute current RMS
    try:
        cur_rms = audioop.rms(frames, sampw)
    except Exception:
        return

    if cur_rms == 0:
        return

    # max amplitude for sampwidth
    max_amp = float(2 ** (8 * sampw - 1) - 1)
    target_linear = max_amp * _db_to_linear(target_db)
    scale = float(target_linear) / float(cur_rms)
    # avoid extreme gain
    if scale <= 0:
        return
    if scale > 10:
        scale = 10.0

    try:
        new_frames = audioop.mul(frames, sampw, scale)
    except Exception:
        return

    # write back
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(nch)
        wf.setsampwidth(sampw)
        wf.setframerate(fr)
        wf.writeframes(new_frames)


def build_tts_segments_from_voiceover(voiceover_payload: dict[str, Any], default_voice: str = DEFAULT_VOICE) -> list[dict[str, Any]]:
    """Chuyển cấu trúc lời giảng thành danh sách các đoạn TTS."""
    items = voiceover_payload.get("voiceover", []) if isinstance(voiceover_payload, dict) else voiceover_payload
    segments: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        text = str(item.get("script", "")).strip()
        if not text:
            continue

        pause_timing = str(item.get("pause_timing", "0"))
        pause_value = _parse_pause(pause_timing, default=0.3)
        hold_duration = _parse_duration(item.get("hold_duration", 0.0), default=0.0)

        speed = _parse_float(item.get("reading_speed"), default=1.0)
        # Giữ tốc độ trung bình nếu input không hợp lệ; cho phép audio tự nhiên hơn với một chút variation.
        if speed < 0.85:
            speed = 0.9
        elif speed > 1.2:
            speed = 1.15

        # apply light punctuation around stress words to encourage TTS emphasis
        stress_raw = item.get("stress_words", "") or ""
        if stress_raw:
            try:
                stress_list = [s.strip() for s in re.split(r"[,;]", stress_raw) if s.strip()]
                for w in stress_list:
                    if not w:
                        continue
                    # surround the word with commas to induce a natural pause
                    text = re.sub(rf"\b({re.escape(w)})\b", r", \1,", text, flags=re.IGNORECASE)
            except Exception:
                pass

        segments.append(
            {
                "index": index,
                "scene_name": item.get("scene_name", f"scene_{index}"),
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


def _get_wav_duration(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def _get_wav_params(audio_path: Path) -> tuple[int, int, int]:
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnchannels(), wf.getsampwidth(), wf.getframerate()


def _resample_frames(frames: bytes, sampwidth: int, in_rate: int, out_rate: int, nchannels: int) -> bytes:
    if in_rate == out_rate:
        return frames
    converted, _ = audioop.ratecv(frames, sampwidth, nchannels, in_rate, out_rate, None)
    return converted


def _ensure_matching_params(frames: bytes, source_params: tuple[int, int, int], target_params: tuple[int, int, int]) -> bytes:
    src_nch, src_sampw, src_rate = source_params
    tgt_nch, tgt_sampw, tgt_rate = target_params

    if src_nch != tgt_nch:
        if src_nch == 2 and tgt_nch == 1:
            frames = audioop.tomono(frames, src_sampw, 0.5, 0.5)
        elif src_nch == 1 and tgt_nch == 2:
            frames = audioop.tostereo(frames, src_sampw, 1.0, 1.0)
        else:
            raise RuntimeError(f"Không hỗ trợ chuyển đổi {src_nch} → {tgt_nch} channels")
        src_nch = tgt_nch

    if src_rate != tgt_rate:
        frames = _resample_frames(frames, src_sampw, src_rate, tgt_rate, src_nch)
        src_rate = tgt_rate

    if src_sampw != tgt_sampw:
        raise RuntimeError("Không hỗ trợ chuyển đổi sampwidth khác nhau")

    return frames


def synthesize_voiceover_segments(
    voiceover_payload: dict[str, Any],
    output_dir: str | Path,
    default_voice: str = DEFAULT_VOICE,
    target_duration: float | None = None,
) -> dict[str, Any]:
    """Sinh audio cho từng đoạn và tạo file tổng hợp cùng manifest JSON, căn theo thời lượng mục tiêu nếu có."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = build_tts_segments_from_voiceover(voiceover_payload, default_voice=default_voice)
    engine = VieneuTTS(voice=default_voice)

    manifest_segments: list[dict[str, Any]] = []
    input_files: list[Path] = []

    if target_duration is not None and target_duration > 0 and segments:
        estimated_total_duration = sum(
            _estimate_text_duration_seconds(str(segment["text"]))
            + float(segment.get("pause_before", 0))
            + float(segment.get("pause_after", 0))
            for segment in segments
        )
        duration_scale = estimated_total_duration / target_duration if estimated_total_duration > 0 else 1.0
    else:
        duration_scale = 1.0

    current_time = 0.0
    for segment in segments:
        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", segment["scene_name"]).strip("_") or f"segment_{segment['index']}"
        audio_path = output_dir / f"{safe_name}_{segment['index']}.wav"

        effective_speed = segment["speed"] * duration_scale

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
            pause_before=segment["pause_before"],
            pause_after=segment["pause_after"],
        )

        voice_sample_rate = DEFAULT_SAMPLE_RATE
        if audio_path.exists():
            _, _, voice_sample_rate = _get_wav_params(audio_path)

        if segment["pause_before"] > 0:
            pause_before_path = output_dir / f"{safe_name}_{segment['index']}_pause_before.wav"
            _write_silence_wav(pause_before_path, segment["pause_before"], sample_rate=voice_sample_rate)
            input_files.append(pause_before_path)

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

        segment_total_duration = audio_duration + float(segment["pause_before"]) + segment_silence_after
        segment_start = current_time
        segment_end = current_time + segment_total_duration
        current_time = segment_end

        manifest_segments.append(
            {
                "index": segment["index"],
                "scene_name": segment["scene_name"],
                "text": segment["text"],
                "voice": segment["voice"],
                "speed": effective_speed,
                "pitch": segment["pitch"],
                "pause_before": segment["pause_before"],
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

    # Normalize loudness to ensure consistent perceived volume
    try:
        _normalize_wav(combined_path, target_db=-18.0)
    except Exception:
        pass

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

    frames: list[bytes] = []
    params = None

    for path in input_files:
        if not path.exists():
            continue
        with wave.open(str(path), "rb") as wf:
            src_params = wf.getparams()
            data = wf.readframes(wf.getnframes())
            if params is None:
                params = src_params
                frames.append(data)
                continue

            target_params = (params.nchannels, params.sampwidth, params.framerate)
            source_params = (src_params.nchannels, src_params.sampwidth, src_params.framerate)
            if source_params != target_params:
                data = _ensure_matching_params(data, source_params, target_params)
            frames.append(data)

    if not frames:
        _write_silence_wav(output_path, 0.2)
        return

    with wave.open(str(output_path), "wb") as wf:
        wf.setparams(params)
        for chunk in frames:
            wf.writeframes(chunk)


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

    if current_duration > target_duration:
        target_frames = int(target_duration * frame_rate)
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.readframes(target_frames)
        with wave.open(str(audio_path), "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames)
    elif current_duration < target_duration:
        pad_frames = int((target_duration - current_duration) * frame_rate)
        if pad_frames > 0:
            with wave.open(str(audio_path), "rb") as wf:
                existing_frames = wf.readframes(wf.getnframes())
            with wave.open(str(audio_path), "wb") as wf:
                wf.setparams(params)
                wf.writeframes(existing_frames)
                wf.writeframes(b"\x00" * pad_frames * DEFAULT_CHANNELS * DEFAULT_SAMPWIDTH)
