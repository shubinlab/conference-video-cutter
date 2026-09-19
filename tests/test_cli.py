import json

import pytest

from conference_video_cutter.cli import main


def test_doctor_help_is_bilingual(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "doctor", "--help"])
    assert error.value.code == 0
    assert "провер" in capsys.readouterr().out.lower()


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
