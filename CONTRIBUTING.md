# Contributing

Thanks for helping make conference editing more reproducible and less error-prone.

## Principles

- Keep the core dependency-light and the transcription boundary provider-neutral. Local ASR is optional; no provider may be assumed or invoked silently.
- Treat the transcript and reviewed JSON plan as inspectable evidence.
- Preserve both English and Russian user paths when changing CLI or documentation.
- Prefer explicit failures over silently damaged clips.
- Do not add conference media, private transcripts, cookies, tokens, or personal data to the repository.
- Treat `scripts/` as user-facing tools: keep them standalone, deterministic, no-upload by default, and test their JSON output.

## Development

```bash
uv venv .venv
uv pip install --python .venv/bin/python pytest build
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m build
python3 /home/totem/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
git diff --check
```

The media end-to-end test creates a synthetic video at runtime. Real recordings belong outside Git.

## Pull requests

Explain the user-visible behavior, the evidence or tests used, and any trade-off in FFmpeg behavior. Include updated English and Russian documentation for user-facing changes.
