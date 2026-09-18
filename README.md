# Conference Video Cutter

Local-first, transcript-driven editing for conferences: turn one long recording into reviewed speaker talks, Q&A blocks, and clearly labeled extra clips.

[Русская версия](README.ru.md)

## Why this exists

Conference recordings are not ordinary silence-cutting jobs. A useful edit must preserve the whole answer, separate the host's transitions from the speaker's talk, keep preparation and technical delays auditable, and retain the correct names in the language of the event.

Conference Video Cutter makes those decisions explicit in a small JSON edit plan. It does not guess boundaries from silence alone and it does not hide the source intervals behind an opaque project file.

## Features

- bilingual CLI and documentation (`en` / `ru`);
- transcript-to-Markdown rendering with source timestamps;
- speaker and extra-block taxonomy: opening, introduction, talk, Q&A, transition, preparation, closing, and other;
- deterministic half-open intervals (`[start, end)`), overlap and duration validation;
- FFmpeg stream-copy cuts by default, with an opt-in accurate re-encode path;
- post-render `ffprobe` checks, SHA-256 hashes, and a machine-readable `manifest.json`;
- no runtime dependency on a cloud API, database, or proprietary editor.

The project deliberately separates discovery from rendering: transcription and identity validation can use the tools appropriate to the recording, while the final cut is reproducible from the reviewed plan.

## Install

Install FFmpeg first from the [official download page](https://ffmpeg.org/download.html), then install the package with any standard Python environment:

```bash
uv tool install git+https://github.com/shubinlab/conference-video-cutter.git
# or, from a checkout:
python -m pip install .
```

Check the local tools:

```bash
cvc doctor
cvc --lang ru doctor
```

## Quick start

1. Obtain a timestamped transcript for the full recording with the local ASR workflow you trust. Keep the original transcript as evidence.
2. Create a project skeleton:

   ```bash
   cvc --lang ru init --input conference.mp4 --output project.json
   ```

3. Fill `speakers` and `segments` in `project.json`. Review every start and end against both the transcript and the video. A speaker segment should begin with the first meaningful frame of the speaker and end after the speaker's final answer; host-only introductions and preparation belong in labeled `role: extra` segments when they need to be retained.
4. Render a readable transcript:

   ```bash
   cvc --lang ru transcript project.json --output transcript.md
   ```

5. Validate, then cut:

   ```bash
   cvc validate project.json
   cvc render project.json
   ```

6. Inspect `output/manifest.json` and play the clips. If a boundary is not keyframe-aligned and stream-copy loses a stream, use:

   ```bash
   cvc render --accurate project.json
   ```

Stream-copy is fast and preserves the encoded streams, but it is constrained by keyframes. Accurate mode decodes and re-encodes with H.264/AAC and is slower.

## Project file

The smallest useful plan looks like this:

```json
{
  "language": "ru",
  "source": "conference.mp4",
  "transcript": "transcript.srt",
  "output_dir": "output",
  "copy_streams": true,
  "speakers": {
    "spk-01": {
      "name": "Alexey Example",
      "name_ru": "Алексей Пример",
      "topic": "How to review evidence"
    }
  },
  "segments": [
    {
      "id": "01",
      "speaker_id": "spk-01",
      "title": "Проверка фактов",
      "kind": "main_talk",
      "start": "00:05:00.000",
      "end": "00:25:00.000",
      "role": "speaker",
      "filename": "01 — Проверка фактов — Алексей Пример.mp4"
    }
  ]
}
```

`start` is inclusive and `end` is exclusive. `role: speaker` requires a known `speaker_id`; `role: extra` is for material such as host transitions or technical delays. Supported `kind` values are `opening`, `speaker_intro`, `main_talk`, `qa`, `host_transition`, `technical_prep`, `closing`, and `other`.

## Output

Each clip is written to `output_dir`. The manifest records the source interval, observed duration, codecs, mode, and SHA-256 hash:

```text
output/
├── 01 — Проверка фактов — Алексей Пример.mp4
├── 00 — Переход ведущего.mp4
└── manifest.json
```

The source recording and real conference transcripts are intentionally excluded from Git. Use `examples/demo/` to understand the schema without distributing media.

## Design boundaries

This is an editing and verification core, not a hosted transcription service or an identity database. It does not download recordings, perform face recognition, search the web for a person's name, or silently rewrite a transcript. Those steps may be useful in a larger authorized workflow, but they must remain explicit and reviewable.

## Development

```bash
uv venv .venv
uv pip install --python .venv/bin/python pytest build
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m build
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and the [research log](docs/research/2026-09-18-sources.md).

## Codex plugin

The repository is also a valid Codex plugin root. Its manifest is [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) and its bilingual workflow is [`skills/conference-video-cutter/SKILL.md`](skills/conference-video-cutter/SKILL.md). Validate it locally with:

```bash
python3 path/to/plugin-creator/scripts/validate_plugin.py .
```
