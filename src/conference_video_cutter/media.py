from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Project, Segment
from .plan import validate_project

DURATION_TOLERANCE = 0.05
SYNC_TOLERANCE = 0.05


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    video_codec: str | None
    audio_codec: str | None
    width: int | None = None
    height: int | None = None
    video_start: float | None = None
    audio_start: float | None = None
    video_duration: float | None = None
    audio_duration: float | None = None


def _seconds(value: float) -> str:
    return f"{value:.3f}"


def build_cut_command(source: Path, segment: Segment, output: Path, accurate: bool = False) -> list[str]:
    if accurate:
        raise ValueError("transcoding is disabled: Conference Video Cutter always uses stream-copy")
    duration = segment.end - segment.start
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(source),
        "-ss",
        _seconds(segment.start),
        "-t",
        _seconds(duration),
        "-map",
        "0",
    ]
    command += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    return command + [str(output)]


def probe(path: Path) -> MediaInfo:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,start_time,duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})

    def optional_float(stream: dict[str, object], key: str) -> float | None:
        value = stream.get(key)
        return float(value) if value not in (None, "N/A") else None

    return MediaInfo(
        duration=float(data["format"]["duration"]),
        video_codec=video.get("codec_name"),
        audio_codec=audio.get("codec_name"),
        width=video.get("width"),
        height=video.get("height"),
        video_start=optional_float(video, "start_time"),
        audio_start=optional_float(audio, "start_time"),
        video_duration=optional_float(video, "duration"),
        audio_duration=optional_float(audio, "duration"),
    )


def ensure_streams_start_together(info: MediaInfo, label: str) -> None:
    if info.video_start is None or info.audio_start is None:
        return
    delta = info.video_start - info.audio_start
    if abs(delta) > SYNC_TOLERANCE:
        raise RuntimeError(
            f"{label} audio/video start mismatch {delta:+.3f}s after stream-copy; "
            "move the start to a decodable video keyframe or use transcoding"
        )


def _safe_filename(value: str) -> str:
    cleaned = "".join("-" if char in '\\/:*?"<>|' else char for char in value).strip(" .")
    return cleaned or "segment"


def _output_name(project: Project, segment: Segment) -> str:
    if segment.filename:
        return _safe_filename(segment.filename)
    speaker = project.speakers.get(segment.speaker_id) if segment.speaker_id else None
    name = speaker.name_ru if project.language == "ru" and speaker and speaker.name_ru else speaker.name if speaker else ""
    prefix = segment.id if segment.role == "speaker" else f"00 — {segment.id}"
    return _safe_filename(" — ".join(part for part in (prefix, segment.title, name) if part) + ".mp4")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_project(project: Project, accurate: bool = False, force: bool = False) -> dict[str, object]:
    if accurate:
        raise ValueError("transcoding is disabled: Conference Video Cutter always uses stream-copy")
    if not project.copy_streams:
        raise ValueError("copy_streams must be true: transcoding is disabled")
    if not project.source.is_file():
        raise FileNotFoundError(f"source video not found: {project.source}")
    source_info = probe(project.source)
    errors = validate_project(project, source_info.duration)
    if errors:
        raise ValueError("invalid project:\n" + "\n".join(f"- {error}" for error in errors))
    project.output_dir.mkdir(parents=True, exist_ok=True)
    if not force:
        existing = [project.output_dir / _output_name(project, segment) for segment in project.segments]
        existing = [path for path in existing if path.exists()]
        if (project.output_dir / "manifest.json").exists():
            existing.append(project.output_dir / "manifest.json")
        if existing:
            raise FileExistsError(
                "output already exists; use --force to replace it: "
                + ", ".join(path.name for path in existing[:5])
            )
    staging = project.output_dir / f".cvc-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    entries: list[dict[str, object]] = []
    manifest_warnings: list[dict[str, str]] = []
    try:
        for segment in project.segments:
            output = staging / _output_name(project, segment)
            command = build_cut_command(project.source, segment, output, accurate=accurate)
            subprocess.run(command, check=True)
            info = probe(output)
            ensure_streams_start_together(info, f"clip {segment.id}")
            if source_info.video_codec and not info.video_codec:
                raise RuntimeError(
                    f"clip {segment.id} has no video stream after stream-copy; "
                    "move the boundary to a keyframe-aligned start time"
                )
            if source_info.audio_codec and not info.audio_codec:
                raise RuntimeError(
                    f"clip {segment.id} has no audio stream after stream-copy; "
                    "move the boundary to a keyframe-aligned start time"
                )
            requested_duration = segment.end - segment.start
            duration_delta = info.duration - requested_duration
            warnings: list[str] = []
            if abs(duration_delta) > DURATION_TOLERANCE:
                advice = "move the boundary to a keyframe-aligned time; transcoding is disabled"
                warnings.append(f"duration drift {duration_delta:+.3f}s; {advice}")
                manifest_warnings.append({"id": segment.id, "message": warnings[-1]})
            entries.append(
                {
                    "id": segment.id,
                    "title": segment.title,
                    "kind": segment.kind,
                    "role": segment.role,
                    "source_start": segment.start,
                    "source_end": segment.end,
                    "requested_duration": requested_duration,
                    "observed_duration": info.duration,
                    "duration_delta": duration_delta,
                    "file": output.name,
                    "size_bytes": output.stat().st_size,
                    "sha256": _sha256(output),
                    "media": asdict(info),
                    "mode": "stream-copy",
                    "warnings": warnings,
                }
            )
        manifest = {
            "source": project.source.name,
            "source_duration": source_info.duration,
            "mode": "stream-copy",
            "clips": entries,
            "warnings": manifest_warnings,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for entry in entries:
            staged_file = staging / str(entry["file"])
            final_file = project.output_dir / staged_file.name
            if final_file.exists() and not force:
                raise FileExistsError(f"output appeared during render: {final_file}")
            os.replace(staged_file, final_file)
        os.replace(manifest_path, project.output_dir / "manifest.json")
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
