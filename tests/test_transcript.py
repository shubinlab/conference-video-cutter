from conference_video_cutter.models import Project, Segment, Speaker
from conference_video_cutter.transcript import TranscriptCue, group_cues, parse_srt, render_markdown


SRT = """1
00:00:00,000 --> 00:00:04,000
Всем привет, я Арина.

2
00:00:04,000 --> 00:00:08,000
Это основной материал.

3
00:00:08,000 --> 00:00:12,000
Спасибо, отвечу на вопросы.
"""


def fixture_project():
    return Project(
        language="ru",
        source="recording.mp4",
        transcript="transcript.srt",
        output_dir="output",
        speakers={"spk-01": Speaker("Arina Khromova", "Арина Хромова")},
        segments=(
            Segment("intro", "Introduction", "speaker_intro", 0, 4, "speaker", "spk-01"),
            Segment("main", "Почему кейсы врут", "main_talk", 4, 8, "speaker", "spk-01"),
            Segment("qa", "Ответы на вопросы", "qa", 8, 12, "speaker", "spk-01"),
        ),
    )


def test_parse_srt_and_group_cues():
    cues = parse_srt(SRT)
    grouped = group_cues(cues, list(fixture_project().segments))
    assert grouped["qa"][0].text.startswith("Спасибо")


def test_markdown_labels_qa_and_keeps_russian_text():
    markdown = render_markdown(fixture_project(), parse_srt(SRT))
    assert "Ответы на вопросы" in markdown
    assert "Арина Хромова" in markdown
    assert "Почему кейсы врут" in markdown
