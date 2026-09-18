# Conference Video Cutter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Historical implementation record. The current plugin contract is provider-neutral/cloud-first; see the revised design spec.

**Goal:** Build a bilingual CLI and Codex plugin that converts a reviewed conference edit plan into a transcript and verified speaker/extra clips.

**Architecture:** A dependency-light Python package owns timecodes, plan validation, transcript grouping, bilingual messages, and FFmpeg command construction. External FFmpeg/FFprobe execution is isolated behind a small adapter; the Codex skill teaches evidence-first planning, visual checks, and safe rendering without embedding a conference-specific hardcoded script.

**Tech Stack:** Python 3.11+, stdlib `argparse`/`json`/`subprocess`/`pathlib`, FFmpeg/FFprobe, pytest, setuptools, Codex plugin manifest.

**Spec:** `docs/superpowers/specs/2026-09-18-conference-video-cutter-design.md`

## Global Constraints

- Keep the editing core dependency-light and provider-neutral; no cloud upload is required by the core.
- Support `en` and `ru`; preserve Unicode speaker names and source-language transcript text.
- Use half-open source intervals `[start, end)` and reject invalid or overlapping plans.
- Use FFmpeg stream copy by default; make accurate re-encoding explicit.
- Do not ship copyrighted conference media or transient URLs.
- Validate outputs with FFprobe and retain a JSON manifest.
- Use only the Python standard library at runtime in v0.1.

---

### Task 1: Package scaffold and bilingual CLI shell

**Files:**
- Create: `pyproject.toml`
- Create: `src/conference_video_cutter/__init__.py`
- Create: `src/conference_video_cutter/__main__.py`
- Create: `src/conference_video_cutter/i18n.py`
- Create: `src/conference_video_cutter/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces console entry point `cvc`.
- Produces `main(argv: list[str] | None = None) -> int`.
- Produces `message(lang: str, key: str, **values: object) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_doctor_help_is_bilingual(capsys):
    assert main(["--lang", "ru", "doctor", "--help"]) == 0
    assert "провер" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_doctor_help_is_bilingual -q`
Expected: FAIL because the package and `main` do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement argparse subcommands `init`, `validate`, `transcript`, `render`, and `doctor`; initially make each unsupported command return a localized, non-zero message while `doctor --help` and `doctor` work.

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_cli.py::test_doctor_help_is_bilingual -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests/test_cli.py
git commit -m "feat: scaffold bilingual cvc CLI"
```

### Task 2: Timecodes and validated edit plans

**Files:**
- Create: `src/conference_video_cutter/timecode.py`
- Create: `src/conference_video_cutter/models.py`
- Create: `src/conference_video_cutter/plan.py`
- Create: `tests/test_timecode.py`
- Create: `tests/test_plan.py`

**Interfaces:**
- `parse_time(value: str | int | float) -> float`.
- `format_time(seconds: float) -> str`.
- `load_project(path: Path) -> Project`.
- `validate_project(project: Project, duration: float | None = None) -> list[str]`.
- `speaker_segments(project: Project) -> list[Segment]`.
- `extra_segments(project: Project) -> list[Segment]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_time_accepts_hh_mm_ss():
    assert parse_time("01:02:03.5") == 3723.5

def test_validate_rejects_overlapping_segments(example_project):
    errors = validate_project(example_project.with_overlap())
    assert any("overlap" in error.lower() for error in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_timecode.py tests/test_plan.py -q`
Expected: FAIL because the functions and dataclasses do not exist.

- [ ] **Step 3: Write minimal implementation**

Use dataclasses and JSON only. Parse `HH:MM:SS`, `MM:SS`, numeric seconds, and reject negative/non-finite values. Validate unique IDs, positive ranges, speaker metadata, overlaps, and optional source duration.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_timecode.py tests/test_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/conference_video_cutter/timecode.py src/conference_video_cutter/models.py src/conference_video_cutter/plan.py tests/test_timecode.py tests/test_plan.py
git commit -m "feat: add validated conference edit plans"
```

### Task 3: Transcript grouping and Markdown output

**Files:**
- Create: `src/conference_video_cutter/transcript.py`
- Create: `tests/test_transcript.py`
- Modify: `src/conference_video_cutter/cli.py`

**Interfaces:**
- `parse_srt(text: str) -> list[TranscriptCue]`.
- `group_cues(cues: list[TranscriptCue], segments: list[Segment]) -> dict[str, list[TranscriptCue]]`.
- `render_markdown(project: Project, cues: list[TranscriptCue]) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_markdown_labels_qa_and_keeps_russian_text(example_project):
    markdown = render_markdown(example_project, cues_for_fixture())
    assert "Ответы на вопросы" in markdown
    assert "Арина Хромова" in markdown
    assert "Почему кейсы врут" in markdown
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_transcript.py::test_markdown_labels_qa_and_keeps_russian_text -q`
Expected: FAIL because transcript parsing/rendering is absent.

- [ ] **Step 3: Write minimal implementation**

Parse SRT timestamps, assign cues by half-open interval, preserve gaps as an `unassigned` note, and render a bilingual heading based on the project language. Do not rewrite names or transcript text in the core.

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_transcript.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/conference_video_cutter/transcript.py src/conference_video_cutter/cli.py tests/test_transcript.py
git commit -m "feat: render transcript by editorial blocks"
```

