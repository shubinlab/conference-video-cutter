# P0 Review Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first-run conference workflow reproducible and reviewable by fixing project paths, making preflight read-only, recording source evidence, generating a local review page, and decoding every rendered clip before publication.

**Architecture:** Keep the existing JSON project and FFmpeg stream-copy core. Add small standard-library helpers: provenance records source hash and full ffprobe JSON without private project paths; review renders a self-contained HTML document referencing the selected media and transcript; render/cut run a decode-only FFmpeg check before atomic publication. No ASR dependency, web upload, or transcoding is added.

**Tech Stack:** Python 3.11+, standard library, pytest, FFmpeg/ffprobe.

**Spec:** `docs/superpowers/specs/2026-09-18-conference-video-cutter-design.md`

## Global Constraints

- The product never silently uploads media or invokes ASR.
- The product never transcodes in the lossless renderer.
- Existing outputs require explicit `--force`.
- Project paths are relative to the project file unless explicitly absolute.
- Private media and absolute local paths stay outside shareable reports.
- Every published clip is staged, verified, and then atomically published.

## Review Focus

- Project JSON created outside the source directory must still resolve the source correctly; test `cvc init` with different directories.
- Preflight must not create directories or modify the project; test a missing output directory.
- Evidence must be reproducible and shareable without leaking absolute paths; test source hash and redacted ffprobe profile.
- Review HTML must escape transcript/name text and retain usable media links; test hostile HTML text.
- A corrupt or undecodable stream-copy output must never be published; test decode failure and output absence.

---

### Task 1: Correct onboarding paths and read-only preflight

**Files:**
- Modify: `src/conference_video_cutter/cli.py`
- Modify: `scripts/cvc_preflight.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_plugin_tools.py`
- Modify: `README.md`
- Modify: `README.ru.md`

**Interfaces:**
- `cvc init --input SOURCE --output PROJECT` writes a source path relative to `PROJECT.parent`, preserving an absolute path only when a relative path cannot be computed.
- `scripts/cvc_preflight.py` reports disk usage from an existing parent directory and never creates `output_dir`.

- [ ] **Step 1: Write failing tests** for `cvc init` from a different directory and for preflight not creating a missing output directory.
- [ ] **Step 2: Run the focused tests and confirm the path assertion fails and the directory side-effect is observable.**
- [ ] **Step 3: Implement relative path calculation with `os.path.relpath` and remove preflight directory creation, using the nearest existing parent for disk usage.**
- [ ] **Step 4: Run focused tests, then the full suite.**
- [ ] **Step 5: Update both READMEs so `doctor` is described accurately and `init` documents project-relative paths.**
- [ ] **Step 6: Commit `fix(cvc): make onboarding paths reproducible`.**

### Task 2: Add reproducible source evidence

**Files:**
- Create: `src/conference_video_cutter/provenance.py`
- Modify: `src/conference_video_cutter/cli.py`
- Create: `tests/test_provenance.py`
- Modify: `README.md`
- Modify: `README.ru.md`

**Interfaces:**
- `build_source_evidence(source: Path) -> dict[str, object]` returns format version, basename, byte size, SHA-256, and full ffprobe JSON with no absolute path.
- `cvc evidence PROJECT --output source-evidence.json` writes the evidence atomically and performs no network request.

- [ ] **Step 1: Write a failing test** that creates a synthetic MP4, calls `build_source_evidence`, and asserts stable hash, size, basename-only source, and codec data.
- [ ] **Step 2: Run the focused test and confirm the import/command fails because the interface is absent.**
- [ ] **Step 3: Implement hashing and ffprobe JSON collection using argument arrays and a temporary file followed by `os.replace`.**
- [ ] **Step 4: Add the `evidence` CLI command and test its output path and absence of absolute paths.**
- [ ] **Step 5: Run the full suite and update bilingual documentation.**
- [ ] **Step 6: Commit `feat(cvc): add source evidence records`.**

### Task 3: Add a local review artifact

**Files:**
- Create: `src/conference_video_cutter/review.py`
- Modify: `src/conference_video_cutter/cli.py`
- Create: `tests/test_review.py`
- Modify: `README.md`
- Modify: `README.ru.md`

**Interfaces:**
- `render_review_html(project: Project, cues: list[TranscriptCue], output: Path) -> None` writes escaped HTML with a video element, segment table, source intervals, transcript cues, and accept/review status placeholders.
- `cvc review PROJECT --output review.html` imports the project transcript without uploading it.

- [ ] **Step 1: Write a failing test** with hostile speaker/title/cue text and assert HTML escaping plus segment and timecode presence.
- [ ] **Step 2: Run the focused test and confirm the missing module/interface failure.**
- [ ] **Step 3: Implement a small standard-library HTML renderer with escaped text and a relative media source.**
- [ ] **Step 4: Add the CLI command, including a useful error when the transcript is missing.**
- [ ] **Step 5: Run full tests and manually open the generated HTML against the real conference project.**
- [ ] **Step 6: Commit `feat(cvc): add local review artifact`.**

### Task 4: Decode-check before publishing clips

**Files:**
- Modify: `src/conference_video_cutter/media.py`
- Modify: `src/conference_video_cutter/cut.py`
- Modify: `tests/test_cut_cli.py`
- Modify: `tests/test_e2e.py`

**Interfaces:**
- `ensure_decodable(path: Path, label: str) -> None` runs FFmpeg with `-f null -`, never writes media, and raises an actionable `RuntimeError` on decode failure.
- Both `cut_one` and `render_project` invoke it after probing the staged output and before `os.replace`.

- [ ] **Step 1: Write a failing test** that calls `ensure_decodable` on a corrupt file and asserts an error.
- [ ] **Step 2: Run the focused test and confirm the missing function failure.**
- [ ] **Step 3: Implement the decode-only FFmpeg check with no shell interpolation.**
- [ ] **Step 4: Wire it into both atomic render paths and assert a failed stage leaves no final clip/manifest.**
- [ ] **Step 5: Run full tests, build the package, rerun the real red-team suite, and manually inspect the review HTML.**
- [ ] **Step 6: Commit `fix(cvc): decode-check staged clips`.**

### Final verification

- [ ] Run `PYTHONPATH=src .venv/bin/python -m pytest -q`.
- [ ] Run `.venv/bin/python -m build`.
- [ ] Run plugin and skill validators.
- [ ] Run `/home/totem/Work/conference-video-cutter-red-team-2026-09-19/red-team/run_red_team.py`.
- [ ] Check `git diff --check`, worktree status, installed plugin cachebuster, and real generated artifacts.

## Self-review

This plan deliberately does not implement diarization, cloud adapters, OCR, OTIO, cross-platform CI, or explicit transcoding. Those are separate subsystems with independent privacy and compatibility decisions. The tasks above close the immediate P0 gaps without changing the stream-copy contract.
