import json
from pathlib import Path

import pytest

from conference_video_cutter.voxtype import (
    VoxtypeConfig,
    load_completed_chunks,
    merge_overlap,
    plan_chunks,
    read_voxtype_config,
    render_transcript_markdown,
    require_local_endpoint,
    require_npu_health,
)


def test_read_voxtype_config_uses_remote_whisper_settings(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[whisper]\nmode = "remote"\nremote_endpoint = "http://127.0.0.1:13305"\n'
        'remote_model = "whisper-v3-turbo-FLM"\nlanguage = "ru"\n',
        encoding="utf-8",
    )

    assert read_voxtype_config(config) == VoxtypeConfig(
        endpoint="http://127.0.0.1:13305",
        model="whisper-v3-turbo-FLM",
        language="ru",
    )


def test_require_npu_health_rejects_cpu_or_unready_backend():
    with pytest.raises(RuntimeError, match="NPU"):
        require_npu_health(
            {
                "status": "ok",
                "all_models_loaded": [
                    {"device": "cpu", "status": "ready", "model_name": "whisper"}
                ],
            }
        )

    assert require_npu_health(
        {
            "status": "ok",
            "all_models_loaded": [
                {"device": "npu", "status": "in_use", "backend_alive": True, "model_name": "whisper"}
            ],
        }
    )["device"] == "npu"


def test_require_local_endpoint_rejects_upload_by_default():
    with pytest.raises(RuntimeError, match="non-local"):
        require_local_endpoint("https://transcribe.example.test/v1")

    require_local_endpoint("http://127.0.0.1:13305/v1")

    with pytest.raises(RuntimeError, match="ready"):
        require_npu_health(
            {
                "status": "ok",
                "all_models_loaded": [
                    {"device": "npu", "status": "loading", "model_name": "whisper"}
                ],
            }
        )


def test_merge_overlap_removes_repeated_boundary_words():
    previous = "Мы начнем с небольшой презентации и разберем первые шаги"
    current = "разберем первые шаги на практике и проверим результат"

    assert merge_overlap(previous, current) == "на практике и проверим результат"


