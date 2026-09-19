import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conference_video_cutter.cli import main
from conference_video_cutter.media import MediaInfo, probe, render_project
from conference_video_cutter.plan import load_project


ROOT = Path(__file__).parents[1]


def test_demo_project_validates_without_media(capsys):
    assert main(["validate", str(ROOT / "examples/demo/project.json")]) == 0
    assert "valid" in capsys.readouterr().out.lower()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required")
def test_demo_project_renders_and_writes_manifest(tmp_path: Path):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-g",
            "1",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    project_path = tmp_path / "project.json"
    project_path.write_text(
        json.dumps(
            {
                "language": "en",
                "source": source.name,
                "output_dir": "output",
                "speakers": {"spk-01": {"name": "Example Speaker"}},
                "segments": [
                    {
                        "id": "01",
                        "speaker_id": "spk-01",
                        "title": "Talk",
                        "kind": "main_talk",
                        "start": 0.2,
                        "end": 1.2,
                        "role": "speaker",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = render_project(load_project(project_path))

    output = tmp_path / "output" / "01 — Talk — Example Speaker.mp4"
    assert output.is_file() and output.stat().st_size > 0
    assert manifest["mode"] == "stream-copy"
    assert manifest["clips"][0]["file"] == output.name
    assert manifest["clips"][0]["size_bytes"] == output.stat().st_size
    assert "duration_delta" in manifest["clips"][0]
    assert "warnings" in manifest["clips"][0]
    assert manifest["warnings"] == []
    assert probe(output).video_codec == "h264"
    assert (tmp_path / "output" / "manifest.json").is_file()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is required")
def test_render_does_not_publish_partial_directory_when_swap_fails(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-g",
            "1",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    project_path = tmp_path / "project.json"
    project_path.write_text(
        json.dumps(
            {
                "language": "en",
                "source": source.name,
                "output_dir": "output",
                "speakers": {"spk-01": {"name": "Example Speaker"}},
                "segments": [
                    {
                        "id": "01",
                        "speaker_id": "spk-01",
                        "title": "Talk",
                        "kind": "main_talk",
                        "start": 0.2,
                        "end": 1.2,
                        "role": "speaker",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    original_replace = __import__("os").replace

    def fail_final_swap(source_path, destination):
        if Path(destination) == output_dir:
            raise OSError("publish failed")
        return original_replace(source_path, destination)

    monkeypatch.setattr("conference_video_cutter.media.os.replace", fail_final_swap)

    with pytest.raises(OSError, match="publish failed"):
        render_project(load_project(project_path))

    assert not output_dir.exists()
    assert not list(tmp_path.glob(".output.*"))


def test_render_refuses_existing_empty_output_without_force(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"placeholder")
    project_path = tmp_path / "project.json"
    project_path.write_text(
        json.dumps({"source": source.name, "output_dir": "output", "segments": []}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(
        "conference_video_cutter.media.probe",
        lambda path: MediaInfo(duration=2.0, video_codec="h264", audio_codec="aac"),
    )

    with pytest.raises(FileExistsError, match="--force"):
        render_project(load_project(project_path))
