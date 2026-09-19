# Conference Video Cutter

Provider-neutral, transcript-driven editing for conferences: turn one long recording into reviewed speaker talks, Q&A blocks, and clearly labeled extra clips.

[Русская версия](README.ru.md)

## Why this exists

Conference recordings are not ordinary silence-cutting jobs. A useful edit must preserve the whole answer, separate the host's transitions from the speaker's talk, keep preparation and technical delays auditable, and retain the correct names in the language of the event.

Conference Video Cutter makes those decisions explicit in a small JSON edit plan. It does not guess boundaries from silence alone and it does not hide the source intervals behind an opaque project file.

## Features

- bilingual CLI and documentation (`en` / `ru`);
- transcript-to-Markdown rendering with source timestamps;
- speaker and extra-block taxonomy: opening, introduction, talk, Q&A, transition, preparation, closing, and other;
- deterministic half-open intervals (`[start, end)`), overlap and duration validation;
- FFmpeg stream-copy cuts only; the product never transcodes;
- post-render `ffprobe` checks, SHA-256 hashes, and a machine-readable `manifest.json`;
- provider-neutral transcript contract: import SRT/VTT/JSON or connect an explicit cloud provider;
- no silent media upload and no mandatory local ASR;
- Codex skills and safety tools for preflight, normalization, review, and output verification.

The project deliberately separates transcription, editorial review, and rendering. A cloud transcription provider is an explicit opt-in; a local ASR backend is optional. The final cut remains reproducible from the reviewed plan.

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

The media engine is also available as a small standalone CLI. It always uses FFmpeg stream-copy and never accepts a transcoding mode:

```bash
cvc-cut probe conference.mp4 --json
cvc-cut cut --input conference.mp4 --start 00:10:00 --end 00:20:00 --output clip.mp4
cvc-cut snap --input conference.mp4 --start 00:10:00 --end 00:20:00 --output clip.mp4 --window 0.25
cvc-cut batch project.json --json
cvc-cut verify output/manifest.json --strict --json
```

`cvc-cut cut` is the shortest path for one interval; `cvc-cut batch` uses the same reviewed project format as `cvc render`. Existing files are protected unless `--force` is explicit. Because streams are copied, a non-keyframe boundary can produce a duration warning; the CLI reports it instead of silently re-encoding.

`cvc-cut snap` is stricter: it tries only nearby video keyframe candidates, verifies the resulting audio/video start alignment and duration, and returns `requires-transcode` without writing a file when no safe candidate exists.

## Quick start

1. Obtain a timestamped transcript for the full recording by importing SRT/VTT/JSON or using an explicitly selected cloud provider. Keep the original transcript as evidence. Local ASR is optional, not required.
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

6. Inspect `output/manifest.json` and play the clips. Stream-copy is always used; any duration drift is a review finding that must be resolved by moving the boundary or explicitly accepted:

   ```bash
   cvc render project.json
   ```

Stream-copy preserves the original encoded streams and never invokes a video or audio encoder. It is constrained by keyframes, so warnings must remain visible and boundary changes must be made in the edit plan.

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

Each clip is written to `output_dir`. The manifest records the source interval, observed duration, duration delta, codecs, mode, file size, SHA-256 hash, and per-clip warnings. Its top-level `warnings` list makes boundary drift easy to gate in automation:

```text
output/
├── 01 — Проверка фактов — Алексей Пример.mp4
├── 00 — Переход ведущего.mp4
└── manifest.json
```

The source recording and real conference transcripts are intentionally excluded from Git. Use `examples/demo/` to understand the schema without distributing media.

## Codex plugin tools

The repository is also a Codex plugin. Its skills teach the cloud-first workflow, review speaker and Q&A boundaries, and harden private-media processing. The bundled tools do not upload anything:

```bash
python3 scripts/cvc_preflight.py project.json --json
python3 scripts/cvc_normalize_transcript.py transcript.srt --output transcript.cvc.json
python3 scripts/cvc_validate_output.py output/manifest.json --json --strict
```

`cvc_preflight.py` checks source, transcript/provider choice, FFmpeg, and disk without making a network request. `cvc_normalize_transcript.py` converts SRT, VTT, and common provider JSON into `cvc-transcript-v1`. `cvc_validate_output.py` checks files and hashes and can fail on render warnings.

## Design boundaries

This is an editing and verification core plus Codex workflow tools, not an identity database or an opaque hosted editor. It does not download recordings, perform face recognition, search the web for a person's name, or silently rewrite a transcript. Cloud processing remains an explicit provider decision with consent and a processing receipt.

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
