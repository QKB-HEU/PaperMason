# PaperMason

**A local, catalog-first literature library for people and AI agents.**

PaperMason turns a folder of papers into a small, explicit index that an AI
agent can search before it reads source files. It works for any research
field: computer science, medicine, social science, humanities, and more.

It deliberately does **not** replace Zotero, download copyrighted papers, or
require an LLM API. Use Zotero (or any reference manager) for citations and
collections; use PaperMason when you want durable local Markdown, figures, and
a machine-readable route to the few papers relevant to a task.

## What problem it solves

A directory of PDFs and converted Markdown is readable to a person but opaque
to an AI: it does not know which files are relevant, whether an item is a
preprint, or where a figure belongs. PaperMason keeps a `library.jsonl` catalog
with one record per paper version. The correct retrieval pattern is:

```text
question -> catalog search -> select a small evidence set -> read those sources
```

The catalog is a routing layer, **not evidence**. An agent must still inspect
the chosen Markdown or PDF before it makes a factual claim.

## Features

- Local-first: PDF text and conversion artifacts stay on your computer.
- Converter-optional: searching, verifying, and cataloging existing Markdown
  require only Python's standard library. MinerU is an optional PDF converter,
  not a PaperMason dependency.
- Safe ingestion: checks exact PDF hashes, DOI, and arXiv identifiers before a
  conversion; external PDFs are copied by default rather than moved.
- Existing-library bootstrap: indexes your current Markdown and optionally
  links PDFs without renaming, moving, or rewriting either.
- Agent-friendly retrieval: stable, concise `search` output lets an agent open
  only the relevant source files.
- Portable layout: new libraries have neutral directory names; the older
  `INBOX/PDF/Markdown` layout is detected for backward compatibility.

## Install from zero

### 1. Install Python and uv

