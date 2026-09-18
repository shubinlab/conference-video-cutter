from conference_video_cutter.models import Project, Segment, Speaker
from conference_video_cutter.transcript import TranscriptCue, group_cues, parse_srt, read_transcript, render_markdown


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


def test_markdown_marks_cue_crossing_edit_boundary():
    srt = SRT + "\n4\n00:00:07,000 --> 00:00:09,000\nПереход через границу.\n"

    markdown = render_markdown(fixture_project(), parse_srt(srt))

    assert "Cue crosses edit boundary" in markdown
    assert "Переход через границу." in markdown


def test_read_transcript_replaces_invalid_utf8_bytes(tmp_path):
    path = tmp_path / "whisper.srt"
    path.write_bytes("1\n00:00:00,000 --> 00:00:01,000\nПривет ".encode() + b"\xa3\n")

    text, replaced = read_transcript(path)

    assert replaced is True
    assert "Привет" in text
    assert "�" in text
