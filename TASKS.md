# shelf — Task Board

Living checklist. `[x]` done · `[~]` partial/foundation laid · `[ ]` not started.
Phase mapping per `IMPLEMENTATION_PLAN.md` §3.

## Milestone: Phase 0 + Phase 1 foundation (current)

### Scaffolding & tooling
- [x] `pyproject.toml` (src layout, `shelf` console script, dev extras)
- [x] `.gitignore` (Python, venv, `.shelf/` caches, extracted plan text)
- [x] Package skeleton `src/shelf/` with `__init__.py`, `__main__.py`
- [x] `shelf.errors` hierarchy incl. `FeatureNotReady`
- [x] Planning docs: IMPLEMENTATION_PLAN, ARCHITECTURE, TASKS, SCHEMA, COMMANDS, CLAUDE

### CLI (Typer)
- [x] `shelf.cli.app` Typer app + `main()` entrypoint + global error handling
- [x] `shelf version`
- [x] `shelf init [PATH] [--name] [--force]`
- [x] `shelf status [--workspace]`  (the `/status` command)
- [x] bare `shelf` / `shelf chat` enter the REPL (workspace) or hint (outside)

### REPL shell (thin; full Textual TUI is Phase 5)
- [x] `shelf.repl.session` `ReplSession.handle()` dispatch + `run_repl()` loop
- [x] `shelf.repl.commands` slash registry (name -> phase/summary)
- [x] built-ins now: `/status`, `/help` (`/`, `/?`), `/exit` (`/quit`, `/q`)
- [x] unimplemented slash -> phase notice; free text -> chat phase notice
- [x] `shelf.services.gather_status` shared by CLI `/status` and REPL
- [x] input: prompt_toolkit on TTY, `input()` fallback; piped-stdin BOM normalized
- [x] `tests/test_repl.py` dispatch, loop, BOM/mojibake handling

### Rich UI components
- [x] `shelf.ui.console` shared Console + success/info/warn/error helpers
- [x] `shelf.ui.theme` styles
- [x] `shelf.ui.status_view` status bar string + status panel

### Config
- [x] `shelf.config.models` dataclasses (Config, ModelProfile, NotionConfig, PrivacyConfig…)
- [x] `shelf.config.loader` load/save/default + YAML round-trip
- [x] Defaults: local-only, remote off, planner+embeddings profiles

### Workspace
- [x] `shelf.workspace.layout` directory + seed-file spec (plan §7.3)
- [x] `shelf.workspace.paths` Workspace dataclass + discovery (cwd walk-up / `$SHELF_HOME`)
- [x] `shelf.workspace.initializer` create dirs/config/db, `--force`, idempotent guard

### SQLite store
- [x] `store/schema.sql` — all 8 core objects + meta (matches SCHEMA.md §1)
- [x] `shelf.store.sqlite_store` open/init, `counts()`, source/item CRUD
- [x] `shelf.store.migrations` schema_version tracking

### Domain models
- [x] `shelf.library.models` dataclasses for Topic/Source/Item/Snapshot/Claim/ReviewItem/Compilation/WatchRun

### Stubs (clear interfaces, raise `FeatureNotReady`)
- [x] `shelf.ingestion.base` Fetcher/Parser protocols (Phase 1 remainder)
- [x] `shelf.llm.gateway` ModelGateway (Phase 2)
- [x] `shelf.discovery.agent` DiscoveryAgent (Phase 3)
- [x] `shelf.watcher.daemon` WatcherDaemon (Phase 4)
- [x] `shelf.tui.app` launch_tui (Phase 5)
- [x] `shelf.notion.adapter` NotionAdapter (Phase 6)
- [x] `shelf.mcp.registry` McpRegistry (Phase 7)

### Tests
- [x] `tests/test_config.py` round-trip + defaults
- [x] `tests/test_workspace.py` init creates layout, `--force`, discovery
- [x] `tests/test_store.py` schema, counts, CRUD
- [x] `tests/test_status.py` status in/out of workspace, status-bar format
- [x] `tests/test_cli.py` `--help`, `version`, `init`→`status` flow, nonzero counts, corrupt-DB clean-fail
- [x] `tests/test_stubs.py` each stub raises `FeatureNotReady` with its phase
- [x] `tests/test_encoding.py` ASCII-only guard for console-reachable text (cp949 safety)

### Hardening (post-review)
- [x] ASCII-only console output (no Unicode glyphs/em-dashes reach stdout/stderr) — verified on a cp949 Windows console
- [x] `shelf status` fails cleanly (not a traceback) when `library.sqlite` is missing/blank
- [x] config boolean capabilities coerce quoted `"false"/"off"/"no"` correctly

