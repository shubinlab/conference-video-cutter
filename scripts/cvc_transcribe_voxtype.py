#!/usr/bin/env python3
"""Transcribe media through the local Voxtype -> Lemonade -> NPU path."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from conference_video_cutter.voxtype import (
        VoxtypeConfig,
        load_completed_chunks,
        merge_overlap,
        plan_chunks,
        read_voxtype_config,
        render_transcript_markdown,
        require_local_endpoint,
        require_npu_health,
    )
except ModuleNotFoundError:  # pragma: no cover - direct checkout execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from conference_video_cutter.voxtype import (
        VoxtypeConfig,
        load_completed_chunks,
        merge_overlap,
        plan_chunks,
        read_voxtype_config,
        render_transcript_markdown,
        require_local_endpoint,
        require_npu_health,
    )


def _json_request(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = getattr(exc, "read", lambda: b"")()
        suffix = f": {detail.decode('utf-8', errors='replace')[:400]}" if detail else ""
        raise RuntimeError(f"Voxtype endpoint request failed: {exc}{suffix}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Voxtype endpoint returned invalid JSON: {payload[:400]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Voxtype endpoint returned a non-object JSON response")
    return data


def _multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----cvc-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: audio/wav\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _duration(source: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned no usable duration for {source}") from exc


def _audio_chunk(source: Path, request_start: float, request_duration: float) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{request_start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{request_duration:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    return result.stdout


def _transcribe_audio(endpoint: str, model: str, language: str, audio: bytes, timeout: float, retries: int = 3) -> str:
    body, content_type = _multipart(
        {"model": model, "language": language, "response_format": "json"},
        "audio.wav",
        audio,
    )
    for attempt in range(retries + 1):
        try:
            response = _json_request(
                endpoint.rstrip("/") + "/api/v1/audio/transcriptions",
                method="POST",
                body=body,
                headers={"Content-Type": content_type},
                timeout=timeout,
            )
            break
        except RuntimeError as exc:
            if attempt >= retries:
                raise
            if "model_not_loaded" in str(exc) or "No model loaded" in str(exc):
                print("model was evicted; reloading the requested NPU model", file=sys.stderr, flush=True)
                _ensure_npu(endpoint, model, timeout, force_load=True)
            delay = min(2**attempt, 10)
            print(f"transcription request failed; retrying in {delay}s ({attempt + 1}/{retries})", file=sys.stderr, flush=True)
            time.sleep(delay)
    if "error" in response:
        raise RuntimeError(f"Voxtype transcription error: {response['error']}")
    text = response.get("text")
    if text is None:
        raise RuntimeError(f"Voxtype transcription response has no text: {response}")
    return str(text).strip()


def _ensure_npu(endpoint: str, model: str, timeout: float, *, force_load: bool = False) -> tuple[dict[str, Any], dict[str, object]]:
    """Load a lazily registered model, then require a ready NPU backend."""
    health_url = endpoint.rstrip("/") + "/v1/health"
    health = _json_request(health_url, timeout=timeout)
    loaded = health.get("all_models_loaded")
    try:
        backend = require_npu_health(health, model)
        return health, backend
    except RuntimeError:
        matching_loaded = any(
            isinstance(item, dict) and item.get("model_name") == model
            for item in loaded
        ) if isinstance(loaded, list) else False
        if not isinstance(loaded, list) or (matching_loaded and not force_load):
            raise

    load_response = _json_request(
        endpoint.rstrip("/") + "/v1/load",
        method="POST",
        body=json.dumps({"model_name": model, "pinned": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    if load_response.get("status") == "error":
        raise RuntimeError(f"Voxtype/Lemonade model load failed: {load_response}")
    health = _json_request(health_url, timeout=timeout)
    backend = require_npu_health(health, model)
    return health, backend


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def transcribe(source: Path, output_dir: Path, config: VoxtypeConfig, *, chunk_seconds: float, overlap_seconds: float, timeout: float, retries: int = 3, force: bool, allow_remote: bool) -> dict[str, Any]:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source media not found: {source}")
    require_local_endpoint(config.endpoint, allow_remote=allow_remote)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / "chunks.jsonl"
    transcript_path = output_dir / "transcript.json"
    markdown_path = output_dir / "transcript.md"
    provenance_path = output_dir / "provenance.json"
    if force:
        for path in (chunks_path, transcript_path, markdown_path, provenance_path):
            path.unlink(missing_ok=True)
    elif transcript_path.exists() or markdown_path.exists():
        raise FileExistsError(f"transcript output already exists; use --force to replace it: {output_dir}")

    health, backend = _ensure_npu(config.endpoint, config.model, timeout)
    duration = _duration(source)
    chunks = plan_chunks(duration, chunk_seconds, overlap_seconds)
    completed = load_completed_chunks(chunks_path)
    for chunk in chunks:
        if chunk.index in completed:
            continue
        audio = _audio_chunk(source, chunk.request_start, chunk.request_duration)
        text = _transcribe_audio(config.endpoint, config.model, config.language, audio, timeout, retries)
        record = {
            "index": chunk.index,
            "start": chunk.start,
            "end": chunk.end,
            "request_start": chunk.request_start,
            "request_end": chunk.request_start + chunk.request_duration,
            "text": text,
        }
        with chunks_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        completed[chunk.index] = record
        print(f"chunk {chunk.index + 1}/{len(chunks)} {chunk.start:.1f}-{chunk.end:.1f}s", file=sys.stderr, flush=True)

    ordered = [completed[chunk.index] for chunk in chunks]
    cues: list[dict[str, Any]] = []
    previous_raw = ""
    for item in ordered:
        raw_text = str(item.get("text", "")).strip()
        text = merge_overlap(previous_raw, raw_text) if previous_raw and raw_text else raw_text
        previous_raw = raw_text or previous_raw
        if text:
            cues.append({"start": float(item["start"]), "end": float(item["end"]), "text": text})
    document = {
        "format": "cvc-transcript-v1",
        "source": source.name,
        "language": config.language,
        "provider": "voxtype-npu",
        "model": config.model,
        "device": backend.get("device"),
        "timestamp_quality": "chunk-boundary",
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "duration": duration,
        "cues": cues,
    }
    _write_atomic(transcript_path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    _write_atomic(markdown_path, render_transcript_markdown(source.name, config.model, str(backend.get("device")), cues))
    _write_atomic(
        provenance_path,
        json.dumps(
            {
                "source": source.name,
                "source_sha256": _sha256(source),
                "endpoint": config.endpoint,
                "model": config.model,
                "device": backend.get("device"),
                "health": health,
                "chunk_count": len(chunks),
                "completed_count": len(completed),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return {"duration": duration, "chunks": len(chunks), "cues": len(cues), "device": backend.get("device"), "output_dir": str(output_dir)}


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("~/.config/voxtype/config.toml").expanduser())
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--language")
    parser.add_argument("--chunk-seconds", type=float, default=120.0)
    parser.add_argument("--overlap-seconds", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--retries", type=int, default=3, help="retries for a failed transcription request")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = read_voxtype_config(args.config)
        config = VoxtypeConfig(args.endpoint or config.endpoint, args.model or config.model, args.language or config.language)
        result = transcribe(
            args.source,
            args.output_dir,
            config,
            chunk_seconds=args.chunk_seconds,
            overlap_seconds=args.overlap_seconds,
            timeout=args.timeout,
            retries=max(0, args.retries),
            force=args.force,
            allow_remote=args.allow_remote,
        )
    except KeyboardInterrupt:
        print("interrupted; completed chunks are safe to resume", file=sys.stderr)
        return 130
    except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
