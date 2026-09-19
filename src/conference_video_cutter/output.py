from __future__ import annotations

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


def validate_manifest(manifest_path: Path, strict: bool = False) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings = list(data.get("warnings", []))
    root = manifest_path.parent.resolve()
    for clip in data.get("clips", []):
        file_name = clip.get("file")
        if not file_name:
            errors.append(f"clip {clip.get('id', '?')} has no file")
            continue
        target = (manifest_path.parent / str(file_name)).resolve()
        try:
            target.relative_to(root)
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
