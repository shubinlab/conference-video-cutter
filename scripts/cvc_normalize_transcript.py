#!/usr/bin/env python3
"""Normalize an external SRT, VTT, or JSON transcript for CVC review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TIMESTAMP = re.compile(
    r"(?P<hours>\d{1,3}):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:[,.](?P<millis>\d{1,3}))?"
)


def parse_time(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = TIMESTAMP.fullmatch(str(value).strip().replace(",", "."))
    if not match:
        raise ValueError(f"unsupported timestamp: {value!r}")
    fraction = (match.group("millis") or "").ljust(3, "0")
    return (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
        + (int(fraction) / 1000 if fraction else 0)
    )


def clean_text(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip()).strip()


def parse_srt_or_vtt(text: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        left, right = (part.strip() for part in lines[timing_index].split("-->", 1))
        right = right.split(maxsplit=1)[0]
        cue = {
            "start": parse_time(left),
            "end": parse_time(right),
            "text": clean_text(lines[timing_index + 1 :]),
        }
        if cue["end"] < cue["start"]:
            raise ValueError(f"cue ends before it starts: {cue}")
        if cue["end"] == cue["start"]:
            cue["warning"] = "non-positive duration cue retained for review"
        if cue["text"]:
            cues.append(cue)
    return cues


def parse_json(data: Any) -> list[dict[str, Any]]:
    raw = data.get("cues", data.get("segments", data)) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("JSON transcript must be a list or an object with cues/segments")
    cues: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each JSON transcript cue must be an object")
        start = parse_time(item.get("start", item.get("start_time")))
        end = parse_time(item.get("end", item.get("end_time")))
        text = str(item.get("text", item.get("transcript", ""))).strip()
        if end < start:
            raise ValueError(f"cue ends before it starts: {item}")
        cue: dict[str, Any] = {"start": start, "end": end, "text": text}
        if end == start:
            cue["warning"] = "non-positive duration cue retained for review"
        for key in ("speaker", "speaker_id", "confidence"):
            if key in item:
                cue[key] = item[key]
        if text:
            cues.append(cue)
    return cues


def read_text(path: Path) -> tuple[str, str | None]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding), None if encoding.startswith("utf-8") else encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replacement"


def normalize(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        cues = parse_json(data)
    else:
        text, fallback = read_text(path)
        if fallback:
            warnings.append(f"decoded source with {fallback}")
        cues = parse_srt_or_vtt(text)
    cues.sort(key=lambda cue: (cue["start"], cue["end"]))
    return {
        "format": "cvc-transcript-v1",
        "source": path.name,
        "warnings": warnings,
        "cues": cues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = normalize(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
