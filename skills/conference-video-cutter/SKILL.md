---
name: conference-video-cutter
description: Use for transcript-first conference video segmentation, speaker-boundary review, bilingual naming, and FFmpeg clip rendering. Supports Russian and English workflows.
---

# Conference Video Cutter

This skill turns a long conference recording into a reviewed, reproducible edit plan and labeled MP4 clips. It is intentionally local-first: the transcript and a human-reviewed JSON plan are the source of truth; FFmpeg performs the cuts; `ffprobe` verifies the outputs.

## Language

Answer in the user's language. Russian is first-class, not a translation afterthought. Preserve the original spelling in `name` and add a checked Russian form in `name_ru` when the project language is Russian. Do not invent a person's identity from a noisy transcript. Use slides, the recording, and public sources only when the user asks for current validation and the source is appropriate.

## Workflow

1. Run `cvc doctor` and confirm that `ffmpeg` and `ffprobe` are available.
2. Create or inspect a project JSON with `cvc init`.
3. Transcribe the complete recording before deciding boundaries. Keep source timestamps and retain uncertain text rather than silently rewriting it.
4. Classify the transcript into blocks: preparation, host opening, speaker introduction, main talk, host transition, audience or host Q&A, technical delay, closing, and other.
5. Make each speaker segment start at the first meaningful frame of that speaker and end after that speaker's final answer. Exclude preparation and host-only material from speaker clips; keep excluded material as explicitly labeled `role: extra` segments when it helps auditability.
6. Review intervals for overlap, accidental gaps, wrong speaker attribution, and speaker-name spelling. Use half-open intervals `[start, end)`.
7. Run `cvc validate project.json` before rendering.
8. Use `cvc render project.json` for stream-copy cuts. If the source has no suitable keyframe at a boundary or the output loses a stream, rerun with `cvc render --accurate project.json` and record that choice.
9. Check `manifest.json`, file sizes, stream metadata, and representative playback before calling the work complete.

## Safety and evidence

- Do not download a recording, contact a service, or publish clips unless the user explicitly authorizes that action and has the right to use the media.
- Never include tokens, cookies, private URLs, or personal account data in a project file or repository.
- Do not claim that an automated boundary is correct without checking it against both the transcript timing and the video.
- Treat OSINT as validation evidence, not identity proof. Cite sources and distinguish confirmed facts, hypotheses, and unresolved items.
- Do not use face recognition or biometric identification. A presentation slide or an explicit spoken introduction may establish a displayed name; public-source validation should resolve spelling and context, not replace evidence from the recording.

## Useful commands

```bash
cvc --lang ru doctor
cvc --lang ru init --input conference.mp4 --output project.json
cvc validate project.json
cvc transcript project.json --output transcript.md
cvc render project.json
cvc render --accurate project.json
```

The repository's [English guide](../../README.md) and [Russian guide](../../README.ru.md) document the JSON schema, block taxonomy, output manifest, troubleshooting, and contribution workflow.
