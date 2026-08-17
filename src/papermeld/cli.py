"""PaperMeld command-line interface."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")
HTML_IMAGE_RE = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)(\2)", re.IGNORECASE)
KNOWN_VENUES = tuple(sorted((
    "Applied-Intelligence", "Information-Fusion", "ACM-MM", "RA-L", "ICCVW", "CVPRW", "ECCVW",
    "AISTATS", "NeurIPS", "InfoFusion", "arXiv", "TPAMI", "TITS", "TIV", "CVPR",
    "ICCV", "ECCV", "ICRA", "ITSC", "IROS", "ICLR", "CoRL", "AAAI", "ESWA", "ACCV",
    "ASE", "PRL", "ETSI", "WACV", "IV",
), key=len, reverse=True))


class PaperMeldError(RuntimeError):
    pass


class Library:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        # v0.1 used the author's ``INBOX/PDF/Markdown/ALL_MARKDOWN`` layout.
        # Continue to recognise it, but do not impose an academic-domain layout
        # on new libraries.  A new library is deliberately boring and portable.
        self.legacy_layout = any((self.root / name).exists() for name in ("INBOX", "PDF", "Markdown"))
        if self.legacy_layout:
            self.inbox = self.root / "INBOX"
            self.pdfs = self.root / "PDF"
            self.markdown = self.root / "Markdown" / "ALL_MARKDOWN"
            self.assets = self.root / "Markdown" / "MINERU_OUTPUT"
        else:
            self.inbox = self.root / "inbox"
            self.pdfs = self.root / "papers"
            self.markdown = self.root / "markdown"
            self.assets = self.root / "assets"
        self.catalog = self.root / "library.jsonl"

    def initialize(self) -> None:
        for directory in (self.inbox, self.pdfs, self.markdown, self.assets):
            directory.mkdir(parents=True, exist_ok=True)
        self.catalog.touch(exist_ok=True)

    def records(self) -> list[dict]:
        if not self.catalog.exists():
            return []
        result = []
        for number, line in enumerate(self.catalog.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise PaperMeldError(f"Invalid catalog line {number}: {error}") from error
        return result

    def append(self, record: dict) -> None:
        with self.catalog.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def replace_records(self, records: list[dict]) -> None:
        self.catalog.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.catalog.with_name(self.catalog.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(temporary, self.catalog)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def catalog_path(library: Library, path: Path | None) -> str | None:
    """Store a relative path when possible, otherwise preserve an absolute path."""
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(library.root))
    except ValueError:
        return str(path.resolve())


def resolve_catalog_path(library: Library, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else library.root / path


def slug(value: str, fallback: str) -> str:
    value = value.replace("++", "PlusPlus")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return value[:80] or fallback


def pdf_text(pdf: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def crossref(doi: str) -> dict | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "PaperMeld/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            message = json.loads(response.read().decode("utf-8"))["message"]
    except Exception:
        return None
    date_parts = None
    for key in ("published-print", "published-online", "issued", "created"):
        date_parts = message.get(key, {}).get("date-parts")
        if date_parts:
            break
    return {
        "title": (message.get("title") or [""])[0].strip(),
        "venue_raw": (message.get("container-title") or [""])[0].strip(),
        "year": date_parts[0][0] if date_parts and date_parts[0] else None,
    }


def venue_alias(value: str) -> str:
    aliases = (
        ("computer vision and pattern recognition", "CVPR"),
        ("international conference on computer vision", "ICCV"),
        ("european conference on computer vision", "ECCV"),
        ("robotics and automation letters", "RA-L"),
        ("international conference on robotics and automation", "ICRA"),
        ("intelligent transportation systems", "TITS"),
        ("intelligent vehicles", "TIV"),
        ("pattern analysis and machine intelligence", "TPAMI"),
        ("conference on robot learning", "CoRL"),
        ("neural information processing systems", "NeurIPS"),
        ("learning representations", "ICLR"),
        ("intelligent transportation systems conference", "ITSC"),
        ("intelligent robots and systems", "IROS"),
        ("expert systems with applications", "ESWA"),
    )
    normalized = value.lower()
    for needle, alias in aliases:
        if needle in normalized:
            return alias
    return slug(value, "Unresolved")


def fallback_title(pdf: Path) -> str:
    stem = re.sub(r"^(?:19|20)\d{2}[-_ ]+", "", pdf.stem)
    return re.sub(r"\s+", " ", stem.replace("_", " ")).strip()


def filename_year(pdf: Path) -> int | None:
    match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", pdf.stem)
    return int(match.group(1)) if match else None


def arxiv_year(arxiv_id: str | None) -> int | None:
    match = re.fullmatch(r"(\d{2})\d{2}\.\d{4,5}", arxiv_id or "")
    return 2000 + int(match.group(1)) if match else None


def venue_from_names(*values: str) -> str | None:
    workshop_aliases = (
        (r"\bCVPR\s+(?:\d{4}\s+)?Workshop\b", "CVPRW"),
        (r"\bICCV\s+(?:\d{4}\s+)?Workshop\b", "ICCVW"),
        (r"\bECCV\s+(?:\d{4}\s+)?Workshop\b", "ECCVW"),
    )
    for pattern, venue in workshop_aliases:
        if any(re.search(pattern, value, re.IGNORECASE) for value in values if value):
            return venue
    matches = {
        venue
        for venue in KNOWN_VENUES
        if any(re.search(rf"(?<![A-Za-z0-9]){re.escape(venue)}(?![A-Za-z0-9])", value, re.IGNORECASE) for value in values if value)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def clean_label(value: str, venue: str | None = None) -> str:
    value = re.sub(r"^(?:19|20)\d{2}[-_ ]+", "", value).strip()
    if venue:
        value = re.sub(rf"^{re.escape(venue)}[-_ ]+", "", value, flags=re.IGNORECASE).strip()
    return value


def infer_handle(title: str) -> tuple[str, bool]:
    official = re.match(r"\s*([A-Za-z][A-Za-z0-9+.-]{1,40})\s*:", title)
    if official:
        return slug(official.group(1), "Untitled"), True
    leading = re.match(r"\s*([A-Za-z][A-Za-z0-9+.-]{2,40})\b", title)
    return (slug(leading.group(1), "Untitled"), False) if leading else ("Untitled", False)


def metadata(pdf: Path, args: argparse.Namespace) -> dict:
    text = pdf_text(pdf)
    raw_doi = args.doi or next(iter(DOI_RE.findall(text)), None)
    doi = raw_doi.rstrip(".,;:)]}>").lower() if raw_doi else None
    arxiv_id = args.arxiv or next(iter(ARXIV_RE.findall(text)), None)
    remote = crossref(doi) if doi else None
    title = args.title or (remote or {}).get("title") or fallback_title(pdf)
    year = args.year or (remote or {}).get("year") or filename_year(pdf) or arxiv_year(arxiv_id) or dt.date.today().year
    filename_venue = venue_from_names(pdf.stem, args.label or "")
    document_venue = venue_from_names(text[:6000])
    inferred_venue = venue_alias((remote or {}).get("venue_raw", "")) if remote else None
    venue = args.venue or inferred_venue or filename_venue or document_venue or ("arXiv" if arxiv_id else "Unresolved")
    handle, official_handle = infer_handle(title)
    label = clean_label(args.label or handle, venue)
    paper_id = args.paper_id or f"{year}-{venue}-{slug(label, 'Untitled')}"
    return {
        "paper_id": paper_id,
        "title": title,
        "year": int(year),
        "venue": venue,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "status": "published" if doi and venue != "Unresolved" else "preprint" if arxiv_id else "needs_review",
        "review_required": venue == "Unresolved" or (not official_handle and not args.label),
        "metadata_source": "doi" if doi else "arxiv" if arxiv_id else "filename",
        "label": label,
    }


def check_duplicates(records: list[dict], digest: str, meta: dict) -> None:
    for record in records:
        if record.get("sha256") == digest:
            raise PaperMeldError(f"Exact PDF duplicate of {record['paper_id']}; conversion was not started.")
        if meta.get("doi") and record.get("doi") == meta["doi"]:
            raise PaperMeldError(f"DOI already belongs to {record['paper_id']}; conversion was not started.")
        if meta.get("arxiv_id") and record.get("arxiv_id") == meta["arxiv_id"]:
            raise PaperMeldError(f"arXiv ID already belongs to {record['paper_id']}; review versions before ingesting.")


def find_conversion_output(staging: Path) -> tuple[Path, Path]:
    """Locate one Markdown result from MinerU or another local converter."""
    candidates = sorted(path for path in staging.rglob("*.md") if not path.name.startswith("."))
    if len(candidates) != 1:
        raise PaperMeldError(f"Expected exactly one converted Markdown file, found {len(candidates)}.")
    markdown = candidates[0]
    # Preserve MinerU's outer source folder; generic converters use the
    # Markdown directory itself as their artifact bundle.
    if markdown.parent.name in {"hybrid_auto", "auto", "ocr", "txt"}:
        return markdown.parent.parent, markdown
    return markdown.parent, markdown


def markdown_destinations(text: str) -> list[str]:
    values = [match.group(2).strip() for match in IMAGE_RE.finditer(text)]
    values.extend(match.group(3).strip() for match in HTML_IMAGE_RE.finditer(text))
    result = []
    for value in values:
        if value.startswith("<") and value.endswith(">"):
            value = value[1:-1]
        result.append(value)
    return result


def abstract_excerpt(text: str) -> str:
    start = re.search(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:abstract|a\s+b\s+s\s+t\s+r\s+a\s+c\s+t)\b\s*[-—:.]?\s*",
        text,
    )
    if not start:
        return ""
    end = re.search(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:(?:\d+|[IVXLCDM]+)\.?\s*)?introduction\b|^\s*(?:#{1,6}\s*)?(?:keywords?|index\s+terms?)\b",
        text[start.end():],
    )
    excerpt = text[start.end():start.end() + end.start() if end else start.end() + 2400]
    return re.sub(r"\s+", " ", excerpt).strip()[:1200]


def infer_tags(text: str, title: str) -> list[str]:
    """Use author-supplied keywords instead of imposing a domain taxonomy."""
    match = re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:keywords?|index\s+terms?)\s*[:—-]\s*(.+)$", text)
    if not match:
        return []
    tags = []
    for item in re.split(r"[,;·•]", match.group(1)):
        value = re.sub(r"\s+", " ", item).strip(" .;:,—-")
        normalized = slug(value.lower(), "")
        if normalized and normalized not in tags:
            tags.append(normalized)
    return tags[:12]


def paper_id_parts(paper_id: str) -> tuple[int | None, str, str]:
    match = re.match(r"^((?:19|20)\d{2})-(.+)$", paper_id)
    if not match:
        # Bootstrap must accept a user's existing filenames.  The catalog is an
        # index, not a renaming command.
        return None, "Unresolved", slug(paper_id, "Untitled")
    year, remainder = int(match.group(1)), match.group(2)
    for venue in KNOWN_VENUES:
        if remainder.startswith(venue + "-"):
            return year, venue, remainder[len(venue) + 1:]
    venue, separator, handle = remainder.partition("-")
    if not separator or not handle:
        return year, "Unresolved", slug(remainder, "Untitled")
    return year, venue, handle


def bundle_from_markdown(library: Library, markdown: Path, text: str) -> tuple[Path | None, Path | None]:
    for value in markdown_destinations(text):
        if value.startswith(("http://", "https://", "data:", "#")):
            continue
        image = (markdown.parent / value).resolve()
        if not image.is_file():
            continue
        # Converters commonly use ``images/``, but existing human-maintained
        # libraries may use ``figures/``, ``media/``, or another local folder.
        images_dir = next((parent for parent in (image.parent, *image.parents) if parent.name == "images"), image.parent)
        try:
            relative = images_dir.relative_to(library.assets)
        except ValueError:
            # An existing library may keep figures alongside Markdown or in a
            # converter-specific folder outside PaperMeld.  Index it without
            # moving it; the record can safely carry an absolute reference.
            return images_dir.parent, images_dir
        return library.assets / relative.parts[0], images_dir
    return None, None


def markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if len(title) >= 12:
                return title
    return fallback


def enrich_metadata_from_markdown(meta: dict, source: Path, text: str, args: argparse.Namespace) -> dict:
    enriched = dict(meta)
    title = markdown_title(text, meta["title"])
    handle, official_handle = infer_handle(title)
    enriched["title"] = title
    markdown_venue = venue_from_names(text[:8000])
    if enriched["venue"] == "Unresolved" and markdown_venue:
        enriched["venue"] = markdown_venue
        enriched["metadata_source"] = "markdown-front-matter"
        enriched["status"] = "published"
    if official_handle and (not args.label or args.label == source.stem):
        enriched["label"] = handle
    else:
        enriched["label"] = clean_label(enriched["label"], enriched["venue"])
    if not args.paper_id:
        enriched["paper_id"] = f"{enriched['year']}-{enriched['venue']}-{slug(enriched['label'], 'Untitled')}"
    enriched["review_required"] = enriched["venue"] == "Unresolved" or (not official_handle and not args.label)
    return enriched


def source_pdf_for_bundle(library: Library, bundle: Path | None, paper_id: str, title: str, pdf_roots: list[Path]) -> Path | None:
    if bundle is not None:
        direct = library.pdfs / f"{bundle.name}.pdf"
        if direct.is_file():
            return direct
        origin = next(iter(sorted(bundle.rglob("*_origin.pdf"))), None)
        if origin is not None:
            return origin
    _, _, handle = paper_id_parts(paper_id)
    normalized_handle = re.sub(r"[^a-z0-9]", "", handle.lower())
    candidates = [path for root in pdf_roots if root.is_dir() for path in sorted(root.rglob("*.pdf"))]
    direct = next((path for path in candidates if normalized_handle and normalized_handle in re.sub(r"[^a-z0-9]", "", path.stem.lower())), None)
    if direct is not None:
        return direct
    normalized_title = re.sub(r"[^a-z0-9]", "", title.lower())
    if len(normalized_title) < 12:
        return None
    return next((path for path in candidates if normalized_title in re.sub(r"[^a-z0-9]", "", pdf_text(path).lower())), None)


def bootstrap_record(library: Library, markdown: Path, collection: str, pdf_roots: list[Path]) -> dict:
    text = markdown.read_text(encoding="utf-8", errors="strict")
    year, venue, handle = paper_id_parts(markdown.stem)
    bundle, images_dir = bundle_from_markdown(library, markdown, text)
    title_source = bundle.name if bundle is not None else handle
    fallback = re.sub(r"^(?:19|20)\d{2}[-_ ]+", "", title_source).replace("_", " ").replace("-", " ")
    title = markdown_title(text, fallback)
    source_pdf = source_pdf_for_bundle(library, bundle, markdown.stem, title, pdf_roots)
    doi_match = next(iter(DOI_RE.findall(text)), None)
    arxiv_match = next(iter(ARXIV_RE.findall(text)), None)
    return {
        "schema_version": 1,
        "paper_id": markdown.stem,
        "title": title,
        "year": year,
        "venue": venue,
        "doi": doi_match.rstrip(".,;:)]}>").lower() if doi_match else None,
        "arxiv_id": arxiv_match,
        "status": "preprint" if venue == "arXiv" else "published" if doi_match else "needs_review",
        "review_required": source_pdf is None,
        "metadata_source": "bootstrap",
        "collection": collection,
        "model_names": [handle],
        "tags": infer_tags(text, title),
        "abstract_excerpt": abstract_excerpt(text),
        "sha256": sha256(source_pdf) if source_pdf is not None else None,
        "source_pdf": catalog_path(library, source_pdf),
        "markdown": catalog_path(library, markdown),
        "artifact_dir": catalog_path(library, bundle),
        "image_root": catalog_path(library, images_dir),
        "image_mode": "local" if images_dir is not None else "remote-or-none",
        "added_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def unique_paths(paths: list[Path]) -> list[Path]:
    result = []
    seen = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            result.append(resolved)
            seen.add(resolved)
    return result


def markdown_sources(library: Library, supplied: list[Path] | None) -> list[tuple[Path, str]]:
    roots = supplied or [library.markdown]
    if not supplied and library.legacy_layout:
        legacy_tits = library.root / "Markdown" / "TITS_MARKDOWN"
        if legacy_tits.is_dir():
            roots.append(legacy_tits)
    result = []
    for root in unique_paths(roots):
        if not root.is_dir():
            raise PaperMeldError(f"Markdown directory does not exist: {root}")
        try:
            collection = str(root.relative_to(library.root))
        except ValueError:
            collection = root.name
        for path in sorted(root.rglob("*.md")):
            if library.assets not in path.parents:
                result.append((path, collection))
    return result


def bootstrap(args: argparse.Namespace) -> int:
    library = Library(args.library)
    sources = markdown_sources(library, args.markdown_dir)
    if not sources:
        raise PaperMeldError("No Markdown files found. Pass one or more --markdown-dir paths if this is an existing collection.")
    default_pdf_roots = [library.pdfs]
    legacy_tits_pdfs = library.root / "TITS"
    if library.legacy_layout and legacy_tits_pdfs.is_dir():
        default_pdf_roots.append(legacy_tits_pdfs)
    pdf_roots = unique_paths(args.pdf_dir or default_pdf_roots)
    records = [bootstrap_record(library, path, collection, pdf_roots) for path, collection in sources]
    ids = [record["paper_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise PaperMeldError("Duplicate paper IDs across Markdown collections; resolve before bootstrapping.")
    linked = sum(record["source_pdf"] is not None for record in records)
    local_images = sum(record["image_root"] is not None for record in records)
    print(f"Bootstrap plan: {len(records)} records; PDFs linked: {linked}; local image roots: {local_images}; review required: {len(records) - linked}")
    if args.dry_run:
        print("Dry run complete; catalog was not written.")
        return 0
    if library.catalog.exists() and library.catalog.read_text(encoding="utf-8").strip() and not args.overwrite:
        raise PaperMeldError("library.jsonl is not empty; refuse to replace it. Use --overwrite only after backing it up.")
    library.initialize()
    temporary = library.catalog.with_name(library.catalog.name + ".bootstrap-tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, library.catalog)
    print(f"Bootstrapped {len(records)} records into {library.catalog}")
    return 0


def migrate_images(text: str, source_md: Path, bundle: Path, final_bundle: Path, final_md: Path) -> str:
    def replacement(value: str) -> str | None:
        raw = value.strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if not raw.startswith(("images/", "./images/")):
            return None
        source = (source_md.parent / (raw[2:] if raw.startswith("./") else raw)).resolve()
        if not source.is_file():
            raise PaperMeldError(f"Converted Markdown refers to a missing image: {raw}")
        final_image = final_bundle / source.relative_to(bundle.resolve())
        return "<" + os.path.relpath(final_image, final_md.parent).replace(os.sep, "/") + ">"

    def markdown_replace(match: re.Match[str]) -> str:
        value = replacement(match.group(2))
        return match.group(0) if value is None else match.group(1) + value + match.group(3)

    def html_replace(match: re.Match[str]) -> str:
        value = replacement(match.group(3))
        return match.group(0) if value is None else match.group(1) + match.group(2) + value + match.group(4)

    return HTML_IMAGE_RE.sub(html_replace, IMAGE_RE.sub(markdown_replace, text))


def call_converter(source: Path, staging: Path, args: argparse.Namespace) -> None:
    if args.gpu is not None and not args.gpu.strip():
        raise PaperMeldError("--gpu must be a non-empty CUDA device selection; omit --gpu to let MinerU choose.")
    if args.converter:
        try:
            command = [part.format(pdf=str(source), output=str(staging)) for part in shlex.split(args.converter)]
        except ValueError as error:
            raise PaperMeldError("Invalid --converter template. Use {pdf} and {output} placeholders.") from error
        if not command:
            raise PaperMeldError("--converter must not be empty.")
        print("Running converter:", " ".join(command))
        subprocess.run(command, check=True)
        return
    mineru = args.mineru or shutil.which("mineru")
    if not mineru:
        raise PaperMeldError("No converter is configured. Install MinerU, provide --mineru, or pass --converter 'command {pdf} {output}'.")
    command = [mineru, "-p", str(source), "-o", str(staging), "--backend", args.backend, "--method", args.method]
    if args.backend == "hybrid-engine":
        command.extend(["--effort", args.effort])
    environment = os.environ.copy()
    if args.gpu is not None:
        environment["CUDA_VISIBLE_DEVICES"] = args.gpu.strip()
    print("Running MinerU:", " ".join(command))
    subprocess.run(command, check=True, env=environment)


def ingest(args: argparse.Namespace) -> int:
    library = Library(args.library)
    library.initialize()
    source = Path(args.pdf).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise PaperMeldError("ingest accepts exactly one existing PDF.")
    try:
        source.relative_to(library.inbox.resolve())
        source_is_inbox = True
    except ValueError:
        # Files outside the library are read-only inputs by default.  This is
        # friendlier for a Downloads folder while still supporting INBOX flows.
        source_is_inbox = False
    digest = sha256(source)
    meta = metadata(source, args)
    check_duplicates(library.records(), digest, meta)
    provisional_markdown = library.markdown / f"{meta['paper_id']}.md"
    print(json.dumps({**meta, "source": str(source), "markdown": str(provisional_markdown)}, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("Dry run complete; conversion was not started and no files changed.")
        return 0
    with tempfile.TemporaryDirectory(prefix="papermeld-", dir=library.inbox) as temporary:
        staging = Path(temporary)
        call_converter(source, staging, args)
        bundle, generated = find_conversion_output(staging)
        generated_markdown = generated.read_text(encoding="utf-8")
        meta = enrich_metadata_from_markdown(meta, source, generated_markdown, args)
        final_pdf = library.pdfs / f"{meta['paper_id']}.pdf"
        final_md = library.markdown / f"{meta['paper_id']}.md"
        final_bundle = library.assets / meta["paper_id"]
        if any(path.exists() for path in (final_pdf, final_md, final_bundle)):
            raise PaperMeldError(f"Destination already exists for {meta['paper_id']}; use --paper-id to resolve it.")
        markdown = migrate_images(generated_markdown, generated, bundle, final_bundle, final_md)
        temporary_markdown = library.markdown / f".{meta['paper_id']}.tmp"
        temporary_markdown.write_text(markdown, encoding="utf-8")
        try:
            os.replace(bundle, final_bundle)
            if source_is_inbox or args.move_source:
                os.replace(source, final_pdf)
            else:
                shutil.copy2(source, final_pdf)
            os.replace(temporary_markdown, final_md)
        finally:
            if temporary_markdown.exists():
                temporary_markdown.unlink()
    record = {
        "schema_version": 1,
        **meta,
        "model_names": [meta["label"]],
        "tags": infer_tags(markdown, meta["title"]),
        "abstract_excerpt": abstract_excerpt(markdown),
        "sha256": digest,
        "source_pdf": catalog_path(library, final_pdf),
        "markdown": catalog_path(library, final_md),
        "artifact_dir": catalog_path(library, final_bundle),
        "image_root": catalog_path(library, final_bundle / generated.parent.relative_to(bundle) / "images") if (final_bundle / generated.parent.relative_to(bundle) / "images").is_dir() else None,
        "image_mode": "local" if (final_bundle / generated.parent.relative_to(bundle) / "images").is_dir() else "none",
        "added_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    library.append(record)
    print(f"Ingested {meta['paper_id']}; review_required={meta['review_required']}")
    return 0


def search(args: argparse.Namespace) -> int:
    records = Library(args.library).records()
    query = args.query.lower()
    matches = [record for record in records if query in json.dumps(record, ensure_ascii=False).lower()]
    for record in matches:
        print(f"{record['paper_id']}\t{record.get('venue', '')}\t{record.get('title', '')}\t{record.get('markdown', '')}")
    print(f"{len(matches)} match(es)")
    return 0


def git_output(repository: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_repositories(root: Path) -> list[Path]:
    repositories = []
    for current, directories, files in os.walk(root):
        if ".git" in directories or ".git" in files:
            repositories.append(Path(current).resolve())
            directories[:] = []
    return sorted(repositories)


def repository_readme(repository: Path) -> tuple[Path | None, str]:
    candidates = sorted(
        path for path in repository.iterdir()
        if path.is_file() and path.name.lower().startswith("readme")
    )
    if not candidates:
        return None, ""
    readme = candidates[0]
    return readme, readme.read_text(encoding="utf-8", errors="replace")[:1_000_000]


def match_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def readme_heading_text(text: str) -> str:
    headings = []
    for line in text.splitlines()[:80]:
        if re.match(r"\s*#{1,3}\s+", line) or re.search(r"<h[1-3][^>]*>", line, re.IGNORECASE):
            headings.append(re.sub(r"<[^>]+>", " ", line))
    return " ".join(headings)


def repository_metadata(repository: Path) -> dict:
    readme, readme_text = repository_readme(repository)
    return {
        "local_path": str(repository),
        "repository_url": git_output(repository, "remote", "get-url", "origin"),
        "branch": git_output(repository, "branch", "--show-current"),
        "commit": git_output(repository, "rev-parse", "HEAD"),
        "readme": str(readme.relative_to(repository)) if readme is not None else None,
        "_readme_text": readme_text,
    }


def code_match_evidence(record: dict, repository: Path, readme_text: str) -> list[str]:
    readme = match_text(readme_text)
    repository_name = match_text(repository.name)
    repository_variants = {repository_name, repository_name.rstrip("0123456789")}
    headings = match_text(readme_heading_text(readme_text))
    evidence = []
    title = match_text(str(record.get("title") or ""))
    if len(title) >= 16 and title in headings:
        evidence.append("title")
    for model in record.get("model_names") or []:
        normalized = match_text(str(model))
        if len(normalized) < 4:
            continue
        if normalized in repository_variants:
            evidence.append("repository_name")
        if normalized in readme and ("title" in evidence or "repository_name" in evidence):
            evidence.append("model_name")
    return list(dict.fromkeys(evidence))


def link_code(args: argparse.Namespace) -> int:
    library = Library(args.library)
    code_root = args.code_root.expanduser().resolve()
    if not code_root.is_dir():
        raise PaperMeldError(f"Code root does not exist: {code_root}")
    records = library.records()
    if not records:
        raise PaperMeldError("library.jsonl is empty; catalog papers before linking code.")
    repositories = git_repositories(code_root)
    links = []
    for repository in repositories:
        metadata = repository_metadata(repository)
        for record in records:
            evidence = code_match_evidence(record, repository, metadata["_readme_text"])
            if not evidence:
                continue
            link = {key: value for key, value in metadata.items() if key != "_readme_text"}
            link.update({
                "relationship": "implementation",
                "match_evidence": evidence,
                "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            })
            links.append((record["paper_id"], link))
    print(f"Code-link plan: {len(repositories)} repositories scanned; {len(links)} paper-code link(s) found.")
    for paper_id, link in links:
        print(f"{paper_id}\t{link['local_path']}\t{','.join(link['match_evidence'])}")
    if args.dry_run:
        print("Dry run complete; catalog was not changed.")
        return 0
    by_paper = {paper_id: [] for paper_id, _ in links}
    for paper_id, link in links:
        by_paper[paper_id].append(link)
    changed = 0
    for record in records:
        discovered = by_paper.get(record.get("paper_id"), [])
        if not discovered:
            continue
        existing = record.get("code") or []
        retained = [
            link for link in existing
            if not any(link.get("local_path") == candidate["local_path"] for candidate in discovered)
        ]
        record["code"] = retained + discovered
        changed += 1
    library.replace_records(records)
    print(f"Linked {len(links)} repository relation(s) to {changed} paper record(s).")
    return 0


def verify(args: argparse.Namespace) -> int:
    library = Library(args.library)
    problems = []
    local_images = 0
    code_links = 0
    records = library.records()
    for record in records:
        paper_id = record.get("paper_id", "<missing paper_id>")
        for field in ("source_pdf", "markdown", "artifact_dir", "mineru_dir"):
            value = record.get(field)
            if value and not resolve_catalog_path(library, value).exists():
                problems.append(f"{paper_id}: missing {field}: {value}")
        markdown_value = record.get("markdown")
        markdown_path = resolve_catalog_path(library, markdown_value) if markdown_value else None
        if record.get("image_mode") == "local" and markdown_path and markdown_path.is_file():
            markdown = markdown_path
            for destination in markdown_destinations(markdown.read_text(encoding="utf-8", errors="strict")):
                if destination.startswith(("../", "./", "images/")):
                    local_images += 1
                    if not (markdown.parent / destination).resolve().is_file():
                        problems.append(f"{paper_id}: broken image link: {destination}")
        code = record.get("code") or []
        if not isinstance(code, list):
            problems.append(f"{paper_id}: code must be a list")
            continue
        for link in code:
            code_links += 1
            local_path = link.get("local_path")
            if not local_path:
                problems.append(f"{paper_id}: code link is missing local_path")
                continue
            repository = resolve_catalog_path(library, local_path)
            if not repository.is_dir() or not (repository / ".git").exists():
                problems.append(f"{paper_id}: missing Git repository: {local_path}")
                continue
            expected_origin = link.get("repository_url")
            actual_origin = git_output(repository, "remote", "get-url", "origin")
            if expected_origin and actual_origin != expected_origin:
                problems.append(f"{paper_id}: code origin changed: {local_path}")
            expected_commit = link.get("commit")
            actual_commit = git_output(repository, "rev-parse", "HEAD")
            if expected_commit and actual_commit != expected_commit:
                problems.append(f"{paper_id}: code checkout changed: {local_path}")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"Verified {len(records)} catalog record(s), {local_images} local image link(s), and {code_links} code link(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="papermeld", description="Build a local, catalog-first literature library for people and AI agents.")
    parser.add_argument("--library", type=Path, default=Path.cwd(), help="Library root; default is current directory.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a portable library layout and library.jsonl.")
    init.set_defaults(handler=lambda args: (Library(args.library).initialize(), print(f"Initialized {args.library.resolve()}"), 0)[2])
    add = sub.add_parser("ingest", help="Convert one PDF and append its catalog record.")
    add.add_argument("pdf")
    add.add_argument("--dry-run", action="store_true")
    add.add_argument("--doi")
    add.add_argument("--arxiv")
    add.add_argument("--title")
    add.add_argument("--year", type=int)
    add.add_argument("--venue", help="Venue identifier, such as Nature or CVPR.")
    add.add_argument("--label", "--model", dest="label", help="Short stable label used in the filename; --model is retained as an alias.")
    add.add_argument("--paper-id", help="Complete output stem, such as 2025-Venue-ShortLabel.")
    add.add_argument("--move-source", action="store_true", help="Move an external input PDF after a successful conversion instead of copying it.")
    add.add_argument("--converter", help="Optional converter template with {pdf} and {output}, for example 'my-converter {pdf} {output}'.")
    add.add_argument("--mineru", help="Absolute MinerU executable when it is not on PATH; used when --converter is omitted.")
    add.add_argument("--backend", choices=("pipeline", "hybrid-engine", "vlm-engine"), default="pipeline")
    add.add_argument("--method", choices=("auto", "txt", "ocr"), default="auto")
    add.add_argument("--effort", choices=("medium", "high"), default="medium")
    add.add_argument("--gpu", help="CUDA_VISIBLE_DEVICES for a GPU backend.")
    add.set_defaults(handler=ingest)
    bootstrap_parser = sub.add_parser("bootstrap", help="Catalog existing Markdown without moving or rewriting it.")
    bootstrap_parser.add_argument("--dry-run", action="store_true")
    bootstrap_parser.add_argument("--overwrite", action="store_true", help="Replace a nonempty catalog after you have backed it up.")
    bootstrap_parser.add_argument("--markdown-dir", type=Path, action="append", help="Markdown directory to catalog; repeat for multiple collections.")
    bootstrap_parser.add_argument("--pdf-dir", type=Path, action="append", help="PDF directory to link when safe; repeat for multiple roots.")
    bootstrap_parser.set_defaults(handler=bootstrap)
    find = sub.add_parser("search", help="Search structured catalog metadata.")
    find.add_argument("query")
    find.set_defaults(handler=search)
    code = sub.add_parser("link-code", help="Link local Git repositories to cataloged papers from README evidence.")
    code.add_argument("--code-root", type=Path, required=True, help="Directory containing local Git repositories.")
    code.add_argument("--dry-run", action="store_true", help="Print discovered links without changing library.jsonl.")
    code.set_defaults(handler=link_code)
    check = sub.add_parser("verify", help="Verify catalog paths.")
    check.set_defaults(handler=verify)
    return parser


def main() -> None:
    try:
        args = build_parser().parse_args()
        raise SystemExit(args.handler(args))
    except PaperMeldError as error:
        print(f"papermeld: {error}", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.CalledProcessError as error:
        print(f"papermeld: converter failed with exit code {error.returncode}; no catalog record was written.", file=sys.stderr)
        raise SystemExit(error.returncode)


if __name__ == "__main__":
    main()
