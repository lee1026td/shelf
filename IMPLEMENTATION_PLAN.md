# shelf — Implementation Plan

> Converts `shelf_agent_product_plan.pdf` into an implementation-ready roadmap.
> This file is the contract for *what gets built when* and *how we know it's done*.

## 0. Scope of the current milestone

The product plan defines Phases 0–7 (§12.2). This milestone delivers **Phase 0
(workspace skeleton)** plus the **foundation slice of Phase 1** needed to make the
app runnable and testable end-to-end, while every later capability is present as a
**stub with a clear interface**.

**In scope now (built for real):**
- Python `src/` package skeleton (`src/shelf`)
- Typer CLI entrypoint (`shelf` console script + `python -m shelf`)
- Rich-based status/output components (`shelf.ui`)
- Local workspace initialization (`shelf init`)
- Local directory structure for Notion-free users (`shelf.workspace.layout`)
- SQLite metadata store with full core schema (`shelf.store`)
- Config loading/saving (`shelf.config`, `.shelf/config.yaml`)
- `/status` command (`shelf status`)
- Basic test suite (pytest)
- **Thin REPL shell** (`shelf.repl`): bare `shelf` / `shelf chat` enter a
  slash-command loop inside a workspace; `/status`/`/help`/`/exit` work for real,
  every other slash command and free-text chat announce their phase. Added to match
  the intended "type `shelf`, get a research prompt" UX. The full Textual command
  palette / wizards remain Phase 5 (`shelf.tui`).

**Explicitly deferred (stub only this milestone):**
- Notion sync (Phase 6) · MCP (Phase 7) · deep research / topic discovery
  (Phase 3) · watcher daemon (Phase 4) · full Textual TUI (Phase 5) · LLM gateway
  (Phase 2) · ingestion/parsing of real content (rest of Phase 1)

Stubs raise `shelf.errors.FeatureNotReady` (a `NotImplementedError` subclass) and
document the phase that will implement them.

## 1. Assumptions

1. **Single-user, local-first, personal-scale.** No multi-tenant auth, no server.
   The library lives in one directory tree the user owns.
2. **Python 3.10+ runtime.** The plan targets 3.12+; we keep `>=3.10` for
   portability via `from __future__ import annotations`. Dev/CI uses the installed
   interpreter (3.13 here).
3. **Minimal hard dependencies now.** Only `typer`, `rich`, `pyyaml` are required at
   runtime for this milestone. Heavy libs (Docling, LanceDB, Textual, Notion SDK,
   MCP SDK, APScheduler, httpx, trafilatura) are introduced in the phase that first
   needs them, to keep install light and tests fast.
4. **Dataclasses over pydantic** for config/domain models in this milestone, to
   avoid a dependency and pydantic v1/v2 ambiguity. May revisit if validation needs
   grow.
5. **SQLite is the metadata index; the filesystem is canonical.** The schema is
   designed so SQLite can later be rebuilt from on-disk Markdown/YAML.
6. **Workspace discovery** walks up from the current directory looking for `.shelf/`,
   overridable by `--workspace` or the `SHELF_HOME` environment variable.
7. **`shelf init` is conservative**: it refuses to overwrite an existing workspace
   unless `--force`, to protect a user's library.
8. **Cross-platform**, with Windows as a first-class target (paths via `pathlib`,
   UTF-8 file writes, no POSIX-only assumptions).
9. **Secrets are out of scope this milestone** beyond reserving the keyring-backed
   design; no tokens are read or stored yet.
10. **The slash commands in `COMMANDS.md` are the UX surface**; in the Typer layer
    they map to subcommands (`/status` → `shelf status`). The REPL/palette that
    renders true `/command` input arrives in Phase 5.

## 2. Acceptance criteria (current milestone)

A reviewer can verify the milestone is complete by checking each item:

### A. Package & tooling
- [ ] `pip install -e ".[dev]"` succeeds from a clean checkout.
- [ ] `shelf --help` and `python -m shelf --help` both work and list commands.
- [ ] `shelf version` prints the package version.

