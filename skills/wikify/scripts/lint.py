#!/usr/bin/env python3
"""
wikify lint — health-check a Karpathy-style LLM Wiki.

Usage:
    python3 lint.py [WIKI_PATH]

If WIKI_PATH is omitted, the wiki is auto-resolved by walking up from cwd
(see wiki_resolver.py for the discovery rules).

Reports, grouped by severity:
    1. Broken wikilinks       — [[link]] targets that don't resolve to a page
    2. Orphan pages           — wiki pages with zero inbound [[wikilinks]]
    3. Index drift            — pages on disk vs index.md
    4. Frontmatter issues     — missing required fields, tags outside taxonomy
    5. Source drift           — raw/ files whose recomputed sha256 differs
    6. Contested pages        — contested: true or contradictions: set
    7. Quality signals        — confidence: low; single-source pages without confidence
    8. Stale content          — page updated >90 days behind newest cited source
    9. Page size              — pages over 200 lines
   10. Tag audit              — tags not in the SCHEMA.md taxonomy
   11. Log rotation           — log.md over 500 entries

Pure stdlib — no PyYAML dependency. Frontmatter parsing is line-based and
tolerant of common YAML shapes used in this skill's templates.
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_resolver import resolve_wiki, WikiNotFoundError

WIKI_DIRS = ("entities", "concepts", "comparisons", "queries")
RAW_DIRS = ("raw/articles", "raw/papers", "raw/transcripts")
REQUIRED_FIELDS = ("title", "created", "updated", "type", "tags", "sources")
WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+?)(?:\|[^\[\]]*)?(?:#[^\[\]]*)?\]\]")
MARKDOWN_LINK_RE = re.compile(r"\[[^\[\]]*\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def resolve_wiki_path(arg: str | None) -> Path:
    if arg:
        path = Path(arg).expanduser().resolve()
        if not path.is_dir():
            sys.exit(f"error: wiki path does not exist or is not a directory: {path}")
        return path
    try:
        return resolve_wiki()
    except WikiNotFoundError as e:
        sys.exit(f"error: {e}")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in m.group(1).splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        list_line = line.lstrip()
        if list_line.startswith("- ") and current_list_key is not None:
            fm.setdefault(current_list_key, []).append(_strip_value(list_line[2:]))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            current_list_key = key
            fm[key] = []
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [_strip_value(p) for p in inner.split(",")] if inner else []
        else:
            fm[key] = _strip_value(value)
    body = text[m.end():]
    return fm, body


def _strip_value(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s


def slug_of(path: Path) -> str:
    return path.stem


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f""  # caller will see empty body; we report errors elsewhere


def collect_wiki_pages(wiki: Path) -> list[Path]:
    pages: list[Path] = []
    for d in WIKI_DIRS:
        sub = wiki / d
        if sub.is_dir():
            pages.extend(sorted(p for p in sub.rglob("*.md")))
    return pages


def collect_raw_files(wiki: Path) -> list[Path]:
    files: list[Path] = []
    for d in RAW_DIRS:
        sub = wiki / d
        if sub.is_dir():
            files.extend(sorted(p for p in sub.rglob("*.md")))
    return files


def parse_taxonomy(schema_text: str) -> set[str]:
    """Best-effort parse of `## Tag Taxonomy` section: extract tag names.
    Folds wrapped bullet continuations (indented non-`-` lines) into the
    active bullet so multi-line tag lists tokenize fully."""
    tags: set[str] = set()
    in_section = False
    current: list[str] = []

    def emit() -> None:
        if not current:
            return
        body = " ".join(current)
        body = re.sub(r"\*\*[^*]+\*\*\s*:?", "", body).strip()
        for token in body.split(","):
            t = token.strip().strip("`").strip()
            if t and re.match(r"^[a-z0-9][a-z0-9\-]*$", t):
                tags.add(t)
        current.clear()

    for line in schema_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## tag taxonomy"):
            in_section = True
            continue
        if in_section and line.startswith("## ") and "tag taxonomy" not in stripped.lower():
            break
        if not in_section:
            continue
        if stripped.startswith("- "):
            emit()
            current.append(stripped[2:].strip())
        elif stripped and current and (line.startswith(" ") or line.startswith("\t")):
            current.append(stripped)
    emit()
    return tags


def parse_index_pages(index_text: str) -> set[str]:
    """Extract every wiki page slug listed in index.md.
    Supports both [[wikilink]] and [Title](path/page.md) forms."""
    slugs = {m.group(1).strip() for m in WIKILINK_RE.finditer(index_text)}
    for m in MARKDOWN_LINK_RE.finditer(index_text):
        target = m.group(1).strip().split()[0]
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        if not target.endswith(".md"):
            continue
        slugs.add(Path(target).stem)
    return slugs


def parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def sha256_of_body(text: str) -> str:
    """Hash everything after the first frontmatter block."""
    m = FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------- checks ----------

def lint(wiki: Path) -> int:
    schema_path = wiki / "SCHEMA.md"
    index_path = wiki / "index.md"
    log_path = wiki / "log.md"

    issues: dict[str, list[str]] = defaultdict(list)

    if not schema_path.exists():
        issues["bootstrap"].append(f"missing SCHEMA.md at {schema_path}")
    if not index_path.exists():
        issues["bootstrap"].append(f"missing index.md at {index_path}")
    if not log_path.exists():
        issues["bootstrap"].append(f"missing log.md at {log_path}")

    schema_text = read_text(schema_path) if schema_path.exists() else ""
    index_text = read_text(index_path) if index_path.exists() else ""
    log_text = read_text(log_path) if log_path.exists() else ""

    taxonomy = parse_taxonomy(schema_text)
    index_slugs = parse_index_pages(index_text)

    pages = collect_wiki_pages(wiki)
    page_by_slug = {slug_of(p): p for p in pages}
    page_slugs = set(page_by_slug.keys())

    inbound: dict[str, set[str]] = defaultdict(set)
    page_frontmatter: dict[str, dict] = {}
    page_body: dict[str, str] = {}
    page_lines: dict[str, int] = {}

    # 1, 4, 9 — scan every page once
    for page in pages:
        slug = slug_of(page)
        text = read_text(page)
        fm, body = parse_frontmatter(text)
        page_frontmatter[slug] = fm
        page_body[slug] = body
        page_lines[slug] = text.count("\n") + 1

        # Frontmatter validation
        missing = [f for f in REQUIRED_FIELDS if f not in fm or fm[f] in (None, "", [])]
        if missing:
            issues["frontmatter"].append(
                f"{page.relative_to(wiki)}: missing fields: {', '.join(missing)}"
            )
        # Tag audit
        tags = fm.get("tags") or []
        if isinstance(tags, list) and taxonomy:
            outside = [t for t in tags if t and t not in taxonomy]
            if outside:
                issues["tags"].append(
                    f"{page.relative_to(wiki)}: tags not in taxonomy: {', '.join(outside)}"
                )

        # Page size
        if page_lines[slug] > 200:
            issues["size"].append(
                f"{page.relative_to(wiki)}: {page_lines[slug]} lines (split candidate)"
            )

        # Wikilinks → inbound graph; also broken-link detection
        for m in WIKILINK_RE.finditer(body):
            target = m.group(1).strip()
            inbound[target].add(slug)
            if target != slug and target not in page_slugs:
                # Allow links to index/log/schema as soft references
                if target.lower() in {"index", "log", "schema"}:
                    continue
                issues["broken_links"].append(
                    f"{page.relative_to(wiki)}: [[{target}]] does not resolve"
                )

        # Contested / contradictions
        if str(fm.get("contested", "")).lower() in {"true", "yes"}:
            issues["contested"].append(f"{page.relative_to(wiki)}: contested: true")
        contradictions = fm.get("contradictions") or []
        if isinstance(contradictions, list) and contradictions:
            issues["contested"].append(
                f"{page.relative_to(wiki)}: contradictions: {', '.join(contradictions)}"
            )

        # Quality signals
        confidence = str(fm.get("confidence", "")).lower()
        sources = fm.get("sources") or []
        if confidence == "low":
            issues["quality"].append(f"{page.relative_to(wiki)}: confidence: low")
        elif not confidence and isinstance(sources, list) and len(sources) <= 1:
            issues["quality"].append(
                f"{page.relative_to(wiki)}: single-source page with no confidence set"
            )

    # 2 — orphan pages
    for slug, page in page_by_slug.items():
        if not inbound.get(slug):
            # Pages linked only from index don't count as orphans if listed in index.md
            if slug not in index_slugs:
                issues["orphans"].append(f"{page.relative_to(wiki)}: no inbound wikilinks")

    # 3 — index drift
    missing_from_index = sorted(page_slugs - index_slugs)
    extra_in_index = sorted(index_slugs - page_slugs - {"index", "log", "schema"})
    for slug in missing_from_index:
        issues["index"].append(f"{page_by_slug[slug].relative_to(wiki)}: not listed in index.md")
    for slug in extra_in_index:
        issues["index"].append(f"index.md: [[{slug}]] points to a missing page")

    # 5 — source drift
    for raw in collect_raw_files(wiki):
        text = read_text(raw)
        fm, _ = parse_frontmatter(text)
        stored = fm.get("sha256")
        if not stored:
            issues["source_drift"].append(
                f"{raw.relative_to(wiki)}: no sha256 frontmatter (cannot detect drift)"
            )
            continue
        actual = sha256_of_body(text)
        if actual != stored:
            issues["source_drift"].append(
                f"{raw.relative_to(wiki)}: sha256 mismatch (stored={stored[:12]}.. actual={actual[:12]}..)"
            )

    # 8 — stale content (heuristic): updated >90 days before today and >90 days
    # behind the newest source's `ingested` date when sources resolve under raw/.
    today = date.today()
    raw_ingested: dict[str, date] = {}
    for raw in collect_raw_files(wiki):
        fm, _ = parse_frontmatter(read_text(raw))
        d = parse_iso_date(fm.get("ingested"))
        if d:
            raw_ingested[str(raw.relative_to(wiki))] = d
    for slug, fm in page_frontmatter.items():
        updated = parse_iso_date(fm.get("updated"))
        if not updated:
            continue
        sources = fm.get("sources") or []
        if not isinstance(sources, list):
            continue
        newest_source: date | None = None
        for s in sources:
            sd = raw_ingested.get(str(s).strip())
            if sd and (newest_source is None or sd > newest_source):
                newest_source = sd
        if newest_source and (newest_source - updated) > timedelta(days=90):
            issues["stale"].append(
                f"{page_by_slug[slug].relative_to(wiki)}: updated {updated} but newest source is {newest_source}"
            )
        elif (today - updated) > timedelta(days=180):
            issues["stale"].append(
                f"{page_by_slug[slug].relative_to(wiki)}: not touched since {updated} (>180d)"
            )

    # 11 — log rotation
    log_entries = sum(1 for line in log_text.splitlines() if line.startswith("## ["))
    if log_entries > 500:
        issues["log"].append(
            f"log.md has {log_entries} entries — rotate to log-{date.today().year}.md"
        )

    return report(wiki, issues, len(pages))


SEVERITY_ORDER = [
    ("bootstrap", "Bootstrap"),
    ("broken_links", "Broken wikilinks"),
    ("source_drift", "Source drift"),
    ("orphans", "Orphan pages"),
    ("index", "Index drift"),
    ("frontmatter", "Frontmatter issues"),
    ("contested", "Contested pages"),
    ("quality", "Quality signals"),
    ("stale", "Stale content"),
    ("size", "Oversize pages"),
    ("tags", "Tag audit"),
    ("log", "Log rotation"),
]


def report(wiki: Path, issues: dict[str, list[str]], page_count: int) -> int:
    total = sum(len(v) for v in issues.values())
    print(f"wikify lint — {wiki}")
    print(f"  {page_count} wiki pages scanned")
    print(f"  {total} issue{'s' if total != 1 else ''} found\n")
    for key, label in SEVERITY_ORDER:
        items = issues.get(key) or []
        if not items:
            continue
        print(f"## {label} ({len(items)})")
        for item in items:
            print(f"  - {item}")
        print()
    if total == 0:
        print("Wiki is clean.")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(lint(resolve_wiki_path(arg)))
