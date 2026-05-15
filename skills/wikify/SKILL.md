---
name: wikify
description: Build, maintain, and query a persistent compounding markdown knowledge base in the spirit of Karpathy's LLM Wiki. Use when the user asks to create, build, or start a wiki / knowledge base / second brain; ingest, add, or process a source (URL, PDF, paste) into their wiki; ask a question against their wiki; lint, audit, or health-check their wiki; or references their "wiki", "knowledge base", "vault", or "notes" in a research context. Wiki location is auto-detected by walking up from cwd; init creates one at any project. Includes templates, a programmatic lint script, and Obsidian-compatible output.
---

# Wikify — Karpathy-style LLM Wiki

Build and maintain a persistent, compounding knowledge base as interlinked markdown files. Based on [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Unlike traditional RAG (which rediscovers knowledge from scratch every query), the wiki compiles knowledge once and keeps it current. Cross-references are already there. Contradictions have already been flagged. Synthesis reflects everything ingested.

**Division of labor:** the human curates sources and directs analysis. The agent summarizes, cross-references, files, and maintains consistency.

## Wiki Location

The wiki is auto-discovered by walking up from the current working directory. At each ancestor, the resolver checks the directory itself, then `wiki/`, `.wiki/`, `repos/wiki/`, and `docs/wiki/`. A directory is a wiki iff it contains `SCHEMA.md`, `index.md`, and `log.md`. First match wins.

To get the resolved path:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikify/scripts/wiki_resolver.py"
```

If the resolver can't find a wiki, do **not** silently default — surface the error and offer to initialize a new one (see "Initializing a New Wiki" below). The wiki is just a directory of markdown files — open it in Obsidian, VS Code, or any editor. No database, no special tooling required.

## Architecture: Three Layers

```
wiki/
├── SCHEMA.md           # Conventions, structure rules, domain config
├── index.md            # Sectioned content catalog with one-line summaries
├── log.md              # Chronological action log (append-only, rotated yearly)
├── raw/                # Layer 1: Immutable source material
│   ├── articles/       # Web articles, clippings
│   ├── papers/         # PDFs, arxiv papers
│   ├── transcripts/    # Meeting notes, interviews
│   └── assets/         # Images, diagrams referenced by sources
├── entities/           # Layer 2: Entity pages (people, orgs, products, models)
├── concepts/           # Layer 2: Concept/topic pages
├── comparisons/        # Layer 2: Side-by-side analyses
└── queries/            # Layer 2: Filed query results worth keeping
```

**Layer 1 — Raw Sources** (`raw/`): Immutable. Read but never modify. Corrections go in wiki pages.
**Layer 2 — The Wiki** (`entities/`, `concepts/`, `comparisons/`, `queries/`): Agent-owned markdown files. Created, updated, and cross-referenced by the agent.
**Layer 3 — The Schema** (`SCHEMA.md`): Defines structure, conventions, and tag taxonomy that constrain Layer 2.

## Resuming an Existing Wiki — do this every session

When the user has an existing wiki, **always orient before doing anything**:

1. Resolve the wiki path with `python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikify/scripts/wiki_resolver.py"`.
2. **Read `SCHEMA.md`** — domain, conventions, tag taxonomy.
3. **Read `index.md`** — what pages exist and their summaries.
4. **Read the tail of `log.md`** — last 20-30 entries to understand recent activity. Use the `Read` tool with an `offset` past the early lines rather than shelling out to `tail`.

Only after orientation should you ingest, query, or lint. Skipping this causes:

- Duplicate pages for entities that already exist
- Missed cross-references to existing content
- Contradictions with the schema's conventions
- Repeated work already logged

For wikis with 100+ pages, also `Grep` for the topic at hand before creating anything new.

## Initializing a New Wiki

When the user asks to create a wiki:

1. **Determine the path** — by default, create the wiki under the current project (e.g. `./wiki/`). Confirm the path with the user.
2. **Ask what domain the wiki covers** — be specific (e.g. "AI/ML research", "personal health", "competitor intelligence for fintech"). The schema will be tailored to this.
3. **Run `init_wiki.py`** to create the structure and seed the templates with today's date:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikify/scripts/init_wiki.py" PATH --domain "..."
```

The script creates the standard subdir tree (`raw/{articles,papers,transcripts,assets}`, `entities`, `concepts`, `comparisons`, `queries`), copies the three templates (`SCHEMA.md`, `index.md`, `log.md`) into the wiki root, and substitutes today's date for `YYYY-MM-DD` placeholders. It refuses to clobber an existing wiki.

4. **Edit `SCHEMA.md`** to replace the example tag taxonomy with one tailored to the user's domain. The domain line is filled in automatically when `--domain` is passed.
5. **Confirm** the wiki is ready and suggest first sources to ingest.

The tag taxonomy is the single biggest determinant of whether the wiki stays organized. Spend a few exchanges with the user getting it right — 10–20 top-level tags grouped into 3–5 categories.

## Page conventions (enforced by SCHEMA.md)

Every wiki page (Layer 2) starts with YAML frontmatter:

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [from-taxonomy-only]
sources: [raw/articles/source-name.md]
# Optional quality signals:
confidence: high | medium | low
contested: true                    # set when there are unresolved contradictions
contradictions: [other-page-slug]  # pages this one conflicts with
---
```

Raw sources (Layer 1) ALSO get a small frontmatter so re-ingests can detect drift:

```yaml
---
source_url: https://example.com/article
ingested: YYYY-MM-DD
sha256: <hex digest of body, computed below the closing --->
---
```

On re-ingest of the same URL: recompute the sha256, compare. Skip if identical, flag drift if different.

Cross-link aggressively with `[[wikilinks]]`. Every new or updated page must link to **at least 2 other pages**. Use only tags that exist in `SCHEMA.md` — if a new tag is needed, add it to the taxonomy first, then use it.

For pages that synthesize 3+ sources, append `^[raw/articles/source.md]` markers at the end of paragraphs whose claims trace to a specific source. This lets readers chase provenance without re-reading every raw file.

## Core Operation: Ingest

When the user provides a source (URL, file, or paste):

**1. Capture the raw source.**
- URL → `WebFetch` (or the `firecrawl-scrape` skill for JS-heavy pages) to get markdown, save to `raw/articles/`
- PDF → use the `Read` tool with `pages:` for local PDFs, save to `raw/papers/`
- Pasted text → save to appropriate `raw/` subdirectory
- Name descriptively: `raw/articles/karpathy-llm-wiki-2025.md`
- **Add raw frontmatter** (`source_url`, `ingested`, `sha256`). Compute the sha256 with the bundled helper — it matches `lint.py`'s drift check exactly:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikify/scripts/compute_body_sha256.py" raw/articles/source-name.md
  ```
  The helper hashes everything after the closing `---\n` of the frontmatter block (UTF-8 bytes, including any trailing newline at EOF).

**2. Discuss takeaways** with the user — what's interesting, what matters for the domain. (Skip in automated/cron contexts.)

**3. Check what already exists.** Read `index.md` and use the `Grep` tool over the wiki's `entities/`, `concepts/`, and `comparisons/` directories for entities/concepts the source mentions. This is the difference between a growing wiki and a pile of duplicates.

**4. Write or update wiki pages.**
- **New entity/concept page:** create only if it appears in 2+ sources OR is central to one source.
- **Existing pages:** add new info, update facts, bump `updated` date.
- **Cross-reference:** every new/updated page must link to ≥2 other pages.
- **Tags:** only from `SCHEMA.md` taxonomy. Add new tags to the taxonomy first.
- **Confidence:** for opinion-heavy, fast-moving, or single-source claims, set `confidence: medium` or `low`. Don't mark `high` unless multi-source corroborated.
- **Contradictions:** when new info conflicts with an existing page, note both positions with dates and sources, set `contested: true`, list the conflicting page in `contradictions:`.

**5. Update navigation.**
- Add new pages to `index.md` under the correct section, alphabetically.
- Update "Total pages" count and "Last updated" date in the index header.
- Append to `log.md`: `## [YYYY-MM-DD] ingest | Source Title`, listing every file created or updated.

**6. Report what changed** — list every file created or updated.

A single source can trigger updates across 5–15 wiki pages. This is normal and desired — it's the compounding effect.

**Bulk ingest:** when ingesting multiple sources at once, batch the work — read all sources first, identify all entities across all of them, do one search pass for existing pages, then create/update in one pass, then update `index.md` once and write a single batched log entry. **Ask before mass-updating** — if an ingest would touch 10+ existing pages, confirm scope with the user first.

## Core Operation: Query

When the user asks a question about the wiki's domain:

1. Read `index.md` to identify relevant pages.
2. For wikis with 100+ pages, also `Grep` across all `.md` files for key terms — the index alone may miss content.
3. `Read` the relevant pages.
4. Synthesize an answer. **Cite the wiki pages you drew from**: "Based on [[page-a]] and [[page-b]]…"
5. **File valuable answers back** — if the answer is a substantial comparison, deep dive, or novel synthesis, create a page in `queries/` or `comparisons/`. Don't file trivial lookups; only file answers that would be painful to re-derive.
6. Append a one-line entry to `log.md`: `## [YYYY-MM-DD] query | <question> [filed: queries/page.md | not filed]`.

## Core Operation: Lint

When the user asks to lint, audit, or health-check the wiki, **run the bundled script** — it auto-resolves the wiki via walk-up, no args required:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikify/scripts/lint.py"
```

Pass an explicit path as the first argument to lint a specific wiki.

The script reports, grouped by severity:

1. **Broken wikilinks** — `[[link]]` targets that don't resolve to a page
2. **Orphan pages** — wiki pages with zero inbound `[[wikilinks]]`
3. **Index drift** — pages on disk missing from `index.md`, or vice versa
4. **Frontmatter validation** — missing required fields, tags outside taxonomy
5. **Source drift** — `raw/` files whose recomputed sha256 differs from frontmatter
6. **Contested pages** — `contested: true` or `contradictions:` set
7. **Quality signals** — `confidence: low`, single-source pages without confidence
8. **Stale content** — pages whose `updated` is >90 days behind their newest cited source
9. **Page size** — pages over 200 lines (split candidates)
10. **Tag audit** — tags used outside the `SCHEMA.md` taxonomy
11. **Log rotation** — `log.md` over 500 entries (rotate to `log-YYYY.md`)

After running, present findings to the user with suggested actions, then append to `log.md`:
`## [YYYY-MM-DD] lint | N issues found`

For details on each check and how to fix issues, see [references/lint-checks.md](references/lint-checks.md).

## Page Thresholds (governed by SCHEMA.md)

- **Create a page** when an entity/concept appears in 2+ sources OR is central to one source
- **Add to existing page** when a source mentions something already covered
- **Don't create a page** for passing mentions, footnote names, or things outside the domain
- **Split a page** when it exceeds ~200 lines — break into sub-topics with cross-links
- **Archive a page** when fully superseded — move to `_archive/`, remove from index, replace inbound wikilinks with plain text + " (archived)"

## Pitfalls

- **Never modify files in `raw/`** — sources are immutable. Corrections go in wiki pages.
- **If walk-up can't find a wiki, do not silently default** — surface the resolver's error and offer to run `init_wiki.py`.
- **Always orient first** — read SCHEMA + index + recent log before any operation. Skipping this causes duplicates and missed cross-references.
- **Always update `index.md` and `log.md`** — they are the navigational backbone. Skipping this makes the wiki degrade.
- **Don't create pages for passing mentions** — follow the page thresholds.
- **Don't create pages without cross-references** — isolated pages are invisible. Every page links to ≥2 others.
- **Frontmatter is required** — it powers search, filtering, and staleness detection.
- **Tags must come from the taxonomy** — freeform tags decay into noise. Add to `SCHEMA.md` first, then use.
- **Keep pages scannable** — readable in 30 seconds. Split pages over 200 lines.
- **Ask before mass-updating** — confirm scope when an ingest would touch 10+ existing pages.
- **Handle contradictions explicitly** — never silently overwrite. Note both claims with dates, mark in frontmatter, flag for user review.
- **Rotate `log.md`** — when over 500 entries, rename to `log-YYYY.md` and start fresh.

## Obsidian Integration

The wiki directory works as an Obsidian vault out of the box (`[[wikilinks]]`, Graph View, Dataview queries). For setup details, including headless sync for server-resident wikis, see [references/obsidian-setup.md](references/obsidian-setup.md).

## Related Skills

- `firecrawl-scrape` / `firecrawl-search` — better than `WebFetch` for JS-rendered pages and structured search
- `firecrawl-crawl` / `firecrawl-download` — bulk-ingest a documentation site
- `generate-llms` — companion for generating `llms.txt` files; complementary, not overlapping
