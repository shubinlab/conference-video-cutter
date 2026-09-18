# Conference Video Cutter Design

**Date:** 2026-09-18
**Status:** Approved for implementation; plugin contract revised 2026-09-18
**Languages:** English and Russian

## Goal

Turn a long conference recording into a reviewable transcript and a clean set of speaker clips, while keeping host transitions, technical preparation, and conference closing in separately named files.

## Product promise

Conference Video Cutter is a provider-neutral, transcript-first editing core and Codex plugin for talks, webinars, and panels. It favors an explicit, inspectable edit plan over opaque automatic cuts: every segment has a type, speaker, topic, source interval, and output role. Precise rendering is the safe default for arbitrary boundaries; stream copy is an explicit fast mode with visible keyframe limitations.

The user-facing project is bilingual. The CLI supports `en` and `ru` messages, documentation is maintained in `README.md` and `README.ru.md`, and transcript text, speaker names, and filenames preserve Unicode and the source language.

## Research-derived decisions

- Use previewable plans and an explicit review step, following mature CLI editor patterns such as Auto-Editor’s preview/manual ranges and export modes.
- Keep speaker diarization optional. `pyannote-audio` is capable but brings a substantial ML stack; transcript segmentation and editorial classification must still be reviewable.
- Treat scene detection as supporting evidence, not as semantic truth; PySceneDetect detects visual cuts, not speaker or Q&A boundaries.
- Keep a no-reencode path, but make precise rendering the default and document keyframe limitations. FFmpeg stream copy is fast but cannot guarantee arbitrary frame-accurate starts.
- Preserve intermediate artifacts and a manifest so a bad cut can be corrected without repeating transcription.
- Design around the practical failure mode surfaced in community discussions: automatic silence/filler removal can clip words, so padding, review, and validation are first-class settings.

## Scope

### In scope for v0.1

1. Dependency-light Python package with a `cvc` console command.
2. JSON project configuration and JSON edit-plan schema.
3. SRT transcript parsing and Markdown rendering with block headings.
4. Human-reviewable segment types: `opening`, `speaker_intro`, `main_talk`, `qa`, `host_transition`, `technical_prep`, `closing`, and `other`.
5. Stream-copy FFmpeg rendering of speaker clips and extra clips.
6. Optional accurate rendering command flag using FFmpeg re-encoding.
7. Coverage, overlap, duration, codec, and output-file validation.
8. English and Russian CLI messages and documentation.
9. Codex plugin manifest, provider-neutral skills, and standalone no-upload tools for preflight, transcript normalization, and output verification.
10. Example plan and synthetic media fixture for tests; no copyrighted conference media in the repository.

### Explicitly deferred

- A desktop or browser editor.
- A built-in cloud transcription vendor; adapters remain an explicit integration boundary.
- Automatic name discovery from the web.
- Fully automatic semantic boundary selection without review.
- Video downloading from third-party services.
- Face recognition or biometric speaker identification.

## Architecture

```text
source video + SRT/VTT/JSON transcript + project.json
                      |
             provider/import adapter
                      v
                  cvc plan
                         v
                  reviewed plan.json
                    /           \
          cvc transcript      cvc render
             |                    |
       transcript.md        clips / extras / manifest
```

The core is pure Python where possible. Process execution is isolated in an FFmpeg adapter. Plans use half-open intervals `[start, end)` in seconds, which makes coverage and adjacent cuts deterministic. Rendering accepts a list of validated segments and never infers names from filenames.

## Data contracts

`project.json`:

```json
{
  "language": "ru",
  "source": "recording.mp4",
  "transcript": "transcript.srt",
  "output_dir": "output",
    "copy_streams": false,
  "speakers": {
    "spk-01": {"name": "Alexey Example", "name_ru": "Алексей Пример", "topic": "Example talk"}
  },
  "segments": [
    {"id": "01", "speaker_id": "spk-01", "title": "Example talk", "kind": "main_talk", "start": 12.4, "end": 842.8, "role": "speaker"}
  ]
}
```

Required invariants:

- `start >= 0`, `end > start`.
- IDs are unique and stable.
- Speaker clip segments do not overlap and have a speaker/title.
- Extra segments may be adjacent to speaker segments but may not overlap them.
- A render plan must declare whether it is complete coverage or intentionally sparse.
- Every rendered file is recorded with source interval, duration, codec, and SHA-256 in `manifest.json`.

## CLI

```text
cvc init --input recording.mp4 --output project.json --lang en
cvc validate project.json
cvc transcript project.json --format md --output transcript.md
cvc render project.json
cvc render project.json --stream-copy
cvc doctor
```

The CLI uses `--lang ru|en` and `CVC_LANG`; documentation gives equivalent commands in both languages. `cvc doctor` checks Python, FFmpeg, FFprobe, and the selected transcription command without downloading a model or touching media.

## Failure handling

- Missing FFmpeg/FFprobe: actionable bilingual error with install hints.
- Invalid or overlapping plan: fail before writing media.
- Stream-copy cut may begin on a nearby keyframe: record the requested and observed duration, warn in the manifest, and suggest precise rendering.
- Failed FFmpeg command: preserve the plan and partial files, return a non-zero exit code, and identify the exact segment.
- Transcript gaps: keep them visible as `unassigned` in Markdown instead of silently dropping text.

## Acceptance criteria

- A new user can install the package, run `cvc doctor`, validate the example plan, and render a synthetic MP4.
- `pytest` covers time parsing, plan validation, coverage, bilingual messages, transcript block grouping, and render-command construction.
- CI runs tests, compilation, package build, and plugin validation.
- No secrets, conference source media, transient stream URLs, or user-specific absolute paths are committed.
- README examples work from a clean checkout with only Python and FFmpeg installed for rendering.
