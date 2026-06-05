# shelf — Architecture

> Local-first, TUI-first CLI research library agent. This document describes the
> **target architecture** and the **boundaries** between what is implemented today
> and what is intentionally stubbed. Source of truth for product intent:
> `shelf_agent_product_plan.pdf`.

## 1. Architectural principles

These are load-bearing. Every module decision traces back to one of them.

1. **Local is canonical.** The SQLite metadata store + filesystem artifacts (raw
   snapshots, normalized text, Markdown, ledgers, vector index) are the single
   source of truth. Notion is an *optional* presentation/review surface, never the
   store. A user with no network and no Notion account loses zero core function.
2. **Propose, don't mutate.** Source registration, wiki updates, file writes,
   Notion sync — all pass through a plan → diff → approval gate. Nothing
   mutates the library silently.
3. **Discover freely, watch cautiously.** Discovery may surface many candidates;
   the watchlist only grows through the review queue. This keeps the library from
   bloating.
4. **Citations are mandatory.** Every generated claim must reference a snapshot or
   local document. Uncited claims go to review, not into artifacts.
5. **Data egress is always visible.** Any path that sends data off the machine
   (remote LLM, web search, remote MCP, Notion sync) must be explicit, off by
   default where sensitive, and able to preview what leaves.
6. **TUI over flags.** The primary UX is select / preview / diff / approve via
   Rich/Textual. Argument-heavy CLI is an advanced accelerator layer, not the
   default path.

## 2. Layered system overview

```
        ┌─────────────────────────────────────────────────────────┐
        │                    CLI / TUI REPL                         │
        │   Typer entrypoint · Rich components · Textual screens    │
        │   slash-command router · command palette · guided wizard  │
        └───────────────────────────┬─────────────────────────────┘
                                     │ intent + approved plans
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │                  Agent Orchestrator                       │
        │   intent router · planner / workflow engine               │
        │   approval gate · review queue                            │
        └───┬───────────────┬───────────────┬────────────────┬─────┘
            │               │               │                │
            ▼               ▼               ▼                ▼
   ┌────────────────┐ ┌───────────┐ ┌────────────────┐ ┌──────────────┐
   │ Model Gateway  │ │ Tool      │ │ Ingestion /    │ │ Library      │
   │ OpenAI-compat  │ │ Runtime   │ │ Watcher        │ │ Store        │
   │ role profiles  │ │ built-in  │ │ web/RSS/PDF    │ │ SQLite +     │
   │ capability     │ │ + MCP     │ │ snapshots,     │ │ filesystem + │
   │ probe          │ │ local/rmt │ │ semantic diff  │ │ vector index │
   └────────────────┘ └───────────┘ └────────────────┘ └──────┬───────┘
                                                               │
                                              ┌────────────────┴───────────┐
                                              ▼                            ▼
                                       ┌─────────────┐            ┌────────────────┐
                                       │ Markdown /  │            │ Notion Adapter │
                                       │ local export│            │ (optional)     │
                                       └─────────────┘            └────────────────┘
```

## 3. Package layout

The package follows the plan's repo-structure draft (§10.3), using a `src/` layout.
**Bold = implemented now. Plain = stub with a clear interface. Italic = not yet
created (later phase).**

