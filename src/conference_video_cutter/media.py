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


def ensure_decodable(path: Path, label: str) -> None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-map",
                "0:v?",
                "-map",
                "0:a?",
                "-c:v",
                "rawvideo",
                "-c:a",
                "pcm_s16le",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"{label} decode failed: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "ffmpeg returned a non-zero status"
        raise RuntimeError(f"{label} decode failed: {detail}")


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


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _recover_output_transaction(output_dir: Path) -> None:
    """Recover a directory swap interrupted between backup and publication."""
    parent = output_dir.parent
    backups = sorted(parent.glob(f".{output_dir.name}.cvc-backup-*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if output_dir.exists():
        for backup in backups:
            _remove_path(backup)
    elif backups:
        os.replace(backups[0], output_dir)
        for backup in backups[1:]:
            _remove_path(backup)
    for staging in parent.glob(f".{output_dir.name}.cvc-staging-*"):
        _remove_path(staging)


def _is_cvc_output(path: Path) -> bool:
    manifest = path / "manifest.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return data.get("mode") == "stream-copy" and isinstance(data.get("clips"), list)


def render_project(project: Project, accurate: bool = False, force: bool = False) -> dict[str, object]:
    if accurate:
        raise ValueError("transcoding is disabled: Conference Video Cutter always uses stream-copy")
    if not project.copy_streams:
        raise ValueError("copy_streams must be true: transcoding is disabled")
    if not project.source.is_file():
        raise FileNotFoundError(f"source video not found: {project.source}")
    protected = [project.source]
    if project.transcript is not None:
        protected.append(project.transcript)
    if project.project_path is not None:
        protected.append(project.project_path)
    output_resolved = project.output_dir.resolve()
    if any(output_resolved == path.resolve() or path.resolve().is_relative_to(output_resolved) for path in protected):
        raise ValueError("output directory must not contain or equal source, transcript, or project")
    _recover_output_transaction(project.output_dir)
    source_info = probe(project.source)
    errors = validate_project(project, source_info.duration)
    if errors:
        raise ValueError("invalid project:\n" + "\n".join(f"- {error}" for error in errors))
    if project.output_dir.exists() and not force:
        raise FileExistsError("output already exists; use --force to replace it: " + str(project.output_dir))
    if project.output_dir.exists() and force and project.output_dir.is_dir() and any(project.output_dir.iterdir()) and not _is_cvc_output(project.output_dir):
        raise FileExistsError("refusing to replace a non-CVC output directory with unrelated files: " + str(project.output_dir))
    project.output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = project.output_dir.parent / f".{project.output_dir.name}.cvc-staging-{uuid.uuid4().hex}"
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
            ensure_decodable(output, f"clip {segment.id}")
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
        backup: Path | None = None
        if project.output_dir.exists():
            backup = project.output_dir.parent / f".{project.output_dir.name}.cvc-backup-{uuid.uuid4().hex}"
            os.replace(project.output_dir, backup)
        try:
            os.replace(staging, project.output_dir)
        except BaseException:
            if backup is not None and not project.output_dir.exists():
                os.replace(backup, project.output_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