## Phase 1 — Local library mode
- [x] `/clip` — fetch URL (http/https/file) → parse → Item + ephemeral source (`shelf clip`)
- [x] `/import` — local PDF/HTML/MD/text file or folder → parse → Items (`shelf import`)
- [x] HTML article extraction (BeautifulSoup/html.parser; trafilatura is a later upgrade)
- [x] PDF parsing (pypdf; Docling is a later upgrade)
- [x] Markdown/text parsing
- [x] Normalized Markdown output + `Items/YYYY/MM/<slug>.md` writer (YAML frontmatter)
- [x] Snapshot store (`.shelf/snapshots` + `.shelf/normalized`, content-hash deduped)
- [x] Source ledger append (`Ledgers/source_ledger.jsonl`)
- [x] `--dry-run` (plan without writing) for clip + import
- [x] Hardening (review): `/import` excludes the workspace's own dirs; per-file
      SAVEPOINT atomicity; URL scheme allow-list; size caps; Windows reserved-name
      slugs; `ensure_safe_streams` for non-ASCII content; relative-POSIX path storage
- [x] Browse + triage: `/inbox` (list new), `/search <q>`, `/sources`, `/save <id>`,
      `/mute <id>` — REPL + CLI (`shelf inbox`/`search`/`sources`)
- [ ] `Topics/`, `Sources/` YAML writers + markdown index rebuild (deferred to discovery)

## Phase 2 — LLM gateway
- [x] OpenAI-compatible client (`shelf.llm.client`, urllib, injectable/mockable)
- [x] `ModelGateway` — role profiles, `complete`/`embed`, capability `probe`
- [x] Egress gate: localhost allowed; remote endpoint requires `privacy.remote_llm`
- [x] `/model` (show profiles + probe) — REPL + `shelf model` (`--no-probe`)
- [x] Model **selection** (chat + embeddings): `/model list [role]`, `/model set <role>
      <model> [base_url]`, `/model use <model>` — persisted to config (REPL + CLI)
- [x] Interactive `/model` **picker** (provider → model): Ollama / Custom
      OpenAI-compatible / OpenAI; remote prompts to enable egress; `/model show` =
      table. (Anthropic deferred — needs a native `/v1/messages` adapter.)
- [x] No fabricated default model: `default_config` ships empty `model` (status shows
      `none`) instead of a `qwen3:32b` placeholder
- [x] Works with local **and** remote OpenAI-compatible endpoints (remote opt-in)
- [x] `/summarize <id>` — LLM summary of an Item, persisted — REPL + `shelf summarize`
- [x] `/ask <q>` + free-text chat — library-grounded answer — REPL + `shelf ask`
- [ ] Summary-on-clip/import (opt-in), streaming, keyring-backed API keys (later)

## Phase 3 — Topic discovery
- [x] **`tools/` layer**: uniform `Tool` interface + registry + composable toolsets
      (Hermes-style, dependency-light). Built-ins: `library_search`, `fetch_url`,
      `web_search` (gated), `propose_source`. (`fs`/`diff`/`export`/MCP tools land in
      their owning phases.)
- [x] **`skills/` layer**: SKILL.md (frontmatter + body), lazy load, progressive
      disclosure; `explore` skill shipped.
- [x] **`agent/` harness** (Agent Orchestrator): text tool-call protocol + tolerant
      JSON repair + ReAct loop with bounded retries / step budget — works on small
      local models (no native function-calling required).
- [x] **`/explore`** end-to-end (REPL + `shelf explore`): search → read → propose
      candidates (`status='candidate'` + pending review item, never auto-watched) →
      cited brief. Topic row created; egress gated + announced. Live step trace +
      stop reason; **configurable step budget** (`--steps`, default 12).
- [x] **`/track`** (REPL + `shelf track`): mark a topic tracked + refresh frequency
      (records intent; collection is the Phase-4 watcher).
- [x] **`/compile`** (REPL + `shelf compile`): agent-driven cited brief/landscape/FAQ/
      timeline from the library, saved under `Compilations/` (`compile` skill+toolset).
- [x] lightweight scoring (`propose_source` accepts `relevance`/`authority` → score
      columns, shown in `/sources`) + query-variation guidance in the explore skill.
- [ ] full 9-axis source **scoring** as a dedicated pass (columns exist; only
      relevance/authority are set today).
- [ ] (RAG, deferred) embedding/keyword retrieval over `.shelf/normalized/*` bodies for
      `/ask` — needs a vector index (new dependency); intentionally out of scope so far.

## Phase 4 — Watcher
- [ ] APScheduler daemon, snapshot hash, text+semantic diff, review queue, weekly digest

## Phase 5 — TUI UX
- [ ] Textual app: command palette, `/review`, `/watch`, `/compile` wizards, diff viewer, approval UI

## Phase 6 — Notion sync
- [ ] schema creation, curated sync, review-queue status import, conflict handling, rate-limit retry

## Phase 7 — MCP
- [ ] stdio/http registry, trust levels, permission prompts, data-to-send preview

## Cross-cutting (later)
- [ ] Secrets via keyring · transaction log + `/rollback` · `/privacy` audit
- [ ] Vector index (LanceDB/Chroma) + semantic `/search`
- [ ] ruff + mypy in CI · pytest-httpx/vcrpy for ingestion regression
