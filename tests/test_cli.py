import pytest

from conference_video_cutter.cli import main


def test_doctor_help_is_bilingual(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "doctor", "--help"])
    assert error.value.code == 0
    assert "провер" in capsys.readouterr().out.lower()


def test_all_command_help_is_russian(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--lang", "ru", "render", "--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "нарезать" in output
    assert "перекодировать" in output
