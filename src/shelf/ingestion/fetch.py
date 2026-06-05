"""HTTP(S)/file fetching for ``/clip``.

Uses the standard library (``urllib``) to avoid an extra dependency this phase; the
``Fetcher`` interface lets services swap in a richer client (httpx) or a fake later.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlsplit

from shelf.errors import FetchError
from shelf.ingestion.base import FetchResult
from shelf.util import utc_now_iso

USER_AGENT = "shelf/0.0.1 (+local-first research agent)"
DEFAULT_TIMEOUT = 20
# Read at most this many bytes from a response to avoid OOM on a huge/streamed body.
MAX_FETCH_BYTES = 50 * 1024 * 1024
# file:// is intentional (local-first: clip a local file); ftp/data/etc. are blocked.
ALLOWED_SCHEMES = frozenset({"http", "https", "file"})


class HttpFetcher:
    """Fetch ``http(s)://`` and ``file://`` URLs via urllib (other schemes rejected)."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_bytes: int = MAX_FETCH_BYTES) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> FetchResult:
        scheme = urlsplit(url).scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise FetchError(
                f"Unsupported URL scheme {scheme or '(none)'!r}; "
                f"allowed: {', '.join(sorted(ALLOWED_SCHEMES))}."
            )
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.max_bytes + 1)
                content_type = response.headers.get_content_type()
                status = getattr(response, "status", 200) or 200
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} fetching {url}") from exc
        except (urllib.error.URLError, ValueError, OSError) as exc:
            raise FetchError(f"Could not fetch {url}: {exc}") from exc
        if len(raw) > self.max_bytes:
            raise FetchError(f"Response exceeds {self.max_bytes} bytes: {url}")
        return FetchResult(
            url=final_url,
            status=int(status),
            content_type=content_type,
            raw=raw,
            fetched_at=utc_now_iso(),
        )