PaperMason supports Python 3.11+. The recommended installer is
[uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the terminal, then confirm the installation:

```bash
uv --version
```

On Windows, use the platform-specific installation command from uv's official
documentation instead of the shell command above.

### 2. Install PaperMason

After the first PyPI release:

```bash
uv tool install papermason
papermason --help
```

Until then, install directly from a GitHub release branch or clone:

```bash
uv tool install "git+https://github.com/<owner>/papermason.git"
papermason --help
```

For contributors working from a clone:

```bash
git clone https://github.com/<owner>/papermason.git
cd papermason
uv tool install .
papermason --help
```

`papermason --help` working is the only installation check required at this
stage. Do not install MinerU unless you want PaperMason to convert new PDFs.

## Start a new library

Choose a location outside the PaperMason source checkout:

```bash
papermason --library ~/Research/Papers init
```

This creates an empty, portable library:

```text
Papers/
├── inbox/          # optional landing place for PDFs
├── papers/         # PaperMason-managed PDF copies
├── markdown/       # one readable Markdown file per paper
├── assets/         # converter artifacts and local figures
└── library.jsonl   # one JSON record per paper version
```

No source PDF, Markdown, or image is uploaded anywhere.

## Choose your starting point

### I already have Markdown or a converter output folder

You do not need MinerU. First preview the catalog that would be built:

```bash
papermason --library ~/Research/Papers bootstrap \
  --markdown-dir ~/OldLibrary/markdown \
  --pdf-dir ~/OldLibrary/pdfs \
  --dry-run
```

If the record count and PDF links look right, run the same command without
`--dry-run`:

```bash
papermason --library ~/Research/Papers bootstrap \
  --markdown-dir ~/OldLibrary/markdown \
  --pdf-dir ~/OldLibrary/pdfs
```

Repeat `--markdown-dir` or `--pdf-dir` to join multiple collections. The
source folders stay where they are; PaperMason writes only `library.jsonl` and
its empty library layout. Files it cannot match are marked for review instead
of guessed.

### I have PDFs and want PaperMason to convert them

Install and test a local PDF-to-Markdown converter first. PaperMason supports
MinerU out of the box, but keeps it optional:

```bash
papermason --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --mineru /absolute/path/to/mineru \
  --label concise-paper-label \
  --dry-run
```

Review the proposed title, year, venue, filename, and duplicate status. Remove
`--dry-run` only when they are acceptable:

```bash
papermason --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --mineru /absolute/path/to/mineru \
  --label concise-paper-label
```

An external PDF is copied into `papers/`; the original remains in Downloads.
Put a PDF in `inbox/` when you want PaperMason to move it into the managed
library. Use `--move-source` only when you explicitly want an external source
file moved.

For another converter, pass a command template with literal `{pdf}` and
`{output}` placeholders. It must write exactly one Markdown file under the
output directory and keep local images reachable with relative paths:

```bash
papermason --library ~/Research/Papers ingest ~/Downloads/paper.pdf \
  --converter 'my-converter --input {pdf} --output {output}' \
  --label concise-paper-label
```

## Retrieve papers for an AI task

Search first, then open a small number of records:

```bash
papermason --library ~/Research/Papers search "causal inference"
papermason --library ~/Research/Papers verify
```

In Codex, install the bundled PaperMason plugin or use the repository-scoped
Skill at `.agents/skills/papermason`. It instructs the agent to search the
catalog before reading papers, to treat catalog fields as routing metadata
rather than proof, and to preserve library data by default.
The Skill itself has no Python, converter, cloud, or API-key dependency; the
optional `papermason` command merely makes its retrieval and maintenance steps
deterministic.

For a full reusable Codex installation, clone the repository and run:

```bash
codex plugin marketplace add /path/to/papermason
codex plugin add papermason@papermason
```

The plugin itself has no converter or Python dependency. It can guide
catalog-first retrieval by reading `library.jsonl`; install the CLI separately
only when you want deterministic `init`, `bootstrap`, `search`, `verify`, or
PDF-ingestion commands. For local development, Codex also discovers
`.agents/skills/papermason` automatically when launched from this repository.

Specialised writing extensions such as `tits-academic-writing` can use the
same catalog-first evidence protocol, but they remain separate from
PaperMason so its core stays discipline-neutral.

## Commands

| Command | Purpose | Needs a converter? |
| --- | --- | --- |
| `init` | Create an empty library layout and catalog | No |
| `bootstrap` | Index existing Markdown/PDF folders without changing them | No |
| `search QUERY` | Route a research question to candidate records | No |
| `verify` | Check catalog paths and local image links | No |
| `ingest PDF` | Convert one PDF, organize assets, and append a record | Yes |

Run `papermason <command> --help` for every option. `ingest --dry-run` is the
recommended first run for any new converter or PDF collection.

## Record format and privacy

`library.jsonl` uses one JSON object per line. Core fields include:

```json
{
  "paper_id": "2025-CVPR-Example",
  "title": "Example paper title",
  "year": 2025,
  "venue": "CVPR",
  "doi": "10.xxxx/example",
  "status": "published",
  "source_pdf": "papers/2025-CVPR-Example.pdf",
  "markdown": "markdown/2025-CVPR-Example.md",
  "artifact_dir": "assets/2025-CVPR-Example"
}
```

When a DOI is available, PaperMason asks Crossref only for bibliographic
metadata. It sends no PDF contents, extracted Markdown, catalog, or API key.
Missing or uncertain metadata is recorded for review rather than silently
invented.

Do not commit personal PDFs, converted papers, figure assets, or a private
catalog to a public repository. The supplied `.gitignore` excludes the default
library layout for that reason.

## Compatibility and safety

PaperMason detects the earlier layout:

```text
INBOX/  PDF/  Markdown/ALL_MARKDOWN/  Markdown/MINERU_OUTPUT/
```

and continues to index it without migration. Bootstrap never renames or
rewrites source Markdown. Ingestion converts in a temporary directory and only
adds the PDF, Markdown, artifacts, and catalog record after successful output
validation. It stops before conversion on an exact hash, DOI, or arXiv-ID
duplicate.

## Development

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution rules. The project is
MIT licensed; see [LICENSE](LICENSE).

## Acknowledgments

PaperMason is grateful to the projects and communities that make this workflow
possible:

- [OpenAI Codex](https://developers.openai.com/codex) for assistance with
  implementation, testing, documentation, and the reusable Skill/plugin
  workflow.
- [MinerU](https://github.com/opendatalab/MinerU) for the optional local
  PDF-to-Markdown conversion path.
- [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
  for DOI-based bibliographic metadata.
- [uv](https://docs.astral.sh/uv/) for reproducible Python packaging and
  development workflows.

These projects did not review or endorse PaperMason. PaperMason remains an
independent, local-first tool; users are responsible for complying with the
licenses and access conditions of their source materials and chosen converters.

## Community and responsible disclosure

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before participating.
Report security-sensitive local-file or converter issues according to
[SECURITY.md](SECURITY.md), not in a public issue.
