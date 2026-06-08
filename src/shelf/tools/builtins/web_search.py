"""``web_search`` — gated web search via a pluggable provider.

Egress is **off by default**: the handler refuses unless ``privacy.remote_search`` is
enabled (ARCHITECTURE.md principle 5). The default provider POSTs to DuckDuckGo's HTML
endpoint via urllib (no new dependency) — a GET returns a 202 "anomaly" page with zero
results, so POST is required. The ``SearchProvider`` protocol lets an API provider
(Tavily/Brave) drop in later. Tests inject a fake provider via
``ctx.scratch['search_provider']``.
"""

from __future__ import annotations

import urllib.request
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

from shelf.ingestion.base import Fetcher
from shelf.tools.base import Tool, ToolContext

_DDG_HTML = "https://html.duckduckgo.com/html/"
_MAX_RESULTS = 6
_TIMEOUT = 20
_MAX_BYTES = 2_000_000
# DDG serves results to browser-like clients; a generic UA is more likely to be served.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class SearchProvider(Protocol):
    def search(self, query: str, fetcher: Fetcher, *, limit: int = _MAX_RESULTS) -> list[dict]: ...


def _ddg_real_url(href: str) -> str:
    """DuckDuckGo HTML may wrap results as /l/?uddg=<encoded-target>; unwrap it.

    Newer responses use direct hrefs (no uddg) - those pass through unchanged.
    """
    if href.startswith("//"):
        href = "https:" + href
    try:
        qs = parse_qs(urlsplit(href).query)
    except ValueError:
        return href
    target = qs.get("uddg")
    return target[0] if target else href


def _parse_results(raw: bytes, limit: int) -> list[dict]:
    """Extract result rows from DuckDuckGo's HTML (pure; testable without network)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    anchors = soup.select("div.result a.result__a") or soup.select("a.result__a")
    out: list[dict] = []
    for anchor in anchors:
        href = anchor.get("href")
        if not href:
            continue
        block = anchor.find_parent("div", class_="result")
        snippet_el = block.select_one(".result__snippet") if block else None
        out.append(
            {
                "title": anchor.get_text(strip=True),
                "url": _ddg_real_url(str(href)),
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            }
        )
        if len(out) >= limit:
            break
    return out


class DuckDuckGoHtmlProvider:
    """Scrape html.duckduckgo.com via POST. No API key; best-effort, may break on markup
    changes. POST is required: a GET returns a 202 "anomaly" page with zero results."""

    def search(self, query: str, fetcher: Fetcher, *, limit: int = _MAX_RESULTS) -> list[dict]:
        # The HTML endpoint only returns results for a POST form submit. We issue our own
        # POST because the shared HttpFetcher is GET-only; egress is already gated by the
        # web_search handler (privacy.remote_search), so `fetcher` is intentionally unused.
        data = urlencode({"q": query}).encode("utf-8")
        request = urllib.request.Request(
            _DDG_HTML, data=data, headers={"User-Agent": _USER_AGENT}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            raw = response.read(_MAX_BYTES)
        return _parse_results(raw, limit)


_PARAMETERS = {
    "properties": {
        "query": {"type": "string", "description": "Search query."},
    },
    "required": ["query"],
}


def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    if ctx.config is None or not ctx.config.privacy.remote_search:
        return (
            "web_search is disabled: remote search egress is off. Use library_search "
            "instead, or ask the user to enable privacy.remote_search."
        )
    if ctx.fetcher is None:
        return "error: no fetcher available"
    query = str(args.get("query") or "").strip()
    if not query:
        return "error: empty query"
    provider: SearchProvider = ctx.scratch.get("search_provider") or DuckDuckGoHtmlProvider()
    try:
        results = provider.search(query, ctx.fetcher, limit=_MAX_RESULTS)
    except Exception as exc:
        return f"error: web search failed: {exc}"
    if not results:
        return f"No web results for {query!r}."
    lines = [f"Web results for {query!r}:"]
    for r in results:
        lines.append(f"- {r.get('title') or '(untitled)'} | {r.get('url')}")
        if r.get("snippet"):
            lines.append(f"    {r['snippet']}")
    return "\n".join(lines)


TOOL = Tool(
    name="web_search",
    description="Search the web for sources on a topic (returns titles + URLs). Remote: "
    "only works when the user has enabled remote search egress.",
    toolset="discovery",
    parameters=_PARAMETERS,
    handler=_handler,
    check_fn=lambda ctx: ctx.fetcher is not None,
)
