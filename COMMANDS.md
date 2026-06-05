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
| `shelf` (no args) | — | ✅ | Inside a workspace: open the **REPL**. Outside: hint to run `shelf init`. |
| `shelf init [PATH]` | — | ✅ | Create a local research-library workspace (dirs, `config.yaml`, SQLite). `--name`, `--force`. |
| `shelf status` | `/status` | ✅ | Show workspace, model, remote posture, and counts (sources/inbox/review). `--workspace`. |
| `shelf clip URL` | `/clip` | ✅ | Fetch a URL (http/https/file) and save it as an Item. `--dry-run`, `--workspace`. |
| `shelf import PATH` | `/import` | ✅ | Import local PDF/HTML/Markdown/text into Items. `--dry-run`, `--no-recursive`. |
| `shelf chat` | — | ✅ | Enter the research REPL (same as bare `shelf`). |
| `shelf version` | — | ✅ | Print the installed shelf version. |

### The REPL (thin shell — full Textual TUI is Phase 5)

```
$ shelf
shelf REPL - ResearchLibrary
[Shelf: ~/ResearchLibrary] [model: qwen3:32b] [remote: off] [sources: 0] [inbox: 0] [review: 0]
Type /help for commands, /exit to quit.
shelf> /status        # runs for real
shelf> /help          # lists every command + the phase that delivers it
shelf> /explore ...    # Note: not implemented yet - planned for Phase 3
shelf> a free topic    # Note: chat routing - planned for Phase 2 (LLM) + 3 (discovery)
shelf> /exit
```

- REPL commands available **now**: `/status`, `/clip <url>`, `/import <path>`,
  `/help` (alias `/`, `/?`), `/exit` (aliases `/quit`, `/q`).
- Every other slash command is recognized and announces its phase (see §2).
- Free text (no leading `/`) will route to chat/`/explore` once Phase 2/3 land.
- Input: prompt_toolkit (history/editing) on a TTY; `input()` fallback when piped.

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
| `/explore` | 🧩 (`discovery`) | One-time research + source discovery from a topic | scope → search depth → source map → watch candidates |
| `/track` | 🧩 (`discovery`/`watcher`) | Promote a topic to a tracked topic | review sources → frequency → refresh policy → approve |
| `/watch` | 🧩 (`watcher`) | Manage a source or watched topic | health dashboard → add/run/pause/mute/fix |
| `/sources` | 🗓️ | Review the source universe | Pinned/Watched/Candidate/Muted/Rejected tabs |
| `/clip` | ✅ (`ingestion`) | Save a URL / clipboard article now | URL → parse → Item + ephemeral source (REPL: `/clip <url>`) |
| `/import` | ✅ (`ingestion`) | Import a local PDF/HTML/Markdown folder | path → parse → Items (REPL: `/import <path>`) |

### 2.2 Review / summarize / compile (plan §5.2)
| Slash | Status | Function | Guided flow |
|---|---|---|---|
| `/inbox` | 🗓️ | Skim newly collected items | high-signal / worth-saving / noise groups |
| `/review` | 🧩 (`tui`) | Process candidates, stale claims, failed extractions, patches | pending → evidence → approve/reject/snooze/mute |
| `/digest` | 🧩 (`watcher`) | Generate a period/collection/topic digest | period → scope → threshold → generate |
| `/compile` | 🧩 (`discovery`) | Compile a brief/landscape/FAQ/timeline | type → scope → draft → diff → apply |
| `/wiki` | 🗓️ | Update/browse/rollback local wiki or Notion page | tree → stale page → patch → approve |
| `/diff` | 🧩 (`watcher`) | Review snapshot/wiki/compilation changes | before/after → semantic summary → evidence |
| `/search` | 🗓️ | Keyword/semantic search across the library | query → filters → ranked → open/save/compile |
| `/ask` | 🧩 (`llm`) | Citation-backed Q&A over library + web | local-only/web → cited answer |

### 2.3 Config / integration / safety (plan §5.3)
| Slash | Status | Function | Guided flow |
|---|---|---|---|
| `/model` | 🧩 (`llm`) | Configure OpenAI-compatible endpoints + role profiles | provider → base_url → test → capability probe |
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
