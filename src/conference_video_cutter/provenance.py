from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    if isinstance(data.get("format"), dict):
        data["format"].pop("filename", None)
    return data


def build_source_evidence(source: Path) -> dict[str, object]:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source video not found: {source}")
    return {
        "format": "cvc-source-evidence-v1",
        "source": source.name,
        "size_bytes": source.stat().st_size,
        "sha256": _sha256(source),
        "probe": _probe(source),
        "network_upload": False,
    }


def write_source_evidence(source: Path, output: Path) -> None:
    evidence = build_source_evidence(source)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, output)
