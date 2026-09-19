from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from .media import DURATION_TOLERANCE, build_cut_command, probe
from .models import Segment
from .timecode import parse_time


def cut_one(source: Path, start: str | int | float, end: str | int | float, output: Path, force: bool = False) -> dict[str, object]:
    source = source.resolve()
    output = output.resolve()
    start_seconds = parse_time(start)
    end_seconds = parse_time(end)
    if end_seconds <= start_seconds:
        raise ValueError("end must be greater than start")
    if not source.is_file():
        raise FileNotFoundError(f"source video not found: {source}")
    if source == output:
        raise ValueError("output must differ from source")
    if output.exists() and not force:
        raise FileExistsError(f"output already exists; use --force to replace it: {output}")

    source_info = probe(source)
    if end_seconds > source_info.duration:
        raise ValueError(f"end exceeds source duration {source_info.duration:.3f}s")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".cvc-cut-{uuid.uuid4().hex}.mp4"
    segment = Segment("cut", "cut", "other", start_seconds, end_seconds, "extra")
    try:
        subprocess.run(build_cut_command(source, segment, staging), check=True)
        info = probe(staging)
        if source_info.video_codec and not info.video_codec:
            raise RuntimeError("cut has no video stream after stream-copy; move start to a keyframe")
        if source_info.audio_codec and not info.audio_codec:
            raise RuntimeError("cut has no audio stream after stream-copy; move start to a keyframe")
        requested_duration = end_seconds - start_seconds
        duration_delta = info.duration - requested_duration
        warnings: list[str] = []
        if abs(duration_delta) > DURATION_TOLERANCE:
            warnings.append(
                f"duration drift {duration_delta:+.3f}s; move the boundary to a keyframe-aligned time; transcoding is disabled"
            )
        os.replace(staging, output)
        return {
            "source": source.name,
            "start": start_seconds,
            "end": end_seconds,
            "requested_duration": requested_duration,
            "observed_duration": info.duration,
            "duration_delta": duration_delta,
            "output": str(output),
            "size_bytes": output.stat().st_size,
            "media": asdict(info),
            "mode": "stream-copy",
            "warnings": warnings,
        }
    finally:
        staging.unlink(missing_ok=True)