```
src/shelf/
  __init__.py                # version, public exports
  __main__.py                # `python -m shelf`
  errors.py                  # ShelfError hierarchy (incl. FeatureNotReady)
  services.py                # app services shared by cli + repl (gather_status)

  cli/                       # ── IMPLEMENTED ──
    app.py                   #   Typer app, main(), global options
    errors.py                #   cli_errors(): ShelfError/FeatureNotReady/sqlite -> clean exit
    commands/
      init.py                #   `shelf init`   — workspace creation
      status.py              #   `shelf status` — the /status command
      chat.py                #   `shelf chat`   — REPL placeholder (Phase 5 stub)

  ui/                        # ── IMPLEMENTED ── Rich output components
    console.py               #   shared Console + success/warn/error/info helpers
    theme.py                 #   colors / styles
    status_view.py           #   status bar string + status panel renderers

  repl/                      # ── IMPLEMENTED (thin shell) ──
    session.py               #   ReplSession.handle() dispatch + run_repl() loop
    commands.py              #   slash-command registry (name -> phase/summary)

  config/                    # ── IMPLEMENTED ──
    models.py                #   dataclasses: Config, ModelProfile, PrivacyConfig...
    loader.py                #   load/save/default config.yaml (YAML round-trip)

  workspace/                 # ── IMPLEMENTED ──
    layout.py                #   directory layout spec + seed files
    paths.py                 #   Workspace dataclass, discovery (walk up / env)
    initializer.py           #   create dirs, config, db (idempotent w/ --force)

  store/                     # ── IMPLEMENTED ──
    schema.sql               #   DDL for all 8 core objects + meta
    sqlite_store.py          #   Store: open/init/migrate, counts, basic CRUD
    migrations.py            #   schema_version handling

  library/                   # ── IMPLEMENTED (models only) ──
    models.py                #   Topic/Source/Item/Snapshot/Claim/ReviewItem/...

  ingestion/                 # ── IMPLEMENTED (Phase 1) ── /clip + /import
    base.py                  #   Fetcher / Parser protocols, FetchResult, ParsedDocument
    parsers.py               #   html / markdown / text / pdf -> ParsedDocument
    fetch.py                 #   HttpFetcher (http/https/file, scheme allow-list)
    writers.py               #   Item markdown, snapshot, ledger writers
    clip.py / importer.py    #   the /clip and /import services
  discovery/                 # ── STUB (Phase 3: topic discovery / deep research) ──
    agent.py                 #   DiscoveryAgent interface
  watcher/                   # ── STUB (Phase 4: daemon) ──
    daemon.py                #   WatcherDaemon interface
  llm/                       # ── STUB (Phase 2) ──
    gateway.py               #   ModelGateway interface
  notion/                    # ── STUB (Phase 6) ──
    adapter.py               #   NotionAdapter interface
  mcp/                       # ── STUB (Phase 7) ──
    registry.py              #   McpRegistry interface
  tui/                       # ── STUB (Phase 5: full Textual app) ──
    app.py                   #   launch_tui()
```

### Why `ui/` and `tui/` are separate

`ui/` holds **Rich** components (tables, panels, status bar) used by the plain CLI
today. `tui/` is reserved for the **full-screen Textual** application (command
palette, review queue screen, diff viewer) delivered in Phase 5. Keeping them
separate lets the CLI render rich output now without pulling in the Textual app.

`repl/` is the **thin REPL shell** entered by bare `shelf` (or `shelf chat`): a
line-oriented loop that dispatches slash commands. Implemented commands run for
real; the rest announce their phase. It is deliberately *not* the full Textual TUI
(`tui/`, Phase 5) — it gives the "type `shelf`, get a research prompt" UX today
without the palette/wizard machinery.

### Tool layer — deferred to Phase 3 (decision)

The plan (§10.3) reserves a `tools/` package (`fs.py`, `web_fetch.py`, `diff.py`,
`export.py`) for the agent's **built-in tools**. We are **not** creating it yet.
Until the Agent Orchestrator exists, commands call functions directly (e.g. `/clip`
→ `clip_url()`), so there is nothing that *selects among* tools — a unified `tools/`
registry now would be premature abstraction. The capabilities that exist live where
they were first needed: web fetch → `ingestion/fetch.py` (`HttpFetcher`), parsing →
`ingestion/parsers.py`, fs writes → `ingestion/writers.py` / `workspace/`.

**Phase 3** introduces `tools/` as a uniform `Tool` interface + registry, unifying
three kinds of tool: (1) built-in local tools (web_fetch/fs/diff/export), (2) LLM
function-calling tools exposed to the model, and (3) MCP tools (`mcp/`, Phase 7).
diff/export/OCR/transaction-rollback are built then or in their owning phase.

## 4. Module responsibilities (target)

