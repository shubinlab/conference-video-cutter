#!/usr/bin/env python3
"""Run a no-upload safety and readiness check for a CVC project."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def resolve(value: Any, base: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else (base / path).resolve()


def check_project(path: Path) -> dict[str, Any]:
    base = path.resolve().parent
    data = json.loads(path.read_text(encoding="utf-8"))
    source = resolve(data.get("source"), base)
    transcript = resolve(data.get("transcript"), base)
    output_dir = resolve(data.get("output_dir", "output"), base)
    transcription = data.get("transcription") or {}
    provider = transcription.get("provider")
    checks: dict[str, Any] = {}
    errors: list[str] = []

    if source and source.is_file():
        source_check: dict[str, Any] = {"status": "ok", "path": source.name, "size_bytes": source.stat().st_size}
        if shutil.which("ffprobe"):
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if probe.returncode != 0:
                source_check["status"] = "error"
                source_check["message"] = "ffprobe could not read the media"
                errors.append("source media failed ffprobe validation")
            else:
                try:
                    source_check["duration_seconds"] = float(probe.stdout.strip())
                except ValueError:
                    source_check["status"] = "error"
                    source_check["message"] = "ffprobe returned no usable duration"
                    errors.append("source media has no usable duration")
        checks["source"] = source_check
    else:
        checks["source"] = {"status": "error", "path": str(source) if source else None}
        errors.append("source video is missing")

    if transcript and transcript.is_file():
        checks["transcript"] = {"status": "ok", "path": transcript.name}
    elif provider:
        checks["transcription"] = {"status": "configured", "provider": str(provider), "mode": transcription.get("mode", "cloud")}
    else:
        checks["transcription"] = {
            "status": "action_required",
            "message": "import a transcript or configure an explicit provider",
        }
        errors.append("transcript or transcription provider is required")

    checks["ffmpeg"] = {"status": "ok" if shutil.which("ffmpeg") else "missing"}
    checks["ffprobe"] = {"status": "ok" if shutil.which("ffprobe") else "missing"}
    if checks["ffmpeg"]["status"] == "missing" or checks["ffprobe"]["status"] == "missing":
        errors.append("ffmpeg and ffprobe are required for media verification")

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(output_dir)
        checks["storage"] = {"status": "ok", "free_bytes": usage.free, "path": str(output_dir)}

    return {
        "format": "cvc-preflight-v1",
        "project": str(path.resolve()),
        "checks": checks,
        "errors": errors,
        "network_upload": False,
        "privacy": "No network request is made by this tool.",
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        report = check_project(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"ok": False, "errors": [str(exc)], "checks": {}, "network_upload": False}
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("OK" if report.get("ok") else "ACTION REQUIRED")
        for name, check in report.get("checks", {}).items():
            print(f"{name}: {check.get('status', 'unknown')}")
        for error in report.get("errors", []):
            print(f"error: {error}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
