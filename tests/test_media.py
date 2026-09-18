from pathlib import Path

from conference_video_cutter.media import build_cut_command
from conference_video_cutter.models import Segment


def test_default_cut_uses_stream_copy():
    command = build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"))
    assert "-c" in command and command[command.index("-c") + 1] == "copy"
    assert "-t" in command and command[command.index("-t") + 1] == "17.500"


def test_accurate_cut_does_not_use_stream_copy():
    command = build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"), accurate=True)
    assert "-c:v" in command and command[command.index("-c:v") + 1] == "libx264"
    assert "copy" not in command
