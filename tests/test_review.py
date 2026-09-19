from __future__ import annotations

from pathlib import Path

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
