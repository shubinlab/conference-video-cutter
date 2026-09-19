#!/usr/bin/env python3
"""Verify CVC output files, hashes, and render warnings."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from conference_video_cutter.output import validate_manifest as validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = validate(args.manifest, strict=args.strict)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"ok": False, "errors": [str(exc)], "warnings": []}
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("OK" if report.get("ok") else "FAILED")
        for error in report.get("errors", []):
            print(f"error: {error}")
        for warning in report.get("warnings", []):
            print(f"warning: {warning}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
