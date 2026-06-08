# CLAUDE.md — guidance for working in this repo

## What this is
**shelf** is a local-first, TUI-first CLI **research library agent**. A user names a
topic in natural language; the agent discovers a source universe, scores sources,
proposes a watchlist, tracks semantic changes, and compiles cited briefs / digests /
a living wiki. It is **not** a bookmark manager or an RSS reader.

Authoritative product spec: `shelf_agent_product_plan.pdf` (Korean, 19 pp). A text
extract may exist at `_plan_extracted.txt` (gitignored — regenerate if missing).

Read these before non-trivial work, in order:
`IMPLEMENTATION_PLAN.md` → `ARCHITECTURE.md` → `SCHEMA.md` → `COMMANDS.md` → `TASKS.md`.

## Non-negotiable product principles
1. **Local is canonical.** SQLite + filesystem are the store; Notion is an optional
   surface. Local-only users must lose no core feature.
2. **Propose, don't mutate.** Every write (source add, wiki update, sync, file
   write) goes through plan → diff → approval.
3. **Discover freely, watch cautiously.** The watchlist grows only via the review
   queue, never automatically.
4. **Citations are mandatory.** Every generated claim references a snapshot or local
   document; uncited claims go to review.
5. **Egress is visible.** Remote LLM / search / MCP / Notion are off-by-default and
   must preview what data leaves the machine.
6. **TUI over flags.** Select/preview/diff/approve is the default UX; argument-heavy
   CLI is an advanced layer only.

## Current status (keep this honest)
Built for real: package skeleton, Typer CLI (`init`, `status`, `version`, `chat`),
a **thin REPL shell** (`shelf.repl`) entered by bare `shelf`/`shelf chat`
(`/status`/`/help`/`/exit` work; other slash commands + free-text chat announce
their phase), Rich UI (`shelf.ui`), workspace init + layout, SQLite store (full
schema), config load/save, `shelf.services.gather_status` (shared by CLI + REPL),
tests. The full Textual command-palette TUI remains Phase 5 (`shelf.tui`).

**Phase 1 ingestion** (`shelf.ingestion`): `/clip`, `/import`, + browse/triage
(`/inbox` `/search` `/sources` `/save` `/mute`). **Phase 2 LLM gateway**
(`shelf.llm`): `ModelGateway` over an OpenAI-compatible endpoint (urllib, injectable
client), capability `probe`, egress gate (localhost ok; remote needs
`privacy.remote_llm`); `/model` (provider→model picker), `/summarize <id>`,
`/ask <q>` + library-aware free-text chat.

**Phase 3 discovery harness** (`shelf.tools` + `shelf.skills` + `shelf.agent` +
`shelf.discovery`): a Hermes-inspired, dependency-light tool/skill harness. `tools/`
is a `Tool` registry + composable toolsets (builtins: `library_search`, `fetch_url`,
`web_search` gated by `privacy.remote_search`, `propose_source`). `skills/` is
SKILL.md guidance loaded on demand. `agent/` is the ReAct loop using a **text**
tool-call protocol (fenced JSON, not native function-calling) with tolerant JSON
repair + bounded retries, so small local models work. Commands on it: `/explore`
(discover → propose candidates to the review queue, never auto-watch → cited brief;
live step trace; `--steps` budget), `/compile` (cited brief/landscape from the library
via the `compile` skill → `Compilations/`), `/track` (mark a topic tracked + frequency;
collection itself is Phase 4). Web search (`web_search` tool) POSTs to DuckDuckGo and
is gated by `privacy.remote_search`. Still open in Phase 3: full 9-axis source scoring
and RAG retrieval for `/ask` (needs a vector index — deliberately deferred).

Stubs that still raise `shelf.errors.FeatureNotReady` (clear interface, no behavior):
`shelf.watcher`, `shelf.tui`, `shelf.notion`, `shelf.mcp`. Do **not** quietly implement
stubs as side effects of unrelated work — they are phased (see `IMPLEMENTATION_PLAN.md`
§3). Update `TASKS.md` and the status memory when a phase lands.

## Layout
```
src/shelf/        cli/ ui/ config/ workspace/ store/ library/   (implemented)
                  ingestion/ llm/ tools/ skills/ agent/ discovery/   (implemented)
                  watcher/ tui/ notion/ mcp/   (stubs)
tests/            pytest suite mirroring the modules
```
`ui/` = Rich components used by the CLI now. `tui/` = the full Textual app (Phase 5).
Keep them separate.

## Dev workflow (Windows-first; the dev machine is Windows 11 + Python 3.13)
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest
.venv\Scripts\shelf.exe init .\ResearchLibrary
.venv\Scripts\shelf.exe status --workspace .\ResearchLibrary
```
On POSIX, use `.venv/bin/python` / `.venv/bin/shelf`.

## Conventions
- **Python 3.10+**, `from __future__ import annotations` at the top of every module
  so modern type hints work on 3.10.
- **Dataclasses** for config/domain models this milestone (no pydantic yet).
- **`pathlib.Path`** everywhere; write files UTF-8; never assume POSIX paths
  (Windows is a first-class target).
- New runtime deps are added **only in the phase that first needs them** — keep the
  base install (`typer`, `rich`, `pyyaml`) light and tests fast.
- Errors users can hit must raise a `ShelfError` subclass; the CLI turns those into
  clean messages (no tracebacks). Stubbed features raise `FeatureNotReady(phase=N)`.
- Keep `SCHEMA.md` and `store/schema.sql` in lockstep. Keep `COMMANDS.md` in sync
  with the Typer commands and the slash-command surface.

## When you add a feature
1. Move its task in `TASKS.md` from `[ ]`/`[~]` to `[x]`.
2. If it changes the store schema, bump `schema_version` + update `migrations.py`
   and `SCHEMA.md` together.
3. If it's a new command, document it in `COMMANDS.md` with its status legend mark.
4. Add/extend tests; `pytest` must stay green.
5. Update the `shelf-current-status` memory so future sessions start accurate.
