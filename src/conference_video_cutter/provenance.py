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
    raw = json.loads(result.stdout)
    format_keys = {"format_name", "format_long_name", "start_time", "duration", "size", "bit_rate", "nb_streams", "nb_programs"}
    stream_keys = {
        "index",
        "codec_type",
        "codec_name",
        "profile",
        "width",
        "height",
        "pix_fmt",
        "level",
        "r_frame_rate",
        "avg_frame_rate",
        "time_base",
        "start_time",
        "duration",
        "bit_rate",
        "channels",
        "channel_layout",
        "sample_rate",
        "disposition",
    }
    format_data = raw.get("format") if isinstance(raw.get("format"), dict) else {}
    streams = raw.get("streams") if isinstance(raw.get("streams"), list) else []
    return {
        "format": {key: format_data[key] for key in format_keys if key in format_data},
        "streams": [{key: stream[key] for key in stream_keys if key in stream} for stream in streams if isinstance(stream, dict)],
        "chapters_count": len(raw.get("chapters", [])) if isinstance(raw.get("chapters"), list) else 0,
    }


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


def write_source_evidence(source: Path, output: Path, force: bool = False) -> None:
    source = source.resolve()
    output = output.resolve()
    if output == source:
        raise ValueError("evidence output must differ from source")
    if output.exists() and not force:
        raise FileExistsError(f"output already exists; use --force to replace it: {output}")
    evidence = build_source_evidence(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
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
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
