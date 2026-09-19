from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run_tool(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_normalize_transcript_accepts_srt_and_emits_canonical_json(tmp_path: Path):
    source = tmp_path / "sample.srt"
    output = tmp_path / "transcript.json"
    source.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nЗдравствуйте, конференция.\n",
        encoding="utf-8",
    )

    result = run_tool("cvc_normalize_transcript.py", str(source), "--output", str(output))

    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["format"] == "cvc-transcript-v1"
    assert data["cues"][0]["text"] == "Здравствуйте, конференция."
    assert data["cues"][0]["start"] == 1.0


def test_normalize_transcript_keeps_zero_duration_cue_for_review(tmp_path: Path):
    source = tmp_path / "broken.srt"
    output = tmp_path / "transcript.json"
    source.write_text("1\n00:00:01,000 --> 00:00:01,000\nПроверить эту реплику.\n", encoding="utf-8")

    result = run_tool("cvc_normalize_transcript.py", str(source), "--output", str(output))

    assert result.returncode == 0, result.stderr
    cue = json.loads(output.read_text(encoding="utf-8"))["cues"][0]
    assert cue["start"] == cue["end"] == 1.0
    assert "warning" in cue


def test_preflight_reports_missing_transcript_provider_without_upload(tmp_path: Path):
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"not a real video")
    project = tmp_path / "project.json"
    project.write_text(
        json.dumps(
            {
                "source": source.name,
                "output_dir": "output",
                "transcript": None,
                "transcription": {"mode": "cloud", "provider": None},
            }
        ),
        encoding="utf-8",
    )

    result = run_tool("cvc_preflight.py", str(project), "--json")

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["checks"]["transcription"]["status"] == "action_required"
    assert report["network_upload"] is False


def test_preflight_does_not_create_output_directory(tmp_path: Path):
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"not a real video")
    output_dir = tmp_path / "not-created"
    project = tmp_path / "project.json"
    project.write_text(
        json.dumps(
            {
                "source": source.name,
                "output_dir": output_dir.name,
                "transcript": None,
                "transcription": {"mode": "cloud", "provider": "provider"},
            }
        ),
        encoding="utf-8",
    )

    run_tool("cvc_preflight.py", str(project), "--json")

    assert not output_dir.exists()


def test_validate_output_rejects_manifest_with_missing_file(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"clips": [{"id": "01", "file": "missing.mp4", "sha256": ""}], "warnings": []}),
        encoding="utf-8",
    )

    result = run_tool("cvc_validate_output.py", str(manifest), "--json")

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert any("missing" in error.lower() for error in report["errors"])