| Module | Responsibility | Key constraint |
|---|---|---|
| `cli` | Slash-command / Typer routing, status bar, error surfacing | Argument-heavy mode is advanced-only |
| `ui` | Rich rendering primitives | No business logic; pure presentation |
| `tui` | Full Textual app: palette, review, diff | Phase 5 |
| `config` | Load/validate/save `config.yaml`, model role profiles | Secrets never in plaintext config (use keyring) |
| `workspace` | Resolve/create the on-disk library layout | Local users are first-class |
| `store` | Canonical metadata in SQLite; counts; transactions | Works with zero network/Notion |
| `library` | Domain model dataclasses + (later) repositories | DB-agnostic value objects |
| `ingestion` | Fetch + parse (RSS/sitemap/HTML/PDF), normalize | RSS/sitemap first; browser is last-resort fallback |
| `discovery` | Query expansion, source discovery, scoring, synthesis | Proposal-centric, never auto-watch |
| `watcher` | Scheduled checks, snapshot hashing, diff, digest | Weekly digest default; high-signal-only immediate alerts |
| `llm` | OpenAI-compatible gateway + capability probe | Don't assume tools/json/vision/embeddings exist |
| `notion` | Curated surface sync, schema creation, status import | Rate-limit, conflict, privacy aware; never canonical |
| `mcp` | Local/remote tool registry + trust/permission policy | Remote tools read-only by default; egress preview |

## 5. Data flow — the MVP single core flow

```
natural-language topic
  → intent interpretation        (cli → orchestrator)
  → search strategy / query plan (orchestrator + llm)
  → source discovery             (discovery + ingestion)
  → source scoring               (discovery)
  → initial synthesis            (llm, citation-checked)
  → watchlist proposal           (review queue)
  → local / Notion review queue  (store + notion adapter)
  → optional topic watcher       (watcher)
```

Today, the **store**, **workspace**, **config**, and the **status** read-path of
this flow are real; the productive write-path stages (discovery, ingestion,
synthesis, watcher) are stubs with defined interfaces so they can be filled in
phase by phase without reshaping the store or CLI.

## 6. Persistence model

Two complementary stores, both local:

- **SQLite** (`.shelf/library.sqlite`, `.shelf/jobs.sqlite`): structured metadata —
  topics, sources, items, snapshots, claims, review items, compilations, watch
  runs; plus job/scheduler state. Fast querying for status, review queues, counts.
- **Filesystem**: human-readable canonical artifacts — `Topics/`, `Sources/`,
  `Items/`, `Wiki/`, `Digests/`, `Compilations/`, `Review/`, append-only
  `Ledgers/*.jsonl`, and machine caches under `.shelf/` (`snapshots/`,
  `normalized/`, `index/`, `cache/`).

The Markdown/YAML files are the *durable, portable* form; SQLite is the *index*
over them. A `rebuild` (Phase 1+) can reconstruct SQLite from the filesystem so the
library survives DB loss. See `SCHEMA.md` for exact schemas.

## 7. Error & feature-gating model

`shelf.errors` defines a small hierarchy:

- `ShelfError` — base; CLI catches it and prints a clean message (exit 1).
- `WorkspaceNotFound` — no `.shelf/` found when one was required.
- `WorkspaceExists` — `init` target already initialized (use `--force`).
- `FeatureNotReady(NotImplementedError)` — a stubbed feature was invoked; carries
  the phase that will deliver it. The CLI renders it as a friendly "coming in
  Phase N" notice rather than a stack trace.

Stub modules raise `FeatureNotReady` from their public methods, so callers and
tests can depend on a stable, documented contract today.

## 8. Concurrency & scheduling (target)

`asyncio` for I/O-bound fetch/parse fan-out; `APScheduler` for the local watcher
daemon (Phase 4). The daemon is opt-in and explicit-run-first; no autonomous
background crawling in the MVP.

## 9. Security & privacy boundaries

- Secrets (Notion token, API keys) live in the OS keychain via `keyring`, never in
  `config.yaml`.
- `config.yaml` records *intent/flags* (e.g. `privacy.remote_llm: false`), and the
  gateway/adapters must honor them as gates.
- Default posture: remote search off, remote LLM off, remote MCP read-only, Notion
  sync `off` (local-only) until the user opts in.
