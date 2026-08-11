# Catalog contract

`library.jsonl` contains one JSON object per line. It is a searchable routing
index, not a bibliography manager and not proof for a research claim.

## Core record fields

| Field | Meaning |
| --- | --- |
| `paper_id` | Stable local identifier; usually `year-venue-label`, but bootstrap preserves existing filename stems. |
| `title`, `year`, `venue` | Bibliographic metadata; may be incomplete and require review. |
| `doi`, `arxiv_id`, `status` | Version and provenance cues; verify conflicts from original sources. |
| `source_pdf`, `markdown`, `artifact_dir`, `image_root` | Relative paths inside the library when possible, otherwise an explicit absolute local path. |
| `review_required`, `metadata_source` | Signals that a person or agent must check the metadata before relying on it. |
| `tags`, `abstract_excerpt` | Optional routing hints only. |

## Path rules

- Resolve relative record paths from the library root.
- Keep absolute paths only when bootstrapping an external collection; do not silently copy it just to make paths relative.
- A local image link must resolve relative to its Markdown file. Remote image URLs are neither errors nor local evidence.
- `verify` checks catalog paths and local image links. It does not verify that a paper's scientific claims are correct.

## Version rules

- Keep a preprint and a formal publication as distinct records until provenance establishes their relationship.
- Use an exact PDF hash for byte-identical duplicates.
- Treat matching DOI or arXiv ID as a stop-and-review condition for ingestion, not permission to delete an existing item.
- Prefer a formal version for citation when it is known to correspond to the preprint, but preserve accessible author manuscripts when licensing or access requires it.
