# wikify

An LLM wiki skill for Claude Code and Claude Cowork — build, maintain, and query a persistent compounding markdown knowledge base in the spirit of [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Unlike RAG (which rediscovers knowledge from scratch every query), wikify compiles knowledge once and keeps it current. Cross-references are already there. Contradictions are already flagged. The wiki is just a directory of interlinked markdown files — open it in Obsidian, VS Code, or any editor.

## What it does

- **Ingest** sources (URLs, PDFs, pasted text) into raw immutable storage, then synthesize and cross-reference into entity and concept pages.
- **Query** the wiki and optionally file the answer back so it compounds.
- **Lint** the wiki — broken wikilinks, orphans, stale pages, schema drift, source drift via sha256.
- **Obsidian-compatible** out of the box — `[[wikilinks]]`, frontmatter, graph view.

## Install

In Claude Code, register this repo as a marketplace, then install the plugin:

```
/plugin marketplace add steve-goldberg/wikify
/plugin install wikify@wikify
```

Run `/reload-plugins` if the skill doesn't show up immediately.

## Usage

In any Claude Code session:

- "Create a wiki for AI/ML research"
- "Ingest https://example.com/article into my wiki"
- "What does my wiki say about transformers?"
- "Lint the wiki"

The skill auto-discovers an existing wiki by walking up from the current directory. If none is found, it offers to initialize one.

## Layout

```
wiki/
├── SCHEMA.md           # conventions, tag taxonomy
├── index.md            # content catalog
├── log.md              # append-only action log
├── raw/                # immutable source material
├── entities/           # entity pages
├── concepts/           # concept pages
├── comparisons/        # side-by-side analyses
└── queries/            # filed query results
```

## License

AGPL-3.0
