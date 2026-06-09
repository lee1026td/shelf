# shelf — Command Surface

shelf is **TUI-first**: slash commands are entry points to guided workflows, not
argument-heavy invocations. Inside a workspace, bare `shelf` opens a **REPL** where
the user types `/status` etc.; the same slash commands also exist as `shelf <name>`
subcommands for scripting. Arguments are an *advanced accelerator* layer — the
default path is a guided flow.

**Status legend:** ✅ implemented · 🧩 stub (interface defined, raises
`FeatureNotReady`) · 🗓️ planned (no module yet).

## 1. CLI commands implemented now

| CLI | Slash | Status | Description |
|---|---|---|---|
| `shelf` (no args) | — | ✅ | Inside a workspace: open the **chat** — the Textual **TUI** on a terminal, the line **REPL** when piped. Outside: hint to run `shelf init`. |
| `shelf init [PATH]` | — | ✅ | Create a local research-library workspace (dirs, `config.yaml`, SQLite). `--name`, `--force`. |
| `shelf status` | `/status` | ✅ | Show workspace, model, remote posture, and counts (sources/inbox/review). `--workspace`. |
| `shelf clip URL` | `/clip` | ✅ | Fetch a URL (http/https/file) and save it as an Item. `--dry-run`, `--workspace`. |
| `shelf import PATH` | `/import` | ✅ | Import local PDF/HTML/Markdown/text into Items. `--dry-run`, `--no-recursive`. |
| `shelf inbox` | `/inbox` | ✅ | List newly collected items (status='new'). `--limit`. |
| `shelf search Q` | `/search` | ✅ | Keyword search over items (title/summary/url). |
| `shelf sources` | `/sources` | ✅ | List the source universe by status. |
| `shelf model [list\|set\|use]` | `/model` | ✅ | On a TTY, bare `/model` opens an interactive **picker** (role → provider → model): pick **planner** (chat) or **embeddings**, then a provider — Ollama / Custom OpenAI-compatible endpoint / OpenAI (Anthropic is parked — it needs a native adapter) — then the model. `/model planner` and `/model embeddings` jump straight to that role. A failed connection re-prompts the endpoint URL instead of faking success. `/model show` always prints the profile table + probe; `list [role]`, `set <role> <model> [--base-url]`, `use <model>` are the scripting layer. Remote endpoints prompt to enable `privacy.remote_llm` and read the key from `$SHELF_API_KEY` (never written to config). |
| `shelf ask Q` | `/ask` | ✅ | Answer a question grounded in the library (also: type free text in the REPL). |
| `shelf explore TOPIC` | `/explore` | ✅ | Agent-driven source discovery: searches (library + web), reads pages, **proposes** candidate sources to the review queue (never auto-watched), and writes a cited brief. Runs the `shelf.agent` harness over the `discovery` toolset; works with small local models. Web search is gated by `privacy.remote_search` (egress, off by default): in the chat (TUI + REPL) `/explore` offers to enable it (y/N, persisted); the CLI uses `--web`. Step budget is configurable: `--steps N` (CLI) / `/explore <topic> --steps N` (REPL), default 12. A live trace of each step + a stop reason are printed. |
| `shelf track TOPIC` | `/track` | ✅ | Mark a topic as **tracked** with a refresh frequency (`--frequency weekly\|daily\|monthly`). Records intent only — sources stay in review until approved; periodic collection is the Phase-4 watcher. |
| `shelf compile TOPIC` | `/compile` | ✅ | Compile a **cited** document from the library (`--kind brief\|landscape\|faq\|timeline`, `--steps N`). Runs the harness over the `compile` toolset (read-only) and saves the Markdown under `Compilations/`. |
| `shelf summarize ID` | `/summarize` | ✅ | LLM-summarize an item and store the summary. |
| `shelf chat` | — | ✅ | Enter the research chat (same as bare `shelf`): TUI on a terminal, REPL when piped. |
| `shelf tui` | — | ✅ | Force the full-screen **Textual TUI**: scrollable transcript, bottom-docked input, `/` command dropdown, tool-call cards. |
| `shelf version` | — | ✅ | Print the installed shelf version. |

