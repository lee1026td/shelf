"""Content parsers: HTML, Markdown, plain text, PDF -> ParsedDocument.

The dispatcher :func:`parse_document` picks a parser from the content type and/or
filename. Each parser is pure (bytes in, :class:`ParsedDocument` out) and therefore
fully testable with local fixtures - no network.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from urllib.parse import urlsplit

from shelf.errors import IngestionError, UnsupportedContentError
from shelf.ingestion.base import ParsedDocument

# filename extension -> internal kind
_EXT_KIND = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
    ".html": "html",
    ".htm": "html",
    ".pdf": "pdf",
}
SUPPORTED_EXTENSIONS = frozenset(_EXT_KIND)

# snapshot file extension per kind
KIND_EXTENSION = {"html": "html", "markdown": "md", "text": "txt", "pdf": "pdf"}

_BLANKS = re.compile(r"\n{3,}")


def detect_kind(content_type: str | None = None, filename: str | None = None) -> str:
    """Resolve the parser kind from a MIME content type and/or a filename."""
    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct in ("text/html", "application/xhtml+xml"):
            return "html"
        if ct == "application/pdf":
            return "pdf"
        if ct in ("text/markdown", "text/x-markdown"):
            return "markdown"
        if ct.startswith("text/"):
            return "text"
    if filename:
        # Strip any URL query/fragment before reading the extension, so
        # "https://cdn/report.pdf?v=2" still classifies as a PDF.
        ext = Path(urlsplit(filename).path or filename).suffix.lower()
        if ext in _EXT_KIND:
            return _EXT_KIND[ext]
    raise UnsupportedContentError(
        f"Unsupported content (content_type={content_type!r}, filename={filename!r}). "
        f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
    )


def parse_document(
    data: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> ParsedDocument:
    """Parse ``data`` into a :class:`ParsedDocument`, dispatching on kind."""
    kind = detect_kind(content_type, filename)
    if kind == "html":
        return parse_html(data)
    if kind == "pdf":
        return parse_pdf(data)
    if kind == "markdown":
        return parse_markdown(data, filename=filename)
    return parse_text(data, filename=filename)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _clean(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def parse_html(data: bytes) -> ParsedDocument:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    # Drop <title> too: html.parser does not synthesize a <body>, so for fragments
    # the container falls back to the whole soup and the title would leak into text.
    for tag in soup(["title", "script", "style", "noscript", "template"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    text = _clean(container.get_text(separator="\n"))
    if not title:
        heading = soup.find(["h1", "h2"])
        title = heading.get_text(strip=True) if heading else (text.split("\n", 1)[0] if text else "")
    return ParsedDocument(title=title or None, text=text, markdown=text, metadata={"kind": "html"})


def parse_markdown(data: bytes, filename: str | None = None) -> ParsedDocument:
    raw = _decode(data)
    title = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            break
        if stripped:
            title = stripped
            break
    if not title and filename:
        title = Path(filename).stem
    return ParsedDocument(
        title=title or None, text=_clean(raw), markdown=raw.strip(), metadata={"kind": "markdown"}
    )


def parse_text(data: bytes, filename: str | None = None) -> ParsedDocument:
    raw = _clean(_decode(data))
    title = raw.split("\n", 1)[0].strip() if raw else ""
    if not title and filename:
        title = Path(filename).stem
    return ParsedDocument(title=title or None, text=raw, markdown=raw, metadata={"kind": "text"})


def parse_pdf(data: bytes) -> ParsedDocument:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        # pypdf raises several unrelated exception types (PyPdfError, DependencyError,
        # OSError, ...). Wrap them all so callers get a clean IngestionError.
        raise IngestionError(f"Could not read PDF: {exc}") from exc
    text = _clean("\n\n".join(p for p in pages if p))
    title = ""
    try:
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip()
    except Exception:  # pragma: no cover - metadata is best-effort
        title = ""
    if not title and text:
        title = text.split("\n", 1)[0].strip()
    return ParsedDocument(
        title=title or None,
        text=text,
        markdown=text,
        metadata={"kind": "pdf", "pages": len(pages)},
    )
