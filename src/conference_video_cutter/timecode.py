from __future__ import annotations

import math


def parse_time(value: str | int | float) -> float:
    if isinstance(value, bool):
        raise ValueError("time must be numeric or a timecode")
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        text = value.strip().replace(",", ".")
        if text.startswith("-"):
            raise ValueError(f"time must be finite and non-negative: {value!r}")
        parts = text.split(":")
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            seconds = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError(f"invalid timecode: {value}")
    else:
        raise ValueError(f"invalid time value: {value!r}")
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"time must be finite and non-negative: {value!r}")
    return seconds


def format_time(seconds: float) -> str:
    value = parse_time(seconds)
    whole = int(value)
    milliseconds = round((value - whole) * 1000)
    if milliseconds == 1000:
        whole += 1
        milliseconds = 0
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
