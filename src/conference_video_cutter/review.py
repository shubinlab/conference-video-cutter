from __future__ import annotations

import html
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from .models import Project
from .timecode import format_time
from .transcript import TranscriptCue, _kind_label, group_cues


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_review_html(project: Project, cues: list[TranscriptCue], output: Path, force: bool = False) -> None:
    output = output.resolve()
    protected = [project.source]
    if project.transcript is not None:
        protected.append(project.transcript)
    if project.project_path is not None:
        protected.append(project.project_path)
    if any(output == path.resolve() for path in protected):
        raise ValueError("review output must differ from source and transcript")
    if output.exists() and not force:
        raise FileExistsError(f"output already exists; use --force to replace it: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    media_href = quote(os.path.relpath(project.source, output.parent).replace(os.sep, "/"), safe="/.:_-~")
    groups = group_cues(cues, list(project.segments))
    russian = project.language == "ru"
    labels = {
        "title": "Редакторская проверка" if russian else "Editorial review",
        "source": "Источник" if russian else "Source",
        "hint": "Нажимайте на таймкод, чтобы перейти к фрагменту. Отметьте блок после проверки видео и транскрипта." if russian else "Click a timecode to seek. Check a block after reviewing the video and transcript.",
        "id": "ID",
        "block": "Блок" if russian else "Block",
        "speaker": "Спикер" if russian else "Speaker",
        "interval": "Интервал" if russian else "Interval",
        "review": "Проверка" if russian else "Review",
        "accepted": "принято" if russian else "accepted",
    }
    parts = [
        "<!doctype html>",
        f'<html lang="{_esc(project.language)}"><head><meta charset="utf-8">',
        f"<title>Conference review — {_esc(project.source.name)}</title>",
        "<style>body{font:16px system-ui,sans-serif;line-height:1.45;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#202124}video{width:100%;max-height:62vh;background:#111}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}th{background:#f3f4f6}button{font:inherit;padding:.25rem .5rem;cursor:pointer}.cue{margin:.5rem 0;padding:.5rem;background:#fafafa}.muted{color:#666}.review{white-space:nowrap}</style>",
        "</head><body>",
        f"<h1>{_esc(labels['title'])}</h1>",
        f"<p class=muted>{_esc(labels['source'])}: {_esc(project.source.name)}</p>",
        f'<video id="player" controls preload="metadata" src="{_esc(media_href)}"></video>',
        f"<p class=muted>{_esc(labels['hint'])}</p>",
        f"<table><thead><tr><th>{_esc(labels['id'])}</th><th>{_esc(labels['block'])}</th><th>{_esc(labels['speaker'])}</th><th>{_esc(labels['interval'])}</th><th>{_esc(labels['review'])}</th></tr></thead><tbody>",
    ]
    for segment in project.segments:
        speaker = project.speakers.get(segment.speaker_id) if segment.speaker_id else None
        speaker_name = ""
        if speaker:
            speaker_name = speaker.name_ru if project.language == "ru" and speaker.name_ru else speaker.name
        interval = f"{format_time(segment.start)}–{format_time(segment.end)}"
        parts.append(
            "<tr>"
            f"<td>{_esc(segment.id)}</td>"
            f"<td>{_esc(_kind_label(project, segment.kind))}<br>{_esc(segment.title)}</td>"
            f"<td>{_esc(speaker_name)}</td>"
            f'<td><button class="seek" data-start="{segment.start:.3f}">{_esc(interval)}</button></td>'
            f'<td class="review"><label><input type="checkbox" data-segment="{_esc(segment.id)}"> {_esc(labels["accepted"])}</label></td>'
            "</tr>"
        )
    parts.append("</tbody></table>")
    for segment in project.segments:
        parts.append(f"<h2>{_esc(segment.id)} — {_esc(segment.title)}</h2>")
        for cue in groups[segment.id]:
            interval = f"{format_time(cue.start)}–{format_time(cue.end)}"
            parts.append(
                f'<div class="cue"><button class="seek" data-start="{cue.start:.3f}">{_esc(interval)}</button> '
                f"{_esc(cue.text)}</div>"
            )
    if groups["unassigned"]:
        parts.append("<h2>Неразмеченный текст</h2>")
        for cue in groups["unassigned"]:
            interval = f"{format_time(cue.start)}–{format_time(cue.end)}"
            parts.append(f'<div class="cue"><button class="seek" data-start="{cue.start:.3f}">{_esc(interval)}</button> {_esc(cue.text)}</div>')
    parts.append(
        f"<script>const player=document.getElementById('player');const reviewKey={json.dumps('cvc-review:'+project.source.name)};document.querySelectorAll('.seek').forEach((button)=>{{button.addEventListener('click',()=>{{player.currentTime=Number(button.dataset.start);player.play();}});}});const saved=JSON.parse(localStorage.getItem(reviewKey)||'{{}}');document.querySelectorAll('input[data-segment]').forEach((box)=>{{box.checked=Boolean(saved[box.dataset.segment]);box.addEventListener('change',()=>{{saved[box.dataset.segment]=box.checked;localStorage.setItem(reviewKey,JSON.stringify(saved));}});}});</script></body></html>"
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("\n".join(parts))
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
