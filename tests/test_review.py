from __future__ import annotations

from pathlib import Path

import pytest

from conference_video_cutter.models import Project, Segment, Speaker
from conference_video_cutter.review import render_review_html
from conference_video_cutter.transcript import TranscriptCue


def test_review_html_escapes_text_and_contains_seekable_segments(tmp_path: Path):
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"placeholder")
    output = tmp_path / "review" / "review.html"
    project = Project(
        language="ru",
        source=source,
        transcript=None,
        output_dir=tmp_path / "output",
        speakers={"spk": Speaker("<Original>", "<Русское имя>")},
        segments=(Segment("01", "<Основное>", "main_talk", 12.5, 30.0, "speaker", "spk"),),
    )

    render_review_html(
        project,
        [TranscriptCue(13.0, 14.0, '<script>alert("x")</script>')],
        output,
    )

    html = output.read_text(encoding="utf-8")
    assert "../recording.mp4" in html
    assert "00:00:12.500–00:00:30.000" in html
    assert "&lt;Основное&gt;" in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "<script>alert" not in html


def test_review_cli_reads_canonical_json_transcript(tmp_path: Path, capsys):
    source = tmp_path / "recording.mp4"
    transcript = tmp_path / "transcript.json"
    project = tmp_path / "project.json"
    output = tmp_path / "review.html"
    source.write_bytes(b"placeholder")
    transcript.write_text(
        '{"format":"cvc-transcript-v1","cues":[{"start":1,"end":2,"text":"Каноническая реплика"}]}',
        encoding="utf-8",
    )
    project.write_text(
        '{"language":"ru","source":"recording.mp4","transcript":"transcript.json","output_dir":"output","segments":[{"id":"01","title":"Блок","kind":"main_talk","start":0,"end":3,"role":"extra"}]}',
        encoding="utf-8",
    )

    from conference_video_cutter.cli import main

    assert main(["review", str(project), "--output", str(output)]) == 0
    assert "Каноническая реплика" in output.read_text(encoding="utf-8")
    assert str(output) in capsys.readouterr().out


def test_review_refuses_existing_output_without_force(tmp_path: Path):
    source = tmp_path / "recording.mp4"
    transcript = tmp_path / "transcript.srt"
    project = tmp_path / "project.json"
    output = tmp_path / "review.html"
    source.write_bytes(b"placeholder")
    transcript.write_text("1\n00:00:00,000 --> 00:00:01,000\nText\n", encoding="utf-8")
    project.write_text(
        '{"language":"en","source":"recording.mp4","transcript":"transcript.srt","output_dir":"output","segments":[]}',
        encoding="utf-8",
    )
    output.write_text("keep", encoding="utf-8")

    from conference_video_cutter.cli import main

    assert main(["review", str(project), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "keep"