### The chat surface — TUI (Phase 5, first slice) + line REPL fallback

On an interactive terminal, `shelf` opens the **Textual TUI**: a scrollable transcript,
a bottom-docked input bordered by horizontal rules with a `>` prompt, a `/` dropdown that
lists matching commands as you type, and agent **tool calls rendered as cards** with a
live trace. When stdin/stdout is piped (scripts, tests), it falls back to the line **REPL**
below — same slash commands, same dispatch (`shelf.repl.session.ReplSession`).

```
$ shelf
shelf REPL - ResearchLibrary
[Shelf: ~/ResearchLibrary] [model: none] [remote: off] [sources: 0] [inbox: 0] [review: 0]
Type /help for commands, /exit to quit.
shelf> /status        # runs for real
shelf> /help          # lists every command + the phase that delivers it
shelf> /explore local-first software   # agent discovers + proposes sources, writes a brief
shelf> a free topic    # library-aware chat via the model gateway
shelf> /exit
```

- Commands available **now** (TUI + REPL): `/status`, `/clip <url>`, `/import <path>`,
  `/inbox`, `/search <q>`, `/sources`, `/save <id>`, `/mute <id>`, `/ask <q>`,
  `/summarize <id>`, `/model`, `/explore <topic>`, `/track <topic>`, `/compile <topic>`,
  `/help` (alias `/`, `/?`), `/exit` (aliases `/quit`, `/q`).
- **Free text** (no leading `/`) is a chat with the model: it converses normally and
  grounds in your library items only when relevant, citing the titles it used.
- Every other slash command is recognized and announces its phase (see §2).
- REPL input: prompt_toolkit (history/editing) on a TTY; `input()` fallback when piped.
  The TUI input adds the `/` command dropdown and Tab-completion.

### `shelf init`
```
shelf init ~/ResearchLibrary --name ResearchLibrary
```
- Creates the directory layout in `SCHEMA.md` §2.
- Writes default `.shelf/config.yaml` (local-only, remote off).
- Initializes `.shelf/library.sqlite` with the full schema.
- Refuses to overwrite an existing workspace unless `--force`.

### `shelf status`  ( `/status` )
Renders a Rich panel plus the canonical status bar (plan §4.2):
```
[Shelf: ~/ResearchLibrary] [model: qwen3:32b] [remote: off] [sources: 42] [inbox: 18] [review: 5]
```
- Resolves the workspace by `--workspace`, then `$SHELF_HOME`, then by walking up
  from the current directory for a `.shelf/` dir.
- Outside any workspace it prints a clean hint to run `shelf init` (exit 1).

## 2. Planned slash-command surface (plan §5)

These define the **target UX**. Each opens a guided TUI flow; the argument form
shown is the advanced layer. Modules backing them are stubbed or not-yet-created.

### 2.1 Explore / collect / track (plan §5.1)
| Slash | Status | Function | Guided flow |
|---|---|---|---|
| `/` | 🗓️ | Command palette | list + fuzzy search + recent + suggested next action |
| `/explore` | ✅ (`discovery`/`agent`/`tools`) | One-time research + source discovery from a topic | search (library + gated web) → read pages → propose candidates → cited brief |
| `/track` | ✅ (`services`) | Mark a topic as tracked + refresh frequency (collection = Phase 4 watcher) | topic → frequency → tracked |
| `/watch` | 🧩 (`watcher`) | Manage a source or watched topic | health dashboard → add/run/pause/mute/fix |
| `/sources` | ✅ | List the source universe by status | `shelf sources` / REPL `/sources` (full tabs UI: Phase 5) |
| `/clip` | ✅ (`ingestion`) | Save a URL / clipboard article now | URL → parse → Item + ephemeral source (REPL: `/clip <url>`) |
| `/import` | ✅ (`ingestion`) | Import a local PDF/HTML/Markdown folder | path → parse → Items (REPL: `/import <path>`) |

