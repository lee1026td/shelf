"""Test fixtures/helpers shared across ingestion tests."""

from __future__ import annotations

from shelf.ingestion.base import FetchResult
from shelf.util import utc_now_iso


def make_minimal_pdf(text: str = "Hello PDF") -> bytes:
    """Build a tiny but valid single-page PDF whose text extracts via pypdf."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("latin-1") + b") Tj ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objs) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF"
    )
    return bytes(out)


class FakeFetcher:
    """A network-free :class:`Fetcher` returning canned bytes."""

    def __init__(self, raw: bytes, content_type: str = "text/html", status: int = 200) -> None:
        self.raw = raw
        self.content_type = content_type
        self.status = status

    def fetch(self, url: str) -> FetchResult:
        return FetchResult(
            url=url,
            status=self.status,
            content_type=self.content_type,
            raw=self.raw,
            fetched_at=utc_now_iso(),
        )


class FakeChatClient:
    """A network-free :class:`ChatClient` for the ModelGateway."""

    def __init__(self, reply: str = "canned answer", embedding=(0.1, 0.2)) -> None:
        self.reply = reply
        self.embedding = list(embedding)
        self.calls: list = []

    def chat(self, base_url, model, messages, *, api_key=None, max_tokens=512, temperature=0.2):
        self.calls.append((base_url, model, messages))
        return self.reply

    def embeddings(self, base_url, model, texts, *, api_key=None):
        return [self.embedding for _ in texts]
