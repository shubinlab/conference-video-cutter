from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conference_video_cutter.provenance import build_source_evidence
from conference_video_cutter.cli import main


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "recording.mp4"
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
            "testsrc=size=320x180:rate=5",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-g",
            "1",
            str(source),
        ],
        check=True,
    )
    return source


def test_build_source_evidence_has_hash_and_redacted_probe(tmp_path: Path):
    source = _source(tmp_path)

    evidence = build_source_evidence(source)

    assert evidence["source"] == source.name
    assert evidence["size_bytes"] == source.stat().st_size
    assert len(evidence["sha256"]) == 64
    assert evidence["probe"]["streams"][0]["codec_name"] == "h264"
    assert str(source) not in json.dumps(evidence)


def test_evidence_cli_writes_json_without_absolute_path(tmp_path: Path, capsys):
    source = _source(tmp_path)
    project = tmp_path / "project.json"
    output = tmp_path / "evidence.json"
    project.write_text(json.dumps({"source": source.name}), encoding="utf-8")

    assert main(["evidence", str(project), "--output", str(output)]) == 0

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["source"] == source.name
    assert str(source) not in output.read_text(encoding="utf-8")
    assert str(output) in capsys.readouterr().out
