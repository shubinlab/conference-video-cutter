import pytest

from pathlib import Path

from conference_video_cutter.media import build_cut_command
from conference_video_cutter.models import Segment


def test_default_cut_uses_stream_copy():
    command = build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"))
    assert "-c" in command and command[command.index("-c") + 1] == "copy"
    assert "-t" in command and command[command.index("-t") + 1] == "17.500"
    assert "-y" not in command


def test_transcoding_is_disabled():
    with pytest.raises(ValueError, match="transcoding is disabled"):
        build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"), accurate=True)
