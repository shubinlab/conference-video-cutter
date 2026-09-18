import pytest

from conference_video_cutter.timecode import format_time, parse_time


@pytest.mark.parametrize(
    ("value", "expected"),
    [("01:02:03.5", 3723.5), ("02:03", 123.0), ("7.25", 7.25), (7, 7.0)],
)
def test_parse_time_accepts_common_forms(value, expected):
    assert parse_time(value) == expected


def test_parse_time_rejects_negative_values():
    with pytest.raises(ValueError):
        parse_time("-00:00:01")


def test_format_time_is_stable():
    assert format_time(3723.5) == "01:02:03.500"
