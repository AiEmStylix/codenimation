import wave
from pathlib import Path

from extract_animation_timings import extract_timings
from generators.tts_engine import _parse_float, build_tts_segments_from_voiceover
from generators.video_sync import build_video_sync_manifest


def test_build_tts_segments_from_voiceover(tmp_path: Path) -> None:
    payload = {
        "voiceover": [
            {
                "scene_name": "Scene 1",
                "script": "Xin chào",
                "reading_speed": "1.2",
                "pause_timing": "0.3",
                "stress_words": "chào",
            }
        ]
    }

    segments = build_tts_segments_from_voiceover(payload)

    assert len(segments) == 1
    assert segments[0]["scene_name"] == "Scene 1"
    assert segments[0]["speed"] == 1.2
    assert segments[0]["pause_before"] == 0.3


def test_build_video_sync_manifest(tmp_path: Path) -> None:
    timings = {
        "tts_blocks": [
            {"scene_label": "[SCENE 1]", "start_time": 0.0, "end_time": 3.0, "duration": 3.0}
        ],
        "segments": [{"scene_label": "[SCENE 1]", "duration": 3.0}],
    }
    tts_manifest = {
        "segments": [
            {"text": "Đây là đoạn đầu", "audio_file": "audio.wav", "stress_words": "đầu"}
        ],
        "combined_audio_file": "combined.wav",
    }

    manifest = build_video_sync_manifest(timings, tts_manifest, tmp_path)

    assert manifest["sync_items"][0]["subtitle"] == "Đây là đoạn đầu"
    assert manifest["sync_items"][0]["scene_name"] is None
    assert manifest["subtitle_file"].endswith("subtitles.srt")


def test_build_video_sync_manifest_matches_tts_scene_name(tmp_path: Path) -> None:
    timings = {
        "tts_blocks": [
            {"scene_label": "[SCENE 1]", "start_time": 0.0, "end_time": 4.0, "duration": 4.0}
        ],
        "segments": [{"scene_label": "[SCENE 1]", "duration": 4.0}],
    }
    tts_manifest = {
        "segments": [
            {"scene_name": "Scene 1", "text": "Đây là đoạn đầu", "audio_file": "audio.wav", "stress_words": "đầu"}
        ],
        "combined_audio_file": "combined.wav",
    }

    manifest = build_video_sync_manifest(timings, tts_manifest, tmp_path)

    assert manifest["sync_items"][0]["scene_name"] == "Scene 1"
    assert manifest["sync_items"][0]["subtitle"] == "Đây là đoạn đầu"
    assert manifest["subtitle_file"].endswith("subtitles.srt")


def test_build_tts_segments_from_voiceover_preserves_hold_and_instruction() -> None:
    payload = {
        "voiceover": [
            {
                "scene_name": "Scene A",
                "script": "Giải thích A",
                "reading_speed": "1.0",
                "pause_timing": "0.5",
                "hold_duration": "4",
                "animation_instruction": "Highlight phần quan trọng",
            }
        ]
    }

    segments = build_tts_segments_from_voiceover(payload)

    assert len(segments) == 1
    assert segments[0]["scene_name"] == "Scene A"
    assert segments[0]["pause_before"] == 0.5
    assert segments[0]["hold_duration"] == 4.0
    assert segments[0]["animation_instruction"] == "Highlight phần quan trọng"


def test_extract_timings_uses_scene_comment_for_following_statement(tmp_path: Path) -> None:
    source = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # [SCENE 1] scene_1_intro
        k_text = MathTex(r"1+1")
        self.play(Write(k_text))
"""
    path = tmp_path / "test_scene.py"
    path.write_text(source, encoding="utf-8")

    timings = extract_timings(str(path))

    assert timings["segments"][0]["scene_label"] == "[SCENE 1]"
    assert timings["segments"][0]["scene_id"] == "scene_1_intro"


def test_parse_float_takes_first_number_not_average() -> None:
    assert _parse_float("12") == 12.0
    assert _parse_float("1.0 (chậm hơn)") == 1.0
    assert _parse_float("4 giây") == 4.0
    assert _parse_float("0,5") == 0.5


def test_build_video_sync_manifest_scales_times_when_audio_longer(tmp_path: Path) -> None:
    audio_path = tmp_path / "combined.wav"
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(b"\x00\x00" * (10 * 8000))

    timings = {
        "total_duration": 5.0,
        "tts_blocks": [
            {"scene_label": "[SCENE 1]", "start_time": 0.0, "end_time": 5.0, "duration": 5.0}
        ],
        "segments": [{"scene_label": "[SCENE 1]", "duration": 5.0}],
    }
    tts_manifest = {
        "segments": [
            {"text": "Đây là đoạn đầu", "audio_file": "audio.wav", "stress_words": "đầu"}
        ],
        "combined_audio_file": str(audio_path),
    }

    manifest = build_video_sync_manifest(timings, tts_manifest, tmp_path)

    assert manifest["sync_items"][0]["start_time"] == 0.0
    assert manifest["sync_items"][0]["end_time"] == 10.0

    srt = (tmp_path / "subtitles.srt").read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:10,000" in srt
