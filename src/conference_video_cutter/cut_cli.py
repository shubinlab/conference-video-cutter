from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from .cut import cut_one, snap_one
from .media import probe, render_project
from .output import validate_manifest
from .plan import load_project


def _text(lang: str, english: str, russian: str) -> str:
    return russian if lang == "ru" else english


def build_parser(lang: str = "en") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cvc-cut",
        description=_text(
            lang,
            "Stream-copy-only FFmpeg cutter for Conference Video Cutter.",
            "Нарезка Conference Video Cutter только через stream-copy.",
        ),
    )
    parser.add_argument("--lang", choices=("en", "ru"), default=lang)
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help=_text(lang, "inspect media with ffprobe", "проверить медиа через ffprobe"))
    probe_parser.add_argument("input", type=Path)
    probe_parser.add_argument("--json", action="store_true", dest="as_json")

    cut_parser = subparsers.add_parser("cut", help=_text(lang, "cut one interval with stream-copy", "нарезать один интервал через stream-copy"))
    cut_parser.add_argument("--input", type=Path, required=True)
    cut_parser.add_argument("--start", required=True, help="start time, seconds or HH:MM:SS")
    cut_parser.add_argument("--end", required=True, help="end time, seconds or HH:MM:SS")
    cut_parser.add_argument("--output", type=Path, required=True)
    cut_parser.add_argument("--force", action="store_true", help="replace an existing output")
    cut_parser.add_argument("--json", action="store_true", dest="as_json")

    snap_parser = subparsers.add_parser("snap", help=_text(lang, "snap boundaries using verified stream-copy", "подобрать границы через проверенный stream-copy"))
    snap_parser.add_argument("--input", type=Path, required=True)
    snap_parser.add_argument("--start", required=True, help="requested start time")
    snap_parser.add_argument("--end", required=True, help="requested end time")
    snap_parser.add_argument("--output", type=Path, required=True)
    snap_parser.add_argument("--window", type=float, default=0.25, help="maximum boundary shift in seconds")
    snap_parser.add_argument("--force", action="store_true", help="replace an existing output")
    snap_parser.add_argument("--json", action="store_true", dest="as_json")

    batch_parser = subparsers.add_parser("batch", help=_text(lang, "render a reviewed project with stream-copy", "нарезать проверенный проект через stream-copy"))
    batch_parser.add_argument("project", type=Path)
    batch_parser.add_argument("--force", action="store_true", help="replace existing project output")
    batch_parser.add_argument("--json", action="store_true", dest="as_json")

    verify_parser = subparsers.add_parser("verify", help=_text(lang, "verify output files and hashes", "проверить файлы и хэши результата"))
    verify_parser.add_argument("manifest", type=Path)
    verify_parser.add_argument("--strict", action="store_true", help="treat render warnings as errors")
    verify_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _print_result(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("output") or result.get("manifest") or json.dumps(result, ensure_ascii=False))
        warnings = result.get("warnings")
        if warnings:
            print(f"warnings: {len(warnings)}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    values = sys.argv[1:] if argv is None else argv
    lang = os.environ.get("CVC_LANG", "en")
    if "--lang" in values and values.index("--lang") + 1 < len(values):
        lang = values[values.index("--lang") + 1]
    args = build_parser(lang).parse_args(argv)
    try:
        if args.command == "probe":
            result = asdict(probe(args.input.resolve()))
            _print_result(result, args.as_json)
            return 0
        if args.command == "cut":
            result = cut_one(args.input, args.start, args.end, args.output, force=args.force)
            _print_result(result, args.as_json)
            return 0
        if args.command == "snap":
            result = snap_one(args.input, args.start, args.end, args.output, window=args.window, force=args.force)
            _print_result(result, args.as_json)
            return 0 if result["status"] == "snapped" else 1
        if args.command == "verify":
            result = validate_manifest(args.manifest, strict=args.strict)
            _print_result(result, args.as_json)
            return 0 if result["ok"] else 1
        project = load_project(args.project)
        manifest = render_project(project, force=args.force)
        result = {"manifest": str(project.output_dir / "manifest.json"), **manifest}
        _print_result(result, args.as_json)
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