### 2.2 Review / summarize / compile (plan §5.2)
| Slash | Status | Function | Guided flow |
|---|---|---|---|
| `/inbox` | ✅ | List newly collected items + triage | `/inbox`, `/save <id>`, `/mute <id>` (high-signal grouping: later) |
| `/review` | 🧩 (`tui`) | Process candidates, stale claims, failed extractions, patches | pending → evidence → approve/reject/snooze/mute |
| `/digest` | 🧩 (`watcher`) | Generate a period/collection/topic digest | period → scope → threshold → generate |
| `/compile` | ✅ (`discovery`/`agent`) | Compile a cited brief/landscape/FAQ/timeline from the library | kind → read library/sources → cited draft → save to Compilations/ |
| `/wiki` | 🗓️ | Update/browse/rollback local wiki or Notion page | tree → stale page → patch → approve |
| `/diff` | 🧩 (`watcher`) | Review snapshot/wiki/compilation changes | before/after → semantic summary → evidence |
| `/search` | ✅ | Keyword search across collected items | `shelf search <q>` / REPL `/search <q>` (semantic search: Phase 3) |
| `/ask` | ✅ (`llm`) | Q&A grounded in the library | recent items as context → answer (web + full citations: Phase 3) |

### 2.3 Config / integration / safety (plan §5.3)
| Slash | Status | Function | Guided flow |
|---|---|---|---|
| `/model` | ✅ (`llm`) | Show OpenAI-compatible profiles + probe endpoint | `shelf model` / `/model` (interactive setup wizard: Phase 5) |
| `/mcp` | 🧩 (`mcp`) | Register/inspect local/remote MCP servers | add/list/inspect → trust → permission prompt |
| `/privacy` | 🗓️ | Audit egress paths and rules | show data-leaves-machine paths + rules |
| `/notion` | 🧩 (`notion`) | Manage Notion connection/schema/sync mode | token → parent page → DB create → sync mode |
| `/local` | 🗓️ (uses `workspace`) | Manage the Notion-free local workspace | folder tree → rebuild indexes → stale check → export |
| `/sync` | 🧩 (`notion`) | Sync to Notion or local markdown output | preview → conflict handling → apply |
| `/jobs` | 🧩 (`watcher`) | Monitor background jobs | running/failed/scheduled → retry/stop/resume |
| `/rules` | 🗓️ | Manage classification/scoring/threshold/style rules | list → add/edit/test → scope |
| `/export` | 🗓️ | Export Markdown/JSON/ZIP/Notion backup | format → scope → output path → generate |
| `/rollback` | 🗓️ | Revert recent wiki/sync/local-write transactions | transaction list → diff → approve |

## 3. Default command palette (plan §5.4)

What `/` should eventually show:
```
shelf> /
Commands
  /explore    Run source discovery and initial research on a topic of interest
  /track      Promote a research topic to a continuously tracked topic
  /review     Review new items, source candidates, stale claims, patches
  /digest     Generate a period/collection summary
  /compile    Compile accumulated material into a cited wiki/brief
  /wiki       Manage local wiki or Notion pages
  /model      Configure local/OpenAI-compatible models
  /privacy    Audit external egress and permissions
```

## 4. Mapping rules (slash ↔ CLI)

- A slash command `/<x>` maps to `shelf <x>` in the advanced CLI layer.
- Natural-language input (no leading `/`) routes through the intent router
  (Phase 3) to `/explore` or `/track`.
- Every mutation (`/clip`, `/track`, `/wiki`, `/sync`, `/compile`) must present a
  plan + diff and require approval before writing (plan §4.2, §11.3).
