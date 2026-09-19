import json
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from conference_video_cutter.cut_cli import main


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg is required",
)


def _source(tmp_path: Path) -> Path:
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
    return source


def test_cut_cli_has_stream_copy_commands(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "probe" in output
    assert "cut" in output
    assert "batch" in output


def test_cut_cli_help_is_russian(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "--help"])
    assert error.value.code == 0
    assert "нарезка" in capsys.readouterr().out.lower()


def test_cut_cli_cuts_one_file_without_transcoding(tmp_path: Path, capsys):
    source = _source(tmp_path)
    output = tmp_path / "clip.mp4"

    assert main(
        [
            "cut",
            "--input",
            str(source),
            "--start",
            "0.2",
            "--end",
            "1.2",
            "--output",
            str(output),
            "--json",
        ]
    ) == 0

    result = json.loads(capsys.readouterr().out)
    assert output.is_file() and output.stat().st_size > 0
    assert result["mode"] == "stream-copy"
    assert result["media"]["video_codec"] == "h264"
    assert result["media"]["audio_codec"] == "aac"


def test_cut_cli_refuses_overwrite_without_force(tmp_path: Path, capsys):
    source = _source(tmp_path)
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"keep me")

    assert main(
        [
            "cut",
            "--input",
            str(source),
            "--start",
            "0",
            "--end",
            "1",
            "--output",
            str(output),
        ]
    ) == 2

    assert output.read_bytes() == b"keep me"
    assert "already exists" in capsys.readouterr().err


def test_cut_cli_verifies_manifest(tmp_path: Path, capsys):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "id": "01",
                        "file": clip.name,
                        "sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
                    }
                ],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(manifest), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
