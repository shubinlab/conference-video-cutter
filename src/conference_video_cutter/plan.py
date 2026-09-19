from __future__ import annotations

import json
from pathlib import Path

from .models import Project, Segment, Speaker
from .timecode import parse_time

KINDS = {"opening", "speaker_intro", "main_talk", "qa", "host_transition", "technical_prep", "closing", "other"}
ROLES = {"speaker", "extra"}


def _path(value: str | None, base: Path) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_project(path: Path) -> Project:
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    speakers = {
        speaker_id: Speaker(
            name=str(value.get("name", speaker_id)),
            name_ru=value.get("name_ru"),
            topic=value.get("topic"),
        )
        for speaker_id, value in data.get("speakers", {}).items()
    }
    segments = tuple(
        Segment(
            id=str(value["id"]),
            title=str(value.get("title", value["id"])),
            kind=str(value.get("kind", "other")),
            start=parse_time(value["start"]),
            end=parse_time(value["end"]),
            role=str(value.get("role", "extra")),
            speaker_id=value.get("speaker_id"),
            filename=value.get("filename"),
        )
        for value in data.get("segments", [])
    )
    return Project(
        language=str(data.get("language", "en")),
        source=_path(str(data["source"]), base),
        transcript=_path(data.get("transcript"), base),
        output_dir=_path(str(data.get("output_dir", "output")), base),
        speakers=speakers,
        segments=segments,
        copy_streams=bool(data.get("copy_streams", True)),
        complete_coverage=bool(data.get("complete_coverage", False)),
        project_path=path,
    )


def validate_project(project: Project, duration: float | None = None) -> list[str]:
    errors: list[str] = []
    if project.language not in {"en", "ru"}:
        errors.append(f"language must be en or ru, got {project.language!r}")
    if not project.source:
        errors.append("source is required")
    ids: set[str] = set()
    ordered: list[Segment] = []
    for segment in project.segments:
        if segment.id in ids:
            errors.append(f"duplicate segment id: {segment.id}")
        ids.add(segment.id)
        if segment.end <= segment.start:
            errors.append(f"segment {segment.id} has non-positive duration")
        if segment.kind not in KINDS:
            errors.append(f"segment {segment.id} has unknown kind: {segment.kind}")
        if segment.role not in ROLES:
            errors.append(f"segment {segment.id} has unknown role: {segment.role}")
        if segment.role == "speaker" and segment.speaker_id not in project.speakers:
            errors.append(f"segment {segment.id} references missing speaker: {segment.speaker_id}")
        if duration is not None and segment.end > duration:
            errors.append(f"segment {segment.id} exceeds source duration {duration:.3f}")
        ordered.append(segment)
    ordered.sort(key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            errors.append(f"segments overlap: {previous.id} and {current.id}")
    if project.complete_coverage and ordered:
        if ordered[0].start > 0:
            errors.append("complete coverage starts after source time zero")
        for previous, current in zip(ordered, ordered[1:]):
            if current.start > previous.end:
                errors.append(f"complete coverage has gap: {previous.id} to {current.id}")
        if duration is not None and ordered[-1].end < duration:
            errors.append("complete coverage ends before source duration")
    return errors


def speaker_segments(project: Project) -> list[Segment]:
    return [segment for segment in project.segments if segment.role == "speaker"]


def extra_segments(project: Project) -> list[Segment]:
    return [segment for segment in project.segments if segment.role == "extra"]
