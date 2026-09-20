import json
import os
import subprocess
import sys

import pytest

from conference_video_cutter.cli import main


def test_doctor_help_is_bilingual(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "doctor", "--help"])
    assert error.value.code == 0
    assert "провер" in capsys.readouterr().out.lower()


def test_new_review_commands_are_bilingual(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "записать хэш" in output
    assert "создать локальную html" in output


def test_module_entrypoint_honors_language_flag():
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-m", "conference_video_cutter", "--lang", "ru", "--help"],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0
    assert "записать хэш" in result.stdout.lower()


def test_all_command_help_is_russian(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "render", "--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "нарезать" in output
    assert "нарезать" in output


def test_init_writes_valid_json_for_quoted_source(tmp_path):
    source = tmp_path / 'talk "final".mp4'
    source.write_bytes(b"placeholder")
    project = tmp_path / "project.json"

    assert main(["--lang", "ru", "init", "--input", str(source), "--output", str(project)]) == 0

    data = json.loads(project.read_text(encoding="utf-8"))
    assert data["source"] == source.name
    assert data["copy_streams"] is True


def test_init_keeps_source_reachable_when_project_is_elsewhere(tmp_path):
    source_dir = tmp_path / "media"
    project_dir = tmp_path / "projects"
    source_dir.mkdir()
    project_dir.mkdir()
    source = source_dir / "conference.mp4"
    project = project_dir / "project.json"
    source.write_bytes(b"placeholder")

    assert main(["init", "--input", str(source), "--output", str(project)]) == 0

    data = json.loads(project.read_text(encoding="utf-8"))
    assert (project.parent / data["source"]).resolve() == source.resolve()


def test_init_refuses_to_overwrite_existing_project(tmp_path):
    source = tmp_path / "conference.mp4"
    project = tmp_path / "project.json"
    source.write_bytes(b"placeholder")
    project.write_text("keep", encoding="utf-8")

    assert main(["init", "--input", str(source), "--output", str(project)]) == 2
    assert project.read_text(encoding="utf-8") == "keep"


def test_transcript_refuses_to_overwrite_existing_output(tmp_path):
    source = tmp_path / "conference.mp4"
    transcript = tmp_path / "transcript.srt"
    project = tmp_path / "project.json"
    output = tmp_path / "transcript.md"
    source.write_bytes(b"placeholder")
    transcript.write_text("1\n00:00:00,000 --> 00:00:01,000\nText\n", encoding="utf-8")
    project.write_text(
        json.dumps({"source": source.name, "transcript": transcript.name, "output_dir": "output"}),
        encoding="utf-8",
    )
    output.write_text("keep", encoding="utf-8")

    assert main(["transcript", str(project), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "keep"


def test_review_reports_malformed_json_transcript_without_traceback(tmp_path, capsys):
    source = tmp_path / "conference.mp4"
    transcript = tmp_path / "transcript.json"
    project = tmp_path / "project.json"
    source.write_bytes(b"placeholder")
    transcript.write_text("{not-json", encoding="utf-8")
    project.write_text(
        json.dumps({"source": source.name, "transcript": transcript.name, "output_dir": "output"}),
        encoding="utf-8",
    )

    assert main(["review", str(project)]) == 2
    assert "error:" in capsys.readouterr().err


def test_render_reports_runtime_error_without_traceback(tmp_path, monkeypatch, capsys):
    project = tmp_path / "project.json"
    project.write_text(json.dumps({"source": "recording.mp4", "output_dir": "output"}), encoding="utf-8")
    monkeypatch.setattr("conference_video_cutter.cli.render_project", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sync gate")))

    assert main(["render", str(project)]) == 2
    assert "error: sync gate" in capsys.readouterr().err
