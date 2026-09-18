from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Project, Segment
from .plan import validate_project


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    video_codec: str | None
    audio_codec: str | None
    width: int | None = None
    height: int | None = None


def _seconds(value: float) -> str:
    return f"{value:.3f}"


def build_cut_command(source: Path, segment: Segment, output: Path, accurate: bool = False) -> list[str]:
    duration = segment.end - segment.start
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ss",
        _seconds(segment.start),
        "-t",
        _seconds(duration),
        "-map",
        "0",
    ]
    if accurate:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k"]
    else:
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
            "stream=codec_type,codec_name,width,height",
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
    return MediaInfo(
        duration=float(data["format"]["duration"]),
        video_codec=video.get("codec_name"),
        audio_codec=audio.get("codec_name"),
        width=video.get("width"),
        height=video.get("height"),
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


def render_project(project: Project, accurate: bool = False) -> dict[str, object]:
    if not project.source.is_file():
        raise FileNotFoundError(f"source video not found: {project.source}")
    source_info = probe(project.source)
    errors = validate_project(project, source_info.duration)
    if errors:
        raise ValueError("invalid project:\n" + "\n".join(f"- {error}" for error in errors))
    project.output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for segment in project.segments:
        output = project.output_dir / _output_name(project, segment)
        command = build_cut_command(project.source, segment, output, accurate=accurate)
        subprocess.run(command, check=True)
        info = probe(output)
        if source_info.video_codec and not info.video_codec:
            raise RuntimeError(
                f"clip {segment.id} has no video stream after stream-copy; "
                "use --accurate or choose a keyframe-aligned start time"
            )
        if source_info.audio_codec and not info.audio_codec:
            raise RuntimeError(
                f"clip {segment.id} has no audio stream after stream-copy; "
                "use --accurate or choose a keyframe-aligned start time"
            )
        entries.append(
            {
                "id": segment.id,
                "title": segment.title,
                "kind": segment.kind,
                "role": segment.role,
                "source_start": segment.start,
                "source_end": segment.end,
                "requested_duration": segment.end - segment.start,
                "observed_duration": info.duration,
                "file": output.name,
                "sha256": _sha256(output),
                "media": asdict(info),
                "mode": "accurate" if accurate else "stream-copy",
            }
        )
    manifest = {"source": str(project.source), "mode": "accurate" if accurate else "stream-copy", "clips": entries}
    (project.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
