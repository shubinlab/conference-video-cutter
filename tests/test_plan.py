import json

import pytest

from conference_video_cutter.plan import load_project, validate_project


def project_file(tmp_path, segments):
    path = tmp_path / "project.json"
    path.write_text(
        json.dumps(
            {
                "language": "ru",
                "source": "recording.mp4",
                "transcript": "transcript.srt",
                "output_dir": "output",
                "speakers": {"spk-01": {"name": "Alex Example", "name_ru": "Алексей Пример"}},
                "segments": segments,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def segment(segment_id, start, end, **extra):
    return {"id": segment_id, "speaker_id": "spk-01", "title": "Talk", "kind": "main_talk", "start": start, "end": end, "role": "speaker", **extra}


def test_load_project_preserves_russian_speaker_name(tmp_path):
    project = load_project(project_file(tmp_path, [segment("01", 0, 10)]))
    assert project.language == "ru"
    assert project.speakers["spk-01"].name_ru == "Алексей Пример"


def test_validate_rejects_overlapping_segments(tmp_path):
    project = load_project(project_file(tmp_path, [segment("01", 0, 10), segment("02", 9, 20)]))
    errors = validate_project(project)
    assert any("overlap" in error.lower() for error in errors)


def test_validate_rejects_speaker_segment_without_speaker(tmp_path):
    project = load_project(project_file(tmp_path, [{"id": "01", "title": "Talk", "kind": "main_talk", "start": 0, "end": 10, "role": "speaker"}]))
    errors = validate_project(project)
    assert any("speaker" in error.lower() for error in errors)


def test_validate_rejects_segment_outside_duration(tmp_path):
    project = load_project(project_file(tmp_path, [segment("01", 0, 11)]))
    errors = validate_project(project, duration=10)
    assert any("duration" in error.lower() for error in errors)
