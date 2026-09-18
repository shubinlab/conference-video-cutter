---
name: conference-video-security
description: Use when processing private recordings, selecting a transcription provider, handling media uploads, packaging FFmpeg, or reviewing privacy and supply-chain risks in conference-video-cutter.
---

# Conference Video Security

Keep the default path no-upload and least-privilege. Any cloud path is an explicit user choice, not an implementation detail.

## Threat model

- Media and subtitle files may be malformed or hostile.
- File names, transcripts, and manifests may contain secrets or personal data.
- Cloud transcription can expose the recording, transcript, and speaker names.
- FFmpeg, installers, GitHub Actions, and provider SDKs are supply-chain inputs.

## Required controls

- Probe actual media content; do not trust extensions alone.
- Use argument arrays, not shell interpolation.
- Limit file size, duration, output disk use, and concurrent work.
- Keep tokens in the OS keychain or provider configuration, never in JSON, logs, or Git.
- Generate safe output names and keep exports inside the selected output directory.
- Render to a temporary path, verify it, then atomically publish it.
- Refuse silent overwrite and make retries idempotent.
- Redact absolute paths and private URLs from shareable manifests.
- Pin CI actions, scan dependencies, produce signed releases and attestations.

Before cloud processing, show provider, data sent, retention policy, estimated cost if available, and a cancel path. If any item is unknown, label it unknown instead of promising privacy.
