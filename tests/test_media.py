import pytest

from pathlib import Path

from conference_video_cutter import media
from conference_video_cutter.media import MediaInfo, build_cut_command, build_synced_cut_command
from conference_video_cutter.models import Segment


def test_default_cut_uses_stream_copy():
    command = build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"))
    assert "-c" in command and command[command.index("-c") + 1] == "copy"
    assert "-t" in command and command[command.index("-t") + 1] == "17.500"
    assert "-y" not in command


def test_transcoding_is_disabled():
    with pytest.raises(ValueError, match="transcoding is disabled"):
        build_cut_command(Path("source.mp4"), Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"), accurate=True)


def test_sync_fallback_uses_two_copy_inputs_and_isync():
    source = Path("source.mp4")
    command = build_synced_cut_command(source, Segment("01", "Talk", "main_talk", 12.5, 30, "speaker"), Path("out.mp4"))

    assert command.count(str(source)) == 2
    assert "-isync" in command
    assert "-c" in command and command[command.index("-c") + 1] == "copy"


def test_sync_fallback_validates_before_replacing_staged_output(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    output = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    calls: list[list[str]] = []

    def fake_run(command, check):
        calls.append(command)
        Path(command[-1]).write_bytes(b"candidate")

    infos = iter(
        [
            MediaInfo(60.0, "h264", "aac", video_start=10.0, audio_start=0.0),
            MediaInfo(60.0, "h264", "aac", video_start=0.0, audio_start=0.0),
        ]
    )
    monkeypatch.setattr(media.subprocess, "run", fake_run)
    monkeypatch.setattr(media, "probe", lambda path: next(infos))

    media.cut_and_probe(source, Segment("01", "Talk", "main_talk", 10.0, 70.0, "speaker"), output)

    assert calls[1][-1] != str(output)
    assert output.read_bytes() == b"candidate"
