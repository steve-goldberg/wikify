#!/usr/bin/env python3
"""compute_body_sha256 — print the canonical sha256 of a raw/ file's body.

Usage:
    python3 compute_body_sha256.py FILE [FILE ...]

The "body" is the bytes from immediately after the closing `---\\n` of the
first frontmatter block to EOF, UTF-8 encoded. Matches lint.py's drift
check byte-for-byte. Use this when populating the `sha256:` frontmatter
field on a new raw/ source or refreshing it after a deliberate re-ingest.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint import sha256_of_body  # single source of truth — keeps helper and lint in lockstep


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: compute_body_sha256.py FILE [FILE ...]", file=sys.stderr)
        return 2
    rc = 0
    for arg in sys.argv[1:]:
        path = Path(arg).expanduser()
        if not path.is_file():
            print(f"error: {path} not a file", file=sys.stderr)
            rc = 1
            continue
        sha = sha256_of_body(path.read_text(encoding="utf-8"))
        print(f"{sha}  {path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
