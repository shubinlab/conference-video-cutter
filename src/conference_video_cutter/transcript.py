from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import Project, Segment
from .timecode import format_time


@dataclass(frozen=True)
class TranscriptCue:
    start: float
    end: float
    text: str


def read_transcript(path: Path) -> tuple[str, bool]:
    """Read UTF-8 transcripts and tolerate isolated invalid decoder bytes."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), True


def _seconds(value: str) -> float:
    hours, minutes, rest = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def parse_srt(text: str) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    for raw_block in re.split(r"\n\s*\n", text.strip()):
        lines = raw_block.splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = (part.strip() for part in lines[1].split("-->", 1))
        cue_text = " ".join(line.strip() for line in lines[2:] if line.strip())
        cues.append(TranscriptCue(_seconds(start), _seconds(end), cue_text))
    return cues


def group_cues(cues: list[TranscriptCue], segments: list[Segment]) -> dict[str, list[TranscriptCue]]:
    groups = {segment.id: [] for segment in segments}
    groups["unassigned"] = []
    for cue in cues:
        matches = [segment for segment in segments if segment.start <= cue.start < segment.end]
        groups[matches[0].id if matches else "unassigned"].append(cue)
    return groups


def _crossed_boundaries(cue: TranscriptCue, segments: list[Segment]) -> list[float]:
    return [segment.end for segment in segments[:-1] if cue.start < segment.end < cue.end]


def _kind_label(project: Project, kind: str) -> str:
    labels = {
        "en": {
            "speaker_intro": "Speaker introduction",
            "main_talk": "Main talk",
            "qa": "Questions and answers",
            "opening": "Opening",
            "host_transition": "Host transition",
            "technical_prep": "Technical preparation",
            "closing": "Closing",
            "other": "Other",
        },
        "ru": {
            "speaker_intro": "Представление спикера",
            "main_talk": "Основное выступление",
            "qa": "Ответы на вопросы",
            "opening": "Открытие",
            "host_transition": "Переход ведущего",
            "technical_prep": "Техническая подготовка",
            "closing": "Закрытие",
            "other": "Прочее",
        },
    }
    return labels.get(project.language, labels["en"]).get(kind, kind)


def render_markdown(project: Project, cues: list[TranscriptCue]) -> str:
    groups = group_cues(cues, list(project.segments))
    lines = [
        "# Conference transcript / Транскрипция конференции",
        "",
        "> Generated from a reviewed edit plan. Source wording is preserved; names and terms should be reviewed against slides and public sources.",
        "> Сгенерировано из проверенного плана нарезки. Исходная формулировка сохранена; имена и термины следует сверять со слайдами и открытыми источниками.",
        "",
    ]
    for segment in project.segments:
        speaker = project.speakers.get(segment.speaker_id) if segment.speaker_id else None
        speaker_name = (speaker.name_ru if project.language == "ru" and speaker and speaker.name_ru else speaker.name if speaker else "")
        heading = " — ".join(part for part in (speaker_name, segment.title) if part)
        lines.extend(
            [
                f"## {heading or segment.id}",
                "",
                f"**Block / Блок:** {_kind_label(project, segment.kind)}",
                f"**Source interval / Исходный интервал:** `{format_time(segment.start)}–{format_time(segment.end)}`",
                "",
            ]
        )
        for cue in groups[segment.id]:
            boundaries = _crossed_boundaries(cue, list(project.segments))
            if boundaries:
                points = ", ".join(format_time(point) for point in boundaries)
                lines.extend([f"> ⚠ Cue crosses edit boundary at {points} / Реплика пересекает границу блока.", ""])
            time_range = f"{format_time(cue.start)}–{format_time(cue.end)}"
            lines.extend([f"### `{time_range}`", "", cue.text, ""])
    if groups["unassigned"]:
        lines.extend(["## Unassigned / Неразмеченный текст", ""])
        for cue in groups["unassigned"]:
            lines.extend([f"- `{format_time(cue.start)}–{format_time(cue.end)}` {cue.text}"])
    return "\n".join(lines).rstrip() + "\n"
