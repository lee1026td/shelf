"""Topic discovery (Phase 3, plan §8.1, §9.2).

Turns a natural-language topic into a multi-step research run driven by the agent
harness (``shelf.agent``) over the discovery toolset: it searches (library + web when
enabled), reads promising pages, and **proposes** candidate sources into the review
queue — never auto-watching ("discover freely, watch cautiously") — then returns a
cited initial brief. Designed to work with a small local model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shelf.agent import AgentLoop
from shelf.config import Config, load_config
from shelf.ingestion import Fetcher
from shelf.ingestion.fetch import HttpFetcher
from shelf.llm import ModelGateway
from shelf.skills import load_skill
from shelf.store import Store
from shelf.tools import ToolContext, ToolRegistry, build_default_registry
from shelf.util import slugify
from shelf.workspace import Workspace


@dataclass
class SourceCandidate:
    """A discovered, not-yet-watched source proposal (plan appendix B)."""

    url: str
    name: str | None = None
    role: str | None = None
    score: dict[str, float] = field(default_factory=dict)
    why_suggested: list[str] = field(default_factory=list)


@dataclass
class ExploreOutcome:
    """Result of an ``/explore`` run."""

    topic: str
    brief: str
    candidates: list[dict[str, Any]] = field(default_factory=list)  # proposed source rows
    steps: int = 0
    stopped_reason: str = "final"
    remote_search: bool = False


def explore_topic(
    workspace: Workspace,
    gateway: ModelGateway,
    topic: str,
    *,
    store: Store,
    fetcher: Fetcher | None = None,
    registry: ToolRegistry | None = None,
    config: Config | None = None,
    max_steps: int = 8,
    on_event: Callable[[str, str], None] | None = None,
) -> ExploreOutcome:
    """Run source discovery for ``topic``; propose candidates + return a cited brief.

    Proposals are written by the ``propose_source`` tool as ``status='candidate'``
    sources plus pending review items — the watchlist is never grown here.
    """
    topic = topic.strip()
    config = config or load_config(workspace.config_path)
    registry = registry or build_default_registry()
    fetcher = fetcher or HttpFetcher()

    topic_id = store.ensure_topic(topic, slugify(topic, fallback="topic"), intent=topic)
    ctx = ToolContext(
        workspace=workspace,
        store=store,
        gateway=gateway,
        fetcher=fetcher,
        config=config,
        scratch={"topic": topic, "topic_id": topic_id, "proposed": []},
    )
    skill = load_skill("explore")
    toolset = skill.toolset if skill and skill.toolset else "discovery"
    goal = f"Discover and propose high-quality sources for the research topic: {topic}"

    result = AgentLoop(gateway, registry, ctx).run(
        goal, toolset=toolset, skill=skill, max_steps=max_steps, on_event=on_event
    )

    proposed_slugs: list[str] = ctx.scratch.get("proposed", [])
    candidates = [c for c in (store.get_source(s) for s in proposed_slugs) if c is not None]
    return ExploreOutcome(
        topic=topic,
        brief=result.answer,
        candidates=candidates,
        steps=len(result.steps),
        stopped_reason=result.stopped_reason,
        remote_search=bool(config.privacy.remote_search),
    )


@dataclass
class AnswerOutcome:
    """Result of an agentic free-text answer (the chat surface's tool routing)."""

    question: str
    answer: str
    steps: int = 0
    stopped_reason: str = "final"


def answer_question(
    workspace: Workspace,
    gateway: ModelGateway,
    question: str,
    *,
    store: Store,
    fetcher: Fetcher | None = None,
    registry: ToolRegistry | None = None,
    config: Config | None = None,
    max_steps: int = 6,
    on_event: Callable[[str, str], None] | None = None,
) -> AnswerOutcome:
    """Answer a free-text question by letting the agent route over read-only tools.

    This is what plain chat input (no slash command) runs: the model decides when to
    ``library_search`` / ``fetch_url`` / ``web_search`` (web gated by
    ``privacy.remote_search``) and returns a cited answer. Nothing is proposed or written
    — the watchlist and review queue are untouched (that is ``/explore``'s job).
    """
    question = question.strip()
    config = config or load_config(workspace.config_path)
    registry = registry or build_default_registry()
    fetcher = fetcher or HttpFetcher()

    ctx = ToolContext(
        workspace=workspace,
        store=store,
        gateway=gateway,
        fetcher=fetcher,
        config=config,
        scratch={"question": question},
    )
    goal = (
        "Answer the user's question. Prefer the local library (library_search); fetch a "
        "source with fetch_url when you need its full text; use web_search only if the "
        "library is insufficient and it is enabled. Cite the sources you rely on.\n\n"
        f"Question: {question}"
    )
    result = AgentLoop(gateway, registry, ctx).run(
        goal, toolset="answer", max_steps=max_steps, on_event=on_event
    )
    return AnswerOutcome(
        question=question,
        answer=result.answer,
        steps=len(result.steps),
        stopped_reason=result.stopped_reason,
    )


@dataclass
class CompileOutcome:
    """Result of a ``/compile`` run."""

    topic: str
    kind: str
    document: str
    output_path: str | None = None
    steps: int = 0
    stopped_reason: str = "final"


def _write_compilation(workspace: Workspace, topic: str, kind: str, document: str) -> str:
    """Write a compiled document under ``Compilations/`` (never overwriting). Returns the
    workspace-relative path."""
    comp_dir = workspace.root / "Compilations"
    comp_dir.mkdir(parents=True, exist_ok=True)
    base = slugify(f"{topic}-{kind}", fallback="compilation")
    path = comp_dir / f"{base}.md"
    counter = 2
    while path.exists():
        path = comp_dir / f"{base}-{counter}.md"
        counter += 1
    path.write_text(document, encoding="utf-8")
    return str(path.relative_to(workspace.root))


def compile_topic(
    workspace: Workspace,
    gateway: ModelGateway,
    topic: str,
    *,
    store: Store,
    kind: str = "brief",
    fetcher: Fetcher | None = None,
    registry: ToolRegistry | None = None,
    config: Config | None = None,
    max_steps: int = 10,
    on_event: Callable[[str, str], None] | None = None,
) -> CompileOutcome:
    """Compile a cited document on ``topic`` from the library, via the agent harness.

    Reuses the same loop as ``/explore`` with the ``compile`` skill + toolset (read-only:
    library_search + fetch_url, no proposing). The agent's final answer is the Markdown
    document; it's written under ``Compilations/`` (additive — never overwrites) and
    recorded in the ``compilations`` table.
    """
    topic = topic.strip()
    config = config or load_config(workspace.config_path)
    registry = registry or build_default_registry()
    fetcher = fetcher or HttpFetcher()

    topic_id = store.ensure_topic(topic, slugify(topic, fallback="topic"), intent=topic)
    ctx = ToolContext(
        workspace=workspace,
        store=store,
        gateway=gateway,
        fetcher=fetcher,
        config=config,
        scratch={"topic": topic, "topic_id": topic_id},
    )
    skill = load_skill("compile")
    toolset = skill.toolset if skill and skill.toolset else "compile"
    goal = f"Compile a cited {kind} on the topic: {topic}"

    result = AgentLoop(gateway, registry, ctx).run(
        goal, toolset=toolset, skill=skill, max_steps=max_steps, on_event=on_event
    )

    output_path: str | None = None
    if result.stopped_reason != "error" and result.answer.strip():
        output_path = _write_compilation(workspace, topic, kind, result.answer)
        store.add_compilation(
            title=f"{topic} ({kind})", topic_id=topic_id, kind=kind, output_path=output_path
        )
        store.commit()
    return CompileOutcome(
        topic=topic,
        kind=kind,
        document=result.answer,
        output_path=output_path,
        steps=len(result.steps),
        stopped_reason=result.stopped_reason,
    )


class DiscoveryAgent:
    """Object wrapper around :func:`explore_topic` (the Agent Orchestrator's discovery arm)."""

    def __init__(
        self,
        workspace: Workspace,
        gateway: ModelGateway,
        *,
        registry: ToolRegistry | None = None,
        fetcher: Fetcher | None = None,
        config: Config | None = None,
    ) -> None:
        self.workspace = workspace
        self.gateway = gateway
        self.registry = registry or build_default_registry()
        self.fetcher = fetcher
        self.config = config

    def explore(self, topic: str, *, store: Store, max_steps: int = 8) -> ExploreOutcome:
        return explore_topic(
            self.workspace,
            self.gateway,
            topic,
            store=store,
            fetcher=self.fetcher,
            registry=self.registry,
            config=self.config,
            max_steps=max_steps,
        )
