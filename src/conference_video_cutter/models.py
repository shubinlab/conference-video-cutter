from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Speaker:
    name: str
    name_ru: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class Segment:
    id: str
    title: str
    kind: str
    start: float
    end: float
    role: str
    speaker_id: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class Project:
    language: str
    source: Path
    transcript: Path | None
    output_dir: Path
    speakers: dict[str, Speaker] = field(default_factory=dict)
    segments: tuple[Segment, ...] = ()
    copy_streams: bool = True
    complete_coverage: bool = False
