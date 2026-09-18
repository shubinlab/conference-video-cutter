---
name: conference-video-review
description: Use when a conference transcript, diarization result, chapter list, or edit plan has uncertain speaker identity, topic blocks, Q&A boundaries, or overlapping time ranges.
---

# Conference Video Review

Treat automation as evidence, not as editorial truth. The deliverable is a reviewable plan whose ranges can be explained from transcript cues and the actual video.

## Review order

1. Read the complete transcript before choosing clips.
2. Align cues to the video and mark speaker turns. Keep `speaker-01` labels until identity is confirmed.
3. Classify every relevant block: preparation, host opening, speaker introduction, talk, transition, Q&A, technical delay, closing, or other.
4. For each speaker clip, check the first meaningful visual/audio frame and the final answer. Do not cut at the first mention of a name or at a host-only introduction.
5. Check the boundary against the preceding and following cue. Add a small editorial pad only when it prevents clipped words; record the reason.
6. Validate unique IDs, no overlap, source-duration bounds, and intended gaps.

## Identity and OSINT

- A slide or explicit spoken introduction can establish a displayed name; public sources can validate spelling, role, company, and current terminology.
- Do not infer identity from voice, face, accent, or search similarity.
- Keep original spelling, normalized Russian spelling, and unresolved alternatives distinct.
- For every correction, record source URL and confidence in review notes.

## Expected output

Produce:

- a Markdown transcript grouped by editorial blocks;
- a JSON plan with source intervals and `role: speaker|extra`;
- a review log containing uncertain boundaries and names;
- a list of clips excluded from the main speaker set and why.

Use `cvc validate` and `scripts/cvc_validate_output.py` after changes. A stream-copy duration warning is a review failure for a boundary that must be exact; adjust the editorial boundary to the nearest acceptable keyframe or retain the warning explicitly. Never switch to transcoding.
