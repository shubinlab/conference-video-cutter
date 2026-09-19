from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from .models import Project
from .timecode import format_time
from .transcript import TranscriptCue, _kind_label, group_cues


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_review_html(project: Project, cues: list[TranscriptCue], output: Path) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    media_href = quote(os.path.relpath(project.source, output.parent).replace(os.sep, "/"), safe="/.:_-~")
    groups = group_cues(cues, list(project.segments))
    parts = [
        "<!doctype html>",
        '<html lang="ru"><head><meta charset="utf-8">',
        f"<title>Conference review — {_esc(project.source.name)}</title>",
        "<style>body{font:16px system-ui,sans-serif;line-height:1.45;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#202124}video{width:100%;max-height:62vh;background:#111}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}th{background:#f3f4f6}button{font:inherit;padding:.25rem .5rem;cursor:pointer}.cue{margin:.5rem 0;padding:.5rem;background:#fafafa}.muted{color:#666}.review{white-space:nowrap}</style>",
        "</head><body>",
        "<h1>Conference review / Редакторская проверка</h1>",
        f"<p class=muted>Source: {_esc(project.source.name)}</p>",
        f'<video id="player" controls preload="metadata" src="{_esc(media_href)}"></video>',
        "<p class=muted>Нажимайте на таймкод, чтобы перейти к фрагменту. Отметьте блок после проверки видео и транскрипта.</p>",
        "<table><thead><tr><th>ID</th><th>Блок</th><th>Спикер</th><th>Интервал</th><th>Проверка</th></tr></thead><tbody>",
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
            f'<td class="review"><label><input type="checkbox" data-segment="{_esc(segment.id)}"> принято</label></td>'
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
        "<script>const player=document.getElementById('player');document.querySelectorAll('.seek').forEach((button)=>{button.addEventListener('click',()=>{player.currentTime=Number(button.dataset.start);player.play();});});</script></body></html>"
    )
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write("\n".join(parts))
    os.replace(temporary, output)