### Task 4: FFmpeg/FFprobe plan and stream-copy renderer

**Files:**
- Create: `src/conference_video_cutter/media.py`
- Create: `tests/test_media.py`
- Modify: `src/conference_video_cutter/cli.py`

**Interfaces:**
- `build_cut_command(source: Path, segment: Segment, output: Path, accurate: bool = False) -> list[str]`.
- `probe(path: Path) -> MediaInfo`.
- `render_project(project: Project, accurate: bool = False) -> Manifest`.

- [ ] **Step 1: Write the failing tests**

```python
def test_default_cut_uses_stream_copy(source, segment, output):
    command = build_cut_command(source, segment, output)
    assert "-c" in command and "copy" in command

def test_accurate_cut_does_not_use_stream_copy(source, segment, output):
    command = build_cut_command(source, segment, output, accurate=True)
    assert "-c:v" in command and "libx264" in command
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_media.py -q`
Expected: FAIL because media helpers are absent.

- [ ] **Step 3: Write minimal implementation**

Build safe argument lists without shell interpolation. Default to `-ss`, `-t`, `-map 0`, `-c copy`, and `-avoid_negative_ts make_zero`; accurate mode uses explicit H.264/AAC encoding. Probe duration and codecs with `ffprobe`; write manifest entries and warnings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_media.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/conference_video_cutter/media.py src/conference_video_cutter/cli.py tests/test_media.py
git commit -m "feat: render reviewed clips with ffmpeg"
```

### Task 5: Example project, end-to-end fixture, and validation command

**Files:**
- Create: `examples/demo/project.json`
- Create: `tests/fixtures/README.md`
- Create: `tests/test_e2e.py`
- Modify: `src/conference_video_cutter/cli.py`

**Interfaces:**
- `cvc init` writes a valid starter project with detected source duration.
- `cvc validate` exits 0 for the demo project and non-zero for an invalid plan.
- `cvc render` writes speaker clips, extras, and `manifest.json`.

- [ ] **Step 1: Write the failing test**

```python
def test_demo_project_validates_without_media():
    result = run_cli(["validate", "examples/demo/project.json"])
    assert result.returncode == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_e2e.py::test_demo_project_validates_without_media -q`
Expected: FAIL because the example project and command are absent.

- [ ] **Step 3: Write minimal implementation**

Add a small synthetic fixture recipe using FFmpeg’s `testsrc`/`sine` filters in test code, keep generated media under pytest temp directories, and make `init` write a project with explicit placeholders only in the example configuration—not in the plugin manifest.

- [ ] **Step 4: Run the end-to-end checks**

Run: `python -m pytest -q`
Expected: PASS, including a real FFmpeg stream-copy render when FFmpeg is installed; otherwise the media test reports a clear skip.

- [ ] **Step 5: Commit**

```bash
git add examples tests src/conference_video_cutter/cli.py
git commit -m "test: add demo project and media validation"
```

### Task 6: Codex plugin and bilingual product documentation

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `skills/conference-video-cutter/SKILL.md`
- Create: `README.md`
- Create: `README.ru.md`
- Create: `docs/research/2026-09-18-sources.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Plugin name: `conference-video-cutter`.
- Skill name: `conference-video-cutter`.
- README quick start works in both languages and links between language versions.

- [ ] **Step 1: Write the failing validation checks**

```bash
python3 path/to/plugin-creator/scripts/validate_plugin.py .
```

Expected: FAIL because `.codex-plugin/plugin.json` is absent.

- [ ] **Step 2: Run it to verify it fails**

Run the command above from the project root and record the missing-manifest error.

- [ ] **Step 3: Write the plugin and documentation**

Use the plugin scaffold schema, then describe the evidence-first workflow: inspect source, transcribe once, create/edit the plan, classify blocks, render with stream copy, inspect first/last frames, run FFprobe, and report unresolved names instead of guessing. Document Russian and English commands side by side.

- [ ] **Step 4: Run validation and CI locally**

Run: `python3 path/to/plugin-creator/scripts/validate_plugin.py . && python -m pytest -q && python -m compileall -q src`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "docs: publish bilingual Codex plugin workflow"
```

### Task 7: Repository review and publication

**Files:**
- Modify: any files needed after review

- [ ] **Step 1: Run the full verification set**

```bash
python -m pytest -q
python -m build
python3 path/to/plugin-creator/scripts/validate_plugin.py .
git diff --check
```

- [ ] **Step 2: Inspect the package artifact and clean tree**

Run: `python -m twine check dist/*` and `git status --short`; confirm no media, secrets, absolute workspace paths, model files, or transient URLs are present.

- [ ] **Step 3: Create the GitHub repository**

Run: `gh repo create shubinlab/conference-video-cutter --public --source=. --remote=origin --push` only after local verification passes.

- [ ] **Step 4: Verify the published repository**

Run: `git ls-remote --heads origin` and `gh repo view shubinlab/conference-video-cutter --json name,url,defaultBranchRef`; confirm the README renders and the default branch points to the verified commit.
