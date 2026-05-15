#!/usr/bin/env python3
"""
wikify wiki_resolver — locate the wiki directory for the current context.

Discovery: walk up from a starting directory through ancestors. At each
ancestor, check the directory itself and a small set of common subpaths.
First match wins. A directory IS a wiki iff it contains SCHEMA.md,
index.md, and log.md.

Usage:
    python3 wiki_resolver.py [START_DIR]

If START_DIR is omitted, uses the current working directory. Prints the
resolved wiki path to stdout. Exits non-zero with a helpful message on
miss.

Importable:
    from wiki_resolver import resolve_wiki, is_wiki, WikiNotFoundError
"""

from __future__ import annotations

import sys
from pathlib import Path

WIKI_SUBPATHS: tuple[str, ...] = ("", "wiki", ".wiki", "repos/wiki", "docs/wiki")
WIKI_MARKERS: tuple[str, ...] = ("SCHEMA.md", "index.md", "log.md")


class WikiNotFoundError(Exception):
    pass


def is_wiki(path: Path) -> bool:
    if not path.is_dir():
        return False
    return all((path / marker).is_file() for marker in WIKI_MARKERS)


def resolve_wiki(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd); return the first match."""
    cursor = (start or Path.cwd()).expanduser().resolve()
    home = Path.home().resolve()
    visited: list[Path] = []

    while True:
        visited.append(cursor)
        for subpath in WIKI_SUBPATHS:
            candidate = cursor / subpath if subpath else cursor
            if is_wiki(candidate):
                return candidate.resolve()
        if cursor == cursor.parent or cursor == home:
            break
        cursor = cursor.parent

    raise WikiNotFoundError(
        f"no wiki found walking up from {visited[0]} "
        f"(checked {len(visited)} ancestor{'s' if len(visited) != 1 else ''} "
        f"for subpaths: {', '.join(repr(s) or '.' for s in WIKI_SUBPATHS)}). "
        "Run init_wiki.py PATH to create one."
    )


def main() -> int:
    start = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        wiki = resolve_wiki(start)
    except WikiNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(wiki)
    return 0


if __name__ == "__main__":
    sys.exit(main())
