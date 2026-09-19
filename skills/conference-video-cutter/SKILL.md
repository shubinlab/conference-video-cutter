---
name: conference-video-cutter
description: Use when turning a long conference, webinar, panel, or interview into reviewed speaker clips, a readable transcript, and an auditable edit plan.
---

# Conference Video Cutter

Use this skill as a provider-neutral editorial workflow. The product is not a local transcription service: accept an existing SRT/VTT/JSON transcript, or ask the user to choose an explicit cloud provider. Never silently upload media and never make local ASR a prerequisite.

## Workflow

1. Run the no-upload preflight before reading or rendering media:

   ```bash
   python3 scripts/cvc_preflight.py project.json --json
   ```

2. Establish the transcript source. Preserve the original transcript as evidence and normalize it when useful:

   ```bash
   python3 scripts/cvc_normalize_transcript.py transcript.srt --output transcript.cvc.json
   ```

3. Build a reviewed plan with half-open intervals `[start, end)`. Classify preparation, host opening, introduction, main talk, host transition, Q&A, technical delay, closing, and other material. Speaker clips begin at the first meaningful frame and end after the speaker's final answer.

4. Keep names separate from recognition. Use the recording, slides, explicit introductions, and requested OSINT validation. Do not turn diarization labels into identities or use face recognition.

5. Validate before rendering. This product never transcodes: always use FFmpeg stream-copy. If a requested boundary is not keyframe-safe, preserve the warning and move the boundary manually to a safe packet/keyframe rather than re-encoding.

6. Verify the output, including hashes, missing files, warnings, duration drift, and representative playback:

   ```bash
   python3 scripts/cvc_validate_output.py output/manifest.json --json --strict
   ```

For direct media operations, use the bundled `cvc-cut` CLI:

```bash
cvc-cut probe recording.mp4 --json
cvc-cut cut --input recording.mp4 --start 00:10:00 --end 00:20:00 --output clip.mp4
cvc-cut snap --input recording.mp4 --start 00:10:00 --end 00:20:00 --output clip.mp4 --window 0.25
cvc-cut batch project.json --json
cvc-cut verify output/manifest.json --strict --json
```

It is stream-copy-only. Existing outputs require `--force`; `snap` writes a file only after checking stream alignment and duration. If no safe candidate exists it returns `requires-transcode`; boundary drift is never silently repaired by timestamp shifting.

## Non-negotiable safety

- Ask for explicit consent before cloud processing and state what is uploaded, the provider, retention, and estimated cost when known.
- Do not expose tokens, cookies, private media URLs, or absolute local paths in project files, logs, Markdown, or Git.
- Do not overwrite an existing export without confirmation.
- Preserve uncertain transcript text and mark uncertainty; do not silently invent names, pronouns, companies, products, or topics.
- Report facts, hypotheses, and unresolved items separately.

Read [provider-contract.md](references/provider-contract.md) for provider selection and [project-schema.md](references/project-schema.md) for the review model. Use `conference-video-review` for detailed boundary review and `conference-video-security` for privacy or hardening work.