def test_load_completed_chunks_reads_resume_jsonl(tmp_path: Path):
    path = tmp_path / "chunks.jsonl"
    path.write_text(
        json.dumps({"index": 0, "start": 0.0, "end": 120.0, "text": "Первый"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"index": 2, "start": 240.0, "end": 300.0, "text": "Третий"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    chunks = load_completed_chunks(path)

    assert sorted(chunks) == [0, 2]
    assert chunks[2]["text"] == "Третий"


def test_plan_chunks_keeps_absolute_targets_and_small_request_overlap():
    chunks = plan_chunks(250.0, chunk_seconds=120.0, overlap_seconds=3.0)

    assert [(item.start, item.end, item.request_start) for item in chunks] == [
        (0.0, 120.0, 0.0),
        (120.0, 240.0, 117.0),
        (240.0, 250.0, 237.0),
    ]


def test_render_transcript_markdown_keeps_chunk_timecodes():
    markdown = render_transcript_markdown(
        source="recording.mp4",
        model="whisper-v3-turbo-FLM",
        device="npu",
        cues=[{"start": 0.0, "end": 12.5, "text": "Здравствуйте"}],
    )

    assert "recording.mp4" in markdown
    assert "00:00:00.000–00:00:12.500" in markdown
    assert "`npu`" in markdown


def test_transcribe_resumes_jsonl_and_writes_provenance(tmp_path: Path, monkeypatch):
    from scripts import cvc_transcribe_voxtype as transcriber

    source = tmp_path / "recording.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "transcript"
    config = VoxtypeConfig("http://127.0.0.1:13305", "whisper-npu", "ru")
    calls: list[int] = []

    monkeypatch.setattr(
        transcriber,
        "_json_request",
        lambda *args, **kwargs: {
            "all_models_loaded": [
                {"device": "npu", "status": "ready", "backend_alive": True, "model_name": "whisper-npu"}
            ]
        },
    )
    monkeypatch.setattr(transcriber, "_duration", lambda path: 10.0)
    monkeypatch.setattr(transcriber, "_audio_chunk", lambda *args: b"wav")

    def fake_transcribe(*args, **kwargs):
        calls.append(len(calls))
        return "текст"

    monkeypatch.setattr(transcriber, "_transcribe_audio", fake_transcribe)

    result = transcriber.transcribe(
        source,
        output,
        config,
        chunk_seconds=6.0,
        overlap_seconds=1.0,
        timeout=5.0,
        force=False,
        allow_remote=False,
    )

    assert result["device"] == "npu"
    assert result["chunks"] == 2
    assert len(calls) == 2
    assert (output / "transcript.json").is_file()
    assert (output / "transcript.md").is_file()
    provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["device"] == "npu"
    assert provenance["completed_count"] == 2
    assert provenance["source"] == source.name
    assert str(tmp_path) not in (output / "provenance.json").read_text(encoding="utf-8")


def test_transcribe_loads_lazily_registered_model_before_npu_check(tmp_path: Path, monkeypatch):
    from scripts import cvc_transcribe_voxtype as transcriber

    source = tmp_path / "recording.mp4"
    source.write_bytes(b"source")
    responses = [
        {"all_models_loaded": []},
        {"status": "success", "message": "Loaded model"},
        {
            "all_models_loaded": [
                {"device": "npu", "status": "ready", "backend_alive": True, "model_name": "model"}
            ]
        },
    ]
    calls: list[tuple[str, str]] = []

    def fake_request(url, *, method="GET", **kwargs):
        calls.append((url, method))
        return responses.pop(0)

    monkeypatch.setattr(transcriber, "_json_request", fake_request)
    monkeypatch.setattr(transcriber, "_duration", lambda path: 1.0)
    monkeypatch.setattr(transcriber, "_audio_chunk", lambda *args: b"wav")
    monkeypatch.setattr(transcriber, "_transcribe_audio", lambda *args: "текст")

    transcriber.transcribe(
        source,
        tmp_path / "transcript",
        VoxtypeConfig("http://127.0.0.1:13305", "model", "ru"),
        chunk_seconds=2.0,
        overlap_seconds=0.0,
        timeout=5.0,
        force=False,
        allow_remote=False,
    )

    assert calls[0][1] == "GET"
    assert calls[1][1] == "POST"
    assert calls[1][0].endswith("/v1/load")
    assert calls[2][1] == "GET"


def test_lazy_npu_load_is_pinned_and_can_replace_evicted_model(monkeypatch):
    from scripts import cvc_transcribe_voxtype as transcriber

    responses = [
        {"all_models_loaded": [{"device": "cpu", "status": "ready", "backend_alive": True, "model_name": "other"}]},
        {"status": "success"},
        {"all_models_loaded": [{"device": "npu", "status": "ready", "backend_alive": True, "model_name": "model"}]},
    ]
    request_bodies: list[dict[str, object]] = []

    def fake_request(url, *, method="GET", body=None, **kwargs):
        if method == "POST":
            request_bodies.append(json.loads(body))
        return responses.pop(0)

    monkeypatch.setattr(transcriber, "_json_request", fake_request)

    _, backend = transcriber._ensure_npu("http://127.0.0.1:13305", "model", 5.0)

    assert backend["device"] == "npu"
    assert request_bodies == [{"model_name": "model", "pinned": True}]


def test_transcribe_audio_retries_transient_endpoint_failure(monkeypatch):
    from scripts import cvc_transcribe_voxtype as transcriber

    attempts = 0

    def fake_request(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary failure")
        return {"text": "готово"}

    monkeypatch.setattr(transcriber, "_json_request", fake_request)
    monkeypatch.setattr(transcriber.time, "sleep", lambda seconds: None)

    assert transcriber._transcribe_audio("http://127.0.0.1:13305", "model", "ru", b"wav", 5.0, retries=2) == "готово"
    assert attempts == 3


def test_transcribe_audio_reloads_model_after_eviction(monkeypatch):
    from scripts import cvc_transcribe_voxtype as transcriber

    responses = iter(
        [
            RuntimeError('HTTP Error 404: {"error":{"type":"model_not_loaded"}}'),
            {"all_models_loaded": []},
            {"status": "success"},
            {"all_models_loaded": [{"device": "npu", "status": "ready", "backend_alive": True, "model_name": "model"}]},
            {"text": "снова работает"},
        ]
    )

    def fake_request(*args, **kwargs):
        response = next(responses)
        if isinstance(response, RuntimeError):
            raise response
        return response

    monkeypatch.setattr(transcriber, "_json_request", fake_request)
    monkeypatch.setattr(transcriber.time, "sleep", lambda seconds: None)

    assert transcriber._transcribe_audio("http://127.0.0.1:13305", "model", "ru", b"wav", 5.0, retries=1) == "снова работает"
