from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .timecode import format_time


@dataclass(frozen=True)
class VoxtypeConfig:
    endpoint: str
    model: str
    language: str


@dataclass(frozen=True)
class AudioChunk:
    index: int
    start: float
    end: float
    request_start: float

    @property
    def request_duration(self) -> float:
        return self.end - self.request_start


def read_voxtype_config(path: Path) -> VoxtypeConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    whisper = data.get("whisper") or {}
    if whisper.get("mode") != "remote":
        raise RuntimeError("Voxtype whisper mode must be remote for the NPU backend")
    endpoint = str(whisper.get("remote_endpoint", "")).strip()
    model = str(whisper.get("remote_model", "")).strip()
    language = str(whisper.get("language", "auto")).strip()
    if not endpoint or not model:
        raise RuntimeError("Voxtype remote_endpoint and remote_model are required")
    return VoxtypeConfig(endpoint, model, language)


def require_local_endpoint(endpoint: str, allow_remote: bool = False) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(f"invalid Voxtype endpoint: {endpoint}")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if not allow_remote and parsed.hostname not in local_hosts:
        raise RuntimeError("refusing to upload audio to a non-local Voxtype endpoint; use --allow-remote explicitly")


def require_npu_health(data: dict[str, object], model: str | None = None) -> dict[str, object]:
    candidates = data.get("all_models_loaded")
    if not isinstance(candidates, list):
        raise RuntimeError("Voxtype health response has no loaded model list")
    matching = [item for item in candidates if isinstance(item, dict) and (not model or item.get("model_name") == model)]
    if not matching:
        matching = [item for item in candidates if isinstance(item, dict)]
    npu = next((item for item in matching if item.get("device") == "npu"), None)
    if npu is None:
        raise RuntimeError("Voxtype/Lemonade transcription backend is not running on NPU")
    if npu.get("status") not in {"ready", "in_use"} or npu.get("backend_alive") is False:
        raise RuntimeError(f"Voxtype/Lemonade NPU backend is not ready: {npu}")
    return npu


def _word_key(value: str) -> str:
    return re.sub(r"[^\wа-яё-]", "", value.lower(), flags=re.IGNORECASE)


def merge_overlap(previous: str, current: str, max_words: int = 32) -> str:
    """Remove a repeated suffix/prefix caused by overlapping ASR windows."""
    previous_words = previous.split()
    current_words = current.split()
    limit = min(max_words, len(previous_words), len(current_words))
    overlap = 0
    for size in range(1, limit + 1):
        left = [_word_key(word) for word in previous_words[-size:]]
        right = [_word_key(word) for word in current_words[:size]]
        if left == right and all(left):
            overlap = size
    return " ".join(current_words[overlap:]).strip()


def load_completed_chunks(path: Path) -> dict[int, dict[str, object]]:
    if not path.exists():
        return {}
    chunks: dict[int, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            index = int(item["index"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid resume record at {path}:{line_number}") from exc
        if not isinstance(item, dict) or "text" not in item:
            raise RuntimeError(f"invalid resume record at {path}:{line_number}")
        chunks[index] = item
    return chunks


def plan_chunks(duration: float, chunk_seconds: float, overlap_seconds: float) -> list[AudioChunk]:
    if duration <= 0 or chunk_seconds <= 0:
        raise ValueError("duration and chunk_seconds must be positive")
    if overlap_seconds < 0 or overlap_seconds >= chunk_seconds:
        raise ValueError("overlap_seconds must be non-negative and smaller than chunk_seconds")
    chunks: list[AudioChunk] = []
    start = 0.0
    index = 0
    while start < duration:
        end = min(duration, start + chunk_seconds)
        chunks.append(AudioChunk(index, start, end, max(0.0, start - overlap_seconds)))
        start = end
        index += 1
    return chunks


def render_transcript_markdown(source: str, model: str, device: str, cues: list[dict[str, object]]) -> str:
    lines = [
        "# Транскрипция",
        "",
        f"- Источник: `{source}`",
        f"- Backend: `{model}`",
        f"- Устройство: `{device}`",
        "- Таймкоды: границы аудиочанков; точность внутри чанка не гарантируется FLM API.",
        "",
    ]
    for cue in cues:
        lines.extend(
            [
                f"## `{format_time(float(cue['start']))}–{format_time(float(cue['end']))}`",
                "",
                str(cue["text"]).strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
