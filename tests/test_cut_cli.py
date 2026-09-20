import json
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from conference_video_cutter.cut_cli import main
from conference_video_cutter.cut import cut_one, snap_one
from conference_video_cutter.media import ensure_decodable


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


def _gop_source(tmp_path: Path) -> Path:
    source = tmp_path / "gop-source.mp4"
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
            "3",
            "-c:v",
            "libx264",
            "-g",
            "10",
            "-keyint_min",
            "10",
            "-sc_threshold",
            "0",
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
    assert "snap" in output
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


def test_cut_repairs_unsynchronized_stream_copy_boundary(tmp_path: Path):
    source = _gop_source(tmp_path)

    output = tmp_path / "repaired.mp4"
    result = cut_one(source, "0.2", "1.2", output)

    assert result["mode"] == "stream-copy"
    assert result["sync_adjusted"] is True
    assert output.is_file()


def test_decode_check_rejects_corrupt_media(tmp_path: Path):
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a media file")

    with pytest.raises(RuntimeError, match="decode failed"):
        ensure_decodable(corrupt, "corrupt test output")


def test_snap_reports_requires_transcode_when_no_nearby_keyframe(tmp_path: Path):
    source = _gop_source(tmp_path)

    result = snap_one(source, "0.8", "1.8", tmp_path / "snap.mp4", window=0.1)

    assert result["status"] == "requires-transcode"
    assert not (tmp_path / "snap.mp4").exists()


def test_snap_writes_verified_stream_copy_from_safe_boundary(tmp_path: Path):
    source = _source(tmp_path)

    result = snap_one(source, "0.23", "1.23", tmp_path / "snap.mp4", window=0.25)

    assert result["status"] == "snapped"
    assert result["mode"] == "stream-copy"
    assert result["snapped_start"] == 0.2
    assert (tmp_path / "snap.mp4").is_file()


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
