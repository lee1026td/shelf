"""Discovery agent. STUB (Phase 3, plan §8.1, §9.2).

Turns a natural-language topic into a query plan, discovers candidate sources,
scores them, and produces an initial source-backed brief — proposal-centric, never
auto-watch (plan principle: "discover freely, watch cautiously").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shelf.errors import FeatureNotReady


@dataclass
class SourceCandidate:
    """A discovered, not-yet-watched source proposal (plan appendix B)."""

    url: str
    name: str | None = None
    role: str | None = None
    score: dict[str, float] = field(default_factory=dict)
    why_suggested: list[str] = field(default_factory=list)


class DiscoveryAgent:
    """Stub discovery agent."""

    PHASE = 3

    def explore(self, topic: str, *, depth: str = "balanced") -> list[SourceCandidate]:
        raise FeatureNotReady("Topic discovery / source discovery", self.PHASE)

    def score_sources(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        raise FeatureNotReady("Source scoring", self.PHASE)

    def initial_brief(self, topic: str) -> str:
        raise FeatureNotReady("Initial research brief synthesis", self.PHASE)
