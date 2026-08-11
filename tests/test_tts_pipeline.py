from pathlib import Path

from generators.tts_engine import build_tts_segments_from_voiceover
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
