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
| `code` | Optional list of local implementation links for the paper. |

## Code links

Each `code` entry records one checked local Git repository:

| Field | Meaning |
| --- | --- |
| `local_path` | Absolute or library-relative repository path. |
| `repository_url`, `branch`, `commit` | Remote address and checked-out Git state at link time. |
| `relationship` | Usually `implementation`; retain a more specific value when known. |
| `match_evidence`, `readme`, `verified_at` | Why the repository was linked, README path, and check time. |

Use `papermeld link-code --code-root <root> --dry-run` to preview README/title and repository-name matches. Re-run without `--dry-run` to update links. `verify` checks every linked repository's path, remote address, and checkout.

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
