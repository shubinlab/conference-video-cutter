from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path

from .media import DURATION_TOLERANCE, cut_and_probe, ensure_decodable, probe
from .models import Segment
from .timecode import parse_time


def _keyframes(source: Path, low: float, high: float) -> list[float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-skip_frame",
            "nokey",
            "-read_intervals",
            f"{max(0.0, low):.6f}%{high:.6f}",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values: set[float] = set()
    for line in result.stdout.splitlines():
        try:
            value = float(line.strip())
        except ValueError:
            continue
        if low <= value <= high:
            values.add(value)
    return sorted(values)


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
        info, sync_adjusted = cut_and_probe(source, segment, staging)
        if source_info.video_codec and not info.video_codec:
            raise RuntimeError("cut has no video stream after stream-copy; move start to a keyframe")
        if source_info.audio_codec and not info.audio_codec:
            raise RuntimeError("cut has no audio stream after stream-copy; move start to a keyframe")
        ensure_decodable(staging, "cut")
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
            "sync_adjusted": sync_adjusted,
            "warnings": warnings,
        }
    finally:
        staging.unlink(missing_ok=True)


def snap_one(
    source: Path,
    start: str | int | float,
    end: str | int | float,
    output: Path,
    window: float = 0.25,
    force: bool = False,
) -> dict[str, object]:
    source = source.resolve()
    output = output.resolve()
    requested_start = parse_time(start)
    requested_end = parse_time(end)
    if window < 0:
        raise ValueError("window must be non-negative")
    if requested_end <= requested_start:
        raise ValueError("end must be greater than start")
    if not source.is_file():
        raise FileNotFoundError(f"source video not found: {source}")
    if source == output:
        raise ValueError("output must differ from source")
    if output.exists() and not force:
        raise FileExistsError(f"output already exists; use --force to replace it: {output}")

    source_info = probe(source)
    if requested_end > source_info.duration:
        raise ValueError(f"end exceeds source duration {source_info.duration:.3f}s")
    starts = _keyframes(source, requested_start - window, requested_start + window)
    ends = [requested_end, *_keyframes(source, requested_end - window, requested_end + window)]
    starts = sorted(set(starts), key=lambda value: abs(value - requested_start))
    ends = sorted(set(ends), key=lambda value: abs(value - requested_end))
    if not starts:
        return {
            "status": "requires-transcode",
            "mode": "stream-copy",
            "reason": "no video keyframe is available inside the boundary window",
            "requested_start": requested_start,
            "requested_end": requested_end,
            "window": window,
            "candidates_tested": 0,
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    best: tuple[tuple[float, float, float], dict[str, object], Path] | None = None
    tested = 0
    with tempfile.TemporaryDirectory(prefix=".cvc-snap-", dir=output.parent) as temporary:
        temporary_dir = Path(temporary)
        for candidate_start in starts:
            for candidate_end in ends:
                if candidate_end <= candidate_start:
                    continue
                tested += 1
                candidate = temporary_dir / f"candidate-{tested}.mp4"
                try:
                    result = cut_one(source, candidate_start, candidate_end, candidate)
                except (OSError, RuntimeError, ValueError):
                    continue
                if abs(float(result["duration_delta"])) > DURATION_TOLERANCE:
                    continue
                score = (
                    abs(candidate_start - requested_start) + abs(candidate_end - requested_end),
                    abs(float(result["duration_delta"])),
                    abs(candidate_start - requested_start),
                )
                if best is None or score < best[0]:
                    best = (score, result, candidate)
            if best is not None and best[0][0] == 0:
                break
        if best is None:
            return {
                "status": "requires-transcode",
                "mode": "stream-copy",
                "reason": "no candidate passed stream synchronization and duration checks",
                "requested_start": requested_start,
                "requested_end": requested_end,
                "window": window,
                "candidates_tested": tested,
            }
        _, result, candidate = best
        os.replace(candidate, output)
        result.update(
            {
                "status": "snapped",
                "output": str(output),
                "requested_start": requested_start,
                "requested_end": requested_end,
                "snapped_start": result["start"],
                "snapped_end": result["end"],
                "shift_start": float(result["start"]) - requested_start,
                "shift_end": float(result["end"]) - requested_end,
                "window": window,
                "candidates_tested": tested,
            }
        )
        return result