### B. Workspace initialization (`shelf init`)
- [ ] `shelf init <path>` creates the full directory layout from plan §7.3
      (`Topics/`, `Sources/`, `Items/`, `Wiki/`, `Digests/`, `Compilations/`,
      `Inbox/`, `Review/{pending,approved,rejected,stale_claims}/`, `Ledgers/`,
      `.shelf/{index,snapshots,normalized,cache}/`).
- [ ] It writes a valid `.shelf/config.yaml` and a `Dashboard.md`.
- [ ] It creates `.shelf/library.sqlite` containing all core tables.
- [ ] Re-running on an initialized path fails with a clear message; `--force`
      re-initializes.
- [ ] Empty append-only ledgers (`Ledgers/source_ledger.jsonl`,
      `Ledgers/claim_ledger.jsonl`) exist.

### C. Config
- [ ] A freshly created config round-trips through `load → save → load` unchanged.
- [ ] Defaults match the plan: local-only (`notion.sync_mode: off`), remote LLM/
      search/MCP off, an OpenAI-compatible `planner` + `embeddings` model profile.

### D. SQLite store
- [ ] Opening a fresh store creates all tables and records a `schema_version`.
- [ ] `Store.counts()` returns zeroed counts on an empty store and accurate counts
      after inserts.
- [ ] Basic CRUD for `sources` and `items` works (insert + read back).

### E. `/status` (`shelf status`)
- [ ] Run inside a workspace, it renders a Rich status panel **and** the one-line
      status bar in the plan's format:
      `[Shelf: ~/ResearchLibrary] [model: <model>] [remote: off] [sources: N] [inbox: N] [review: N]`.
- [ ] Run outside any workspace, it fails cleanly telling the user to run
      `shelf init` (no traceback).
- [ ] Counts shown reflect the store (sources / inbox-items / pending-reviews).

### F. Stubs
- [ ] Importing `shelf.notion`, `shelf.mcp`, `shelf.discovery`, `shelf.watcher`,
      `shelf.llm`, `shelf.tui`, `shelf.ingestion` succeeds.
- [ ] Each stub's public entrypoint raises `FeatureNotReady` carrying its phase.
- [ ] `shelf chat` prints a friendly "Phase 5" notice and exits 0 (placeholder).

### G. Tests
- [ ] `pytest` passes with coverage of config round-trip, workspace init, store
      schema/counts/CRUD, status rendering (in/out of workspace), and stub gating.

## 3. Phase roadmap (from plan §12.2)

| Phase | Goal | Primary deliverables | Status |
|---|---|---|---|
| **0** | Workspace skeleton | `shelf init`, `config.yaml`, SQLite schema, local dir layout | **This milestone** |
| **1** | Local library mode | `/clip`, `/import`, HTML/PDF parsing, local Markdown output, source ledger | **Implemented** (clip/import/parse/snapshots/ledger/dry-run) |
| **2** | LLM gateway | OpenAI-compatible config, local model test, summary card, capability probe | Stub (`shelf.llm`) |
| **3** | Topic discovery | natural prompt → web search → candidates → scoring → initial brief | Stub (`shelf.discovery`) |
| **4** | Watcher | RSS/sitemap watcher, snapshots, diff, review queue, weekly digest | Stub (`shelf.watcher`) |
| **5** | TUI UX | Rich/Textual `/review` `/watch` `/compile`, command palette, approval UI | Stub (`shelf.tui`) |
| **6** | Notion sync | schema creation, curated sync, review-queue status import | Stub (`shelf.notion`) |
| **7** | MCP | stdio/remote read-only registry, permission prompts | Stub (`shelf.mcp`) |

## 4. Out of scope for the whole MVP (plan §12.3)

Full automated browser crawling, auto-watching all sources, Notion-only operation,
mobile apps, team collaboration/permissions, fully autonomous background crawling.

## 5. Build/verify workflow

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest          # run tests
.venv\Scripts\shelf.exe init .\ResearchLibrary
.venv\Scripts\shelf.exe status --workspace .\ResearchLibrary
```

See `TASKS.md` for the granular checklist and `COMMANDS.md` for the command surface.
