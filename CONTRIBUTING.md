# Contributing

Thank you for helping make local literature libraries more reliable.

## Before opening a pull request

1. Keep the core package free of mandatory cloud services, LLM APIs, and converter dependencies.
2. Do not add PDFs, converted documents, API keys, personal catalogs, or research-domain assumptions to the core workflow.
3. Add a test for every ingestion, bootstrap, or path-handling change.
4. Keep the PaperMason Skill general. Put venue- or discipline-specific writing advice in a separate Skill.
5. Run the test suite:

~~~bash
uv sync
uv run python -m unittest discover -s tests -v
uv build
~~~

## Scope

Small, reviewable improvements are preferred. Converter integrations should
preserve PaperMason's transaction boundary: parse in a temporary directory,
validate outputs, then move the PDF, Markdown, artifacts, and catalog record
into their final locations.
