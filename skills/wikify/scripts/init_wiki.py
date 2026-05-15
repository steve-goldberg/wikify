#!/usr/bin/env python3
"""
wikify init_wiki — create a new wiki at PATH.

Usage:
    python3 init_wiki.py PATH [--domain "..."]

Creates the standard subdir tree, copies the three templates from this
skill's assets/ directory, and substitutes today's date for YYYY-MM-DD
placeholders in index.md and log.md. Refuses to clobber an existing
wiki (errors if PATH already contains SCHEMA.md).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from wiki_resolver import is_wiki

SUBDIRS = (
    "raw/articles",
    "raw/papers",
    "raw/transcripts",
    "raw/assets",
    "entities",
    "concepts",
    "comparisons",
    "queries",
)

TEMPLATES = (
    ("SCHEMA.md.template", "SCHEMA.md"),
    ("index.md.template", "index.md"),
    ("log.md.template", "log.md"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a wikify wiki at PATH.")
    parser.add_argument("path", type=Path, help="Wiki directory to create")
    parser.add_argument("--domain", default=None, help="One-line domain description")
    args = parser.parse_args()

    wiki = args.path.expanduser().resolve()
    if is_wiki(wiki):
        print(f"error: wiki already exists at {wiki}", file=sys.stderr)
        return 1
    if (wiki / "SCHEMA.md").exists():
        print(f"error: {wiki}/SCHEMA.md already exists; refusing to clobber", file=sys.stderr)
        return 1

    assets = Path(__file__).resolve().parent.parent / "assets"
    for template, _ in TEMPLATES:
        if not (assets / template).is_file():
            print(f"error: missing template {assets / template}", file=sys.stderr)
            return 1

    wiki.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (wiki / sub).mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    for template, dest_name in TEMPLATES:
        src = assets / template
        dest = wiki / dest_name
        text = src.read_text(encoding="utf-8")
        if dest_name in ("index.md", "log.md"):
            text = text.replace("YYYY-MM-DD", today)
        dest.write_text(text, encoding="utf-8")

    if args.domain:
        schema = wiki / "SCHEMA.md"
        schema_text = schema.read_text(encoding="utf-8")
        marker = "[REPLACE: One sentence describing what this wiki covers."
        if marker in schema_text:
            end_marker = '"Competitor and market intelligence for the consumer fintech space."]'
            start = schema_text.index(marker)
            end = schema_text.index(end_marker, start) + len(end_marker)
            schema_text = schema_text[:start] + args.domain + schema_text[end:]
            schema.write_text(schema_text, encoding="utf-8")

        log = wiki / "log.md"
        log_text = log.read_text(encoding="utf-8")
        log_text = log_text.replace(
            "[REPLACE with the domain set in SCHEMA.md]", args.domain
        )
        log.write_text(log_text, encoding="utf-8")

    print(f"initialized wiki at {wiki}")
    if not args.domain:
        print("next: edit SCHEMA.md to set the domain and tag taxonomy")
    else:
        print("next: edit SCHEMA.md to fill in the tag taxonomy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
