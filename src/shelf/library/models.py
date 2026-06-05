"""Core domain models (plan §6.1). Plain dataclasses, independent of storage.

These mirror the SQLite tables in ``SCHEMA.md`` §1 but carry no persistence logic;
repositories (added per phase) translate between these and rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceStatus(str, Enum):
    """Source status taxonomy (plan §6.2)."""

    PINNED = "pinned"
    WATCHED = "watched"
    CANDIDATE = "candidate"
    EPHEMERAL = "ephemeral"
    MUTED = "muted"
    REJECTED = "rejected"
    FAILING = "failing"


@dataclass
class SourceScore:
    """The nine source-scoring axes (plan §6.3), each in ``[0, 1]``."""

    relevance: float | None = None
    authority: float | None = None
    originality: float | None = None
    freshness: float | None = None
    update_frequency: float | None = None
    extractability: float | None = None
    uniqueness: float | None = None
    noise_risk: float | None = None
    watchability: float | None = None


@dataclass
class Topic:
    name: str
    slug: str
    intent: str | None = None
    status: str = "active"
    collections: list[str] = field(default_factory=list)
    id: int | None = None


@dataclass
class Source:
    slug: str
    url: str
    name: str | None = None
    role: str | None = None
    status: SourceStatus = SourceStatus.CANDIDATE
    topic_id: int | None = None
    score: SourceScore = field(default_factory=SourceScore)
    extraction_health: str | None = None
    id: int | None = None


@dataclass
class Item:
    title: str | None = None
    url: str | None = None
    source_id: int | None = None
    published_at: str | None = None
    captured_at: str | None = None
    summary: str | None = None
    novelty: float | None = None
    status: str = "new"
    local_path: str | None = None
    id: int | None = None


@dataclass
class Snapshot:
    hash: str
    fetched_at: str
    source_id: int | None = None
    item_id: int | None = None
    raw_path: str | None = None
    normalized_path: str | None = None
    parser_version: str | None = None
    id: int | None = None


@dataclass
class Claim:
    claim_text: str
    topic_id: int | None = None
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float | None = None
    stale_status: str = "fresh"
    id: int | None = None


@dataclass
class ReviewItem:
    type: str
    title: str | None = None
    priority: str = "normal"
    status: str = "pending"
    suggested_action: str | None = None
    ref_kind: str | None = None
    ref_id: int | None = None
    local_ref: str | None = None
    notion_ref: str | None = None
    id: int | None = None


@dataclass
class Compilation:
    title: str
    topic_id: int | None = None
    kind: str | None = None
    source_count: int = 0
    confidence: float | None = None
    output_path: str | None = None
    id: int | None = None


@dataclass
class WatchRun:
    started_at: str
    topic_id: int | None = None
    finished_at: str | None = None
    sources_checked: int = 0
    new_items: int = 0
    changes: int = 0
    failures: int = 0
    cost: float | None = None
    model_used: str | None = None
    status: str = "completed"
    id: int | None = None
