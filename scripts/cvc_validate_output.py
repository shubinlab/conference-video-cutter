#!/usr/bin/env python3
"""Verify CVC output files, hashes, and render warnings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(manifest_path: Path, strict: bool = False) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings = list(data.get("warnings", []))
    for clip in data.get("clips", []):
        file_name = clip.get("file")
        if not file_name:
            errors.append(f"clip {clip.get('id', '?')} has no file")
            continue
        target = (manifest_path.parent / str(file_name)).resolve()
        try:
            target.relative_to(manifest_path.parent.resolve())
        except ValueError:
            errors.append(f"clip {clip.get('id', '?')} escapes output directory")
            continue
        if not target.is_file():
            errors.append(f"missing output file: {file_name}")
            continue
        if target.stat().st_size == 0:
            errors.append(f"empty output file: {file_name}")
        expected = clip.get("sha256")
        if expected and sha256(target) != expected:
            errors.append(f"hash mismatch: {file_name}")
    if strict and warnings:
        errors.extend(f"render warning: {warning}" for warning in warnings)
    return {"format": "cvc-output-report-v1", "ok": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = validate(args.manifest, strict=args.strict)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"ok": False, "errors": [str(exc)], "warnings": []}
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("OK" if report.get("ok") else "FAILED")
        for error in report.get("errors", []):
            print(f"error: {error}")
        for warning in report.get("warnings", []):
            print(f"warning: {warning}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
