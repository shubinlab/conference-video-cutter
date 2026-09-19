from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .i18n import message
from .media import probe, render_project
from .plan import load_project, validate_project
from .provenance import write_source_evidence
from .review import render_review_html
from .transcript import parse_srt, read_transcript, render_markdown


def build_parser(lang: str = "en") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cvc", description=message(lang, "description"))
    parser.add_argument("--lang", choices=("en", "ru"), default=lang)
    subparsers = parser.add_subparsers(dest="command")
    doctor = subparsers.add_parser("doctor", help=message(lang, "doctor_help"), description=message(lang, "doctor_help"))
    doctor.set_defaults(handler="doctor")
    evidence = subparsers.add_parser("evidence", help=message(lang, "evidence_help"))
    evidence.add_argument("project", type=Path, help=message(lang, "project_help"))
    evidence.add_argument("--output", type=Path, help="evidence JSON path")
    review = subparsers.add_parser("review", help=message(lang, "review_help"))
    review.add_argument("project", type=Path, help=message(lang, "project_help"))
    review.add_argument("--output", type=Path, help="review HTML path")
    init = subparsers.add_parser("init", help=message(lang, "init_help"), description=message(lang, "init_help"))
    init.add_argument("--input", type=Path, required=True, help=message(lang, "input_help"))
    init.add_argument("--output", type=Path, required=True, help=message(lang, "output_help"))
    validate = subparsers.add_parser("validate", help=message(lang, "validate_help"), description=message(lang, "validate_help"))
    validate.add_argument("project", type=Path, help=message(lang, "project_help"))
    transcript = subparsers.add_parser("transcript", help=message(lang, "transcript_help"), description=message(lang, "transcript_help"))
    transcript.add_argument("project", type=Path, help=message(lang, "project_help"))
    transcript.add_argument("--output", type=Path, help=message(lang, "transcript_output_help"))
    render = subparsers.add_parser("render", help=message(lang, "render_help"), description=message(lang, "render_help"))
    render.add_argument("project", type=Path, help=message(lang, "project_help"))
    render.add_argument("--force", action="store_true", help="replace existing output files")
    return parser


def main(argv: list[str] | None = None) -> int:
    values = argv or []
    lang = os.environ.get("CVC_LANG", "en")
    if "--lang" in values and values.index("--lang") + 1 < len(values):
        lang = values[values.index("--lang") + 1]
    parser = build_parser(lang)
    args = parser.parse_args(argv)
    if getattr(args, "command", None) == "doctor":
        missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
        if missing:
            print(message(args.lang, "missing_tools", tools=", ".join(missing)))
            return 1
        print(message(args.lang, "doctor_ok"))
        return 0
    if args.command == "init":
        output = args.output.resolve()
        source = args.input.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "language": args.lang,
                    "source": os.path.relpath(source, output.parent),
                    "transcript": "transcript.srt",
                    "output_dir": "output",
                    "copy_streams": True,
                    "speakers": {},
                    "segments": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(output)
        return 0
    project = load_project(args.project)
    if args.command == "evidence":
        output = args.output or project.output_dir / "source-evidence.json"
        write_source_evidence(project.source, output)
        print(output)
        return 0
    if args.command == "review":
        if project.transcript is None or not project.transcript.is_file():
            print(message(args.lang, "transcript_not_found", path=project.transcript), file=sys.stderr)
            return 1
        transcript_text, replaced = read_transcript(project.transcript)
        if replaced:
            print(message(args.lang, "transcript_decode_warning"), file=sys.stderr)
        output = args.output or project.output_dir / "review.html"
        render_review_html(project, parse_srt(transcript_text), output)
        print(output)
        return 0
    if args.command == "validate":
        duration = probe(project.source).duration if project.source.is_file() else None
        errors = validate_project(project, duration)
        if errors:
            print("\n".join(errors))
            return 1
        print(message(args.lang, "project_valid"))
        return 0
    if args.command == "transcript":
        if project.transcript is None or not project.transcript.is_file():
            print(message(args.lang, "transcript_not_found", path=project.transcript))
            return 1
        output = args.output or project.output_dir / "transcript.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        transcript_text, replaced = read_transcript(project.transcript)
        if replaced:
            print(message(args.lang, "transcript_decode_warning"), file=sys.stderr)
        output.write_text(render_markdown(project, parse_srt(transcript_text)), encoding="utf-8")
        print(output)
        return 0
    if args.command == "render":
        manifest = render_project(project, accurate=False, force=args.force)
        print(message(args.lang, "rendered", count=len(manifest["clips"])))
        if manifest["warnings"]:
            print(message(args.lang, "render_warnings", count=len(manifest["warnings"])))
        return 0
    if not getattr(args, "command", None):
        parser.print_help()
    return 0
