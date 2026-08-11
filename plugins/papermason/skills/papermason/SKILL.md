---
name: papermason
description: Build, maintain, retrieve, and audit a local catalog-first literature library with PaperMason. Use when Codex needs to organize PDFs or converted Markdown, bootstrap an existing paper folder, diagnose broken Markdown image links, find a small evidence set for a research question, or help an AI use library.jsonl without scanning every paper. Works across research fields and can operate read-only without PaperMason, MinerU, cloud services, or API keys.
---

# PaperMason — Codex Skill

Treat a paper library as two layers: a compact catalog for routing and original
Markdown/PDF/figure files for evidence. Use `library.jsonl` to decide what to
open; never use a title, tag, abstract excerpt, or filename as factual proof.

## Start with discovery

1. Ask for or locate the library root. Look for `library.jsonl` first.
2. If the `papermason` command is available, run `papermason --library <root> search <query>` or `verify` as appropriate. If it is not installed, inspect `library.jsonl` directly; do not block a read-only research task on an installation.
3. Read [references/catalog-contract.md](references/catalog-contract.md) before editing a catalog or deciding whether a path is a valid local record.
4. Report the observed layout, catalog record count, unresolved records, and any assumptions before proposing a structural change.

## Choose the narrowest workflow

### Retrieve evidence for a question or writing task

1. Extract 2–4 precise concepts from the task: problem, setting, method family, limitation, or venue.
2. Search one focused query at a time. Rank records by title, tags, abstract excerpt, status, and source paths.
3. Select the smallest viable evidence set—normally 3–8 papers, not the entire library.
4. Open the relevant section, page, or figure in each selected source. Record a source card with its path, version, precise claim, and location.
5. State evidence gaps explicitly. Hand the source cards to a domain writing skill when one applies; for example, use `tits-academic-writing` for a TITS Introduction rather than pretending PaperMason supplies venue-specific rhetoric.

### Bootstrap an existing collection

Use bootstrap when Markdown and PDFs already exist. First run a dry-run. Pass every Markdown root and PDF root explicitly if they lie outside the library root. Bootstrap may create the library layout and catalog, but must not rename, move, delete, or rewrite the source collection.

```bash
papermason --library <library-root> bootstrap \
  --markdown-dir <markdown-root> \
  --pdf-dir <pdf-root> \
  --dry-run
```

Check duplicate `paper_id` values and links before rerunning without `--dry-run`. Never use `--overwrite` until the existing catalog has been inspected and backed up.

### Ingest one new PDF

Use `ingest` only after a converter has been separately installed and tested. The core catalog workflow does not require MinerU. Preview metadata and duplicate detection first:

```bash
papermason --library <library-root> ingest <input.pdf> --label <short-label> --dry-run
```

Remove `--dry-run` only after the user has reviewed title, year, venue, identifier, and destination. An arbitrary external PDF is copied by default. A PDF in `inbox/` is managed by the library. Moving an external source requires the explicit `--move-source` flag.

For non-MinerU converters, use a command template containing literal `{pdf}` and `{output}` placeholders. The converter must generate exactly one Markdown file below its output directory. Read [references/converter-boundary.md](references/converter-boundary.md) before diagnosing a converter integration or image migration.

### Repair or audit a library

Run `verify` before proposing a repair. Classify failures as missing source material, an invalid catalog path, a converter-output/image-link mismatch, or a duplicate/version conflict. Prefer a narrowly scoped reversible repair. Do not mass-rewrite Markdown image paths, mass-delete apparent duplicates, or re-bootstrap a nonempty catalog without direct authorization and a backup.

## Non-negotiable rules

- Preserve the user's PDFs, Markdown, images, annotations, and reference-manager data unless the user explicitly authorizes a modification.
- Do not claim a preprint and formal publication are duplicates solely because their titles resemble each other. Verify DOI, arXiv ID, authors, or the actual document.
- Do not let a catalog search replace source inspection or citation checking.
- Keep personal library data out of a public repository. Share an empty example library or synthetic fixtures instead.
- Do not require a cloud service, embedding database, LLM API, GPU, or PDF converter for catalog search and evidence routing.
- Separate general library behavior from domain writing behavior. Keep TITS, medicine, law, or other specialised advice in an extension Skill.

## Deliverables

- Retrieval: a short candidate table, selected source cards, and stated gaps.
- Bootstrap/ingest: a dry-run summary, intended changes, user-confirmed metadata, and post-run verification result.
- Audit: the exact broken records, failure category, safe repair options, and what was not changed.
- Open-source setup: minimal prerequisites, a fresh-install path, a fresh-library path, and a test command proven in a clean directory.

## Resources

- [references/catalog-contract.md](references/catalog-contract.md): catalog fields, path rules, and evidence boundary.
- [references/converter-boundary.md](references/converter-boundary.md): converter contract, transactional import, and image-link checks.
