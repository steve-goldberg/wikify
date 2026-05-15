# Lint checks — what each one means and how to fix

Reference for the bundled `scripts/lint.py` script. The script reports issues
grouped by severity. Use this guide to triage.

## Severity order

1. **Bootstrap** — wiki is missing required top-level files (SCHEMA / index / log)
2. **Broken wikilinks** — link targets don't resolve
3. **Source drift** — `raw/` content has changed under us
4. **Orphan pages** — pages with no inbound wikilinks
5. **Index drift** — disk and `index.md` disagree
6. **Frontmatter issues** — required fields missing
7. **Contested pages** — explicit unresolved contradictions
8. **Quality signals** — low-confidence or weakly-sourced pages
9. **Stale content** — pages that haven't been touched since their sources updated
10. **Oversize pages** — pages over 200 lines
11. **Tag audit** — tags used outside the taxonomy
12. **Log rotation** — `log.md` over 500 entries

## Bootstrap

`SCHEMA.md`, `index.md`, or `log.md` is missing. The wiki cannot be linted
meaningfully without all three. Restore from `assets/*.template` in this skill.

## Broken wikilinks

`[[some-page]]` doesn't resolve to a `.md` file in any wiki subdirectory.
Causes:
- Page was renamed without updating inbound links
- Typo in the wikilink
- Page was archived without replacing inbound links with plain text

Fix: rename the link, fix the typo, or replace with plain text + ` (archived)`.

## Source drift

A file in `raw/` has frontmatter `sha256:` set, but recomputing the hash on
the body yields a different value. Possible causes:
- A human edited the raw source (shouldn't happen — `raw/` is immutable)
- The source URL was re-ingested but the new content overwrote without
  refreshing the hash
- File corruption

Fix: investigate the diff. If the change is intentional, recompute the hash and
update frontmatter; otherwise restore from version control.

## Orphan pages

A wiki page has zero inbound `[[wikilinks]]` from any other page (the index
counts as a directory listing, not a real inbound link, but a page that's
listed in the index is given the benefit of the doubt and not flagged here).

Fix: either find natural places to link to it from related pages, merge it
into a sibling page, or archive it. Isolated pages are invisible.

## Index drift

`index.md` and the filesystem disagree:
- **Pages on disk missing from index** — add them under the correct section
- **Index entries pointing to nonexistent pages** — remove the entry, or
  restore the page

Fix: bring `index.md` into agreement with the disk. Update the "Total pages"
count and "Last updated" date in the header.

## Frontmatter issues

A page is missing required fields (`title`, `created`, `updated`, `type`,
`tags`, `sources`). Required because lint, search, and staleness detection
all depend on frontmatter being present and valid.

Fix: add the missing fields. Use today's date for `updated`; the original
creation date if you can find it (e.g. from `git log --diff-filter=A`),
otherwise today.

## Contested pages

Page has `contested: true` or a non-empty `contradictions:` list. The agent
has flagged unresolved tension between sources. **Do not silently resolve.**
Bring the contradictions to the user, present both claims with dates and
sources, and let the user decide.

Fix: after the user picks a position, update the page, remove the
`contested` flag, and log the resolution.

## Quality signals

- `confidence: low` — the page itself acknowledges weak support
- Single-source page with no `confidence:` field — could be `medium` or `low`
  but the agent never set it, leaving it implicitly `high` by absence

Fix: corroborate with additional sources to upgrade confidence; or set the
field explicitly to `medium` / `low`. Don't leave it ambiguous.

## Stale content

Two heuristics fire:
- `updated` on the page is >90 days behind the newest source the page cites
  (the source has been updated but the page hasn't synthesized it)
- `updated` on the page is >180 days old in absolute terms (the page may
  reflect a stale state of the world)

Fix: re-read the cited sources, refresh the page, bump `updated`. If the
page is still accurate, just bump `updated` with no content change to
acknowledge the review.

## Oversize pages

Page has more than 200 lines. A wiki page should be readable in 30 seconds.

Fix: split into focused sub-pages with cross-links, or move detailed
analysis into a dedicated deep-dive page that the parent links to.

## Tag audit

A page uses a tag not declared in `SCHEMA.md`'s **Tag Taxonomy** section.

Fix: either rename the tag to an existing one, or — if the new tag is
genuinely needed — add it to the taxonomy in `SCHEMA.md` first, then
re-run lint.

## Log rotation

`log.md` has more than 500 `## [YYYY-MM-DD]` entries.

Fix: rename `log.md` to `log-YYYY.md` (use the year of the oldest remaining
entry), then create a new empty `log.md` from `assets/log.md.template`.
Old logs stay in the wiki for history.

## After running lint

Always append a one-line summary to `log.md`:

```
## [YYYY-MM-DD] lint | N issues found
- broken_links: 3
- orphans: 2
- ...
```

This makes it easy to track wiki health over time.
