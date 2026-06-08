# shelf — Data Schemas

Three coordinated schemas: **(1)** the SQLite metadata store, **(2)** the on-disk
directory layout + YAML/Markdown artifacts, and **(3)** `config.yaml`. SQLite is the
index; the filesystem is canonical (see `ARCHITECTURE.md` §6).

The SQLite section below mirrors `src/shelf/store/schema.sql` exactly. If you change
one, change both.

---

## 1. SQLite metadata schema (`.shelf/library.sqlite`)

`schema_version` is tracked in `schema_meta`. All timestamps are ISO-8601 UTC
strings. JSON-typed columns store serialized arrays/objects (SQLite has no native
array/JSON column; we use `TEXT` + `json` module).

### 1.1 `schema_meta`
| Column | Type | Notes |
|---|---|---|
| key | TEXT PK | e.g. `schema_version`, `created_at`, `shelf_version` |
| value | TEXT NOT NULL | |

### 1.2 `topics` — a tracked interest (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| slug | TEXT UNIQUE NOT NULL | filesystem-safe key, matches `Topics/<slug>/` |
| name | TEXT NOT NULL | |
| intent | TEXT | freeform description |
| status | TEXT NOT NULL = 'active' | `active` \| `paused` \| `archived` |
| collections | TEXT (JSON array) | e.g. `["ai-agents","mcp"]` |
| discovery_policy | TEXT (JSON) | `{known_source_check, open_web_refresh, ...}` |
| output_policy | TEXT (JSON) | `{outputs: [...]}` |
| created_at / updated_at | TEXT NOT NULL | |

### 1.3 `sources` — a trackable origin (plan §6.1–6.3)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| slug | TEXT UNIQUE NOT NULL | matches `Sources/<slug>.source.yaml` |
| url | TEXT NOT NULL | |
| name | TEXT | |
| role | TEXT | `expert_commentary` \| `docs` \| `changelog` \| `news` \| … |
| status | TEXT NOT NULL = 'candidate' | taxonomy below |
| topic_id | INTEGER FK→topics(id) ON DELETE SET NULL | |
| relevance / authority / originality / freshness / update_frequency / extractability / uniqueness / noise_risk / watchability | REAL | source score axes (0..1) |
| extraction_health | TEXT | `good` \| `degraded` \| `failing` |
| discovered_from | TEXT (JSON) | `{topic, run_id}` |
| created_at / updated_at | TEXT NOT NULL | |

Indexes: `idx_sources_status(status)`, `idx_sources_topic(topic_id)`.

**Source status taxonomy** (plan §6.2): `pinned`, `watched`, `candidate`,
`ephemeral`, `muted`, `rejected`, `failing`.

### 1.4 `items` — a collected article/document (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| source_id | INTEGER FK→sources(id) ON DELETE SET NULL | |
| title | TEXT | |
| url | TEXT | |
| published_at | TEXT | |
| captured_at | TEXT NOT NULL | |
| summary | TEXT | |
| novelty | REAL | |
| status | TEXT NOT NULL = 'new' | `new` \| `reviewed` \| `saved` \| `archived` \| `muted` |
| local_path | TEXT | `Items/YYYY/MM/<slug>.md` |
| created_at / updated_at | TEXT NOT NULL | |

Indexes: `idx_items_status(status)`, `idx_items_source(source_id)`.
`inbox` count in `/status` = items with `status='new'`.

### 1.5 `item_topics` — item↔topic many-to-many
| Column | Type | Notes |
|---|---|---|
| item_id | INTEGER FK→items(id) ON DELETE CASCADE | PK part |
| topic_id | INTEGER FK→topics(id) ON DELETE CASCADE | PK part |

### 1.6 `snapshots` — fetched content version (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| source_id | INTEGER FK→sources(id) ON DELETE CASCADE | |
| item_id | INTEGER FK→items(id) ON DELETE CASCADE | |
| hash | TEXT NOT NULL | content hash for change detection |
| raw_path | TEXT | `.shelf/snapshots/...` |
| normalized_path | TEXT | `.shelf/normalized/...` |
| fetched_at | TEXT NOT NULL | |
| parser_version | TEXT | |
| created_at | TEXT NOT NULL | |

Index: `idx_snapshots_hash(hash)`.

### 1.7 `claims` — source-backed assertion (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| claim_text | TEXT NOT NULL | |
| topic_id | INTEGER FK→topics(id) ON DELETE SET NULL | |
| evidence_refs | TEXT (JSON array) | snapshot/item references |
| confidence | REAL | |
| stale_status | TEXT NOT NULL = 'fresh' | `fresh` \| `stale` \| `unknown` |
| created_at / updated_at | TEXT NOT NULL | |

### 1.8 `review_items` — a unit the user must judge (plan §6.1, appendix C)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| type | TEXT NOT NULL | `source_candidate` \| `stale_claim` \| `failed_extraction` \| `wiki_patch` \| `item` |
| priority | TEXT NOT NULL = 'normal' | `high` \| `normal` \| `low` |
| status | TEXT NOT NULL = 'pending' | `pending` \| `approved` \| `rejected` \| `snoozed` \| `muted` |
| title | TEXT | |
| suggested_action | TEXT | |
| evidence | TEXT (JSON) | |
| ref_kind | TEXT | `source` \| `item` \| `claim` \| `compilation` |
| ref_id | INTEGER | id within ref_kind table |
| local_ref | TEXT | path under `Review/` |
| notion_ref | TEXT | Notion page id (optional) |
| created_at / updated_at | TEXT NOT NULL | |

Indexes: `idx_review_status(status)`, `idx_review_priority(priority)`.
`review` count in `/status` = review_items with `status='pending'`.

### 1.9 `compilations` — synthesized artifact (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| title | TEXT NOT NULL | |
| topic_id | INTEGER FK→topics(id) ON DELETE SET NULL | |
| kind | TEXT | `topic_brief` \| `market_map` \| `timeline` \| `faq` \| `literature_review` |
| source_count | INTEGER = 0 | |
| confidence | REAL | |
| output_path | TEXT | `Compilations/*.md` |
| created_at / updated_at | TEXT NOT NULL | |

### 1.10 `watch_runs` — a watcher execution (plan §6.1)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| topic_id | INTEGER FK→topics(id) ON DELETE SET NULL | |
| started_at | TEXT NOT NULL | |
| finished_at | TEXT | |
| sources_checked / new_items / changes / failures | INTEGER = 0 | |
| cost | REAL | |
| model_used | TEXT | |
| status | TEXT NOT NULL = 'completed' | `running` \| `completed` \| `failed` |

---

## 2. Local directory layout (plan §7.3)

Created by `shelf init`. This is the canonical, portable form of the library.

```
<root>/                         # e.g. ~/ResearchLibrary
  Dashboard.md                  # human overview, regenerated by status/rebuild
  Inbox/
    review_queue.md             # pending review summary (markdown mirror)
  Topics/
    <Topic Slug>/
      topic.yaml                # see §3.1
      README.md
      sources.md
      candidates.md
      digests/
      compilations/
      watch_runs/
  Sources/
    <slug>.source.yaml          # see §3.2
  Items/
    YYYY/MM/<slug>.md           # article metadata + summary + snapshot ref
  Wiki/
    <area>/<page>.md            # living wiki pages
  Digests/
    YYYY-Www_<topic>.md
  Compilations/
    <slug>.md
  Review/
    pending/  approved/  rejected/  stale_claims/
  Ledgers/
    source_ledger.jsonl         # append-only audit of source lifecycle
    claim_ledger.jsonl          # append-only audit of claims
  .shelf/                       # machine state (not the canonical artifacts)
    config.yaml                 # see §4
    library.sqlite              # §1
    jobs.sqlite                 # scheduler/job state (Phase 4)
    index/                      # vector index (Phase 2/3)
    snapshots/                  # raw fetched content
    normalized/                 # normalized/parsed text
    cache/
```

---

## 3. YAML artifact schemas (plan appendix)

### 3.1 `Topics/<slug>/topic.yaml`
```yaml
name: Local-first Document Agents
status: active                 # active | paused | archived
intent: >
  Track document collection, summarization, compilation, and local-model agents.
collections: [ai-agents, local-llm, mcp]
discovery_policy:
  known_source_check: weekly
  open_web_refresh: monthly
  source_candidate_review: monthly
source_policy:
  auto_save_items: true
  auto_add_watchers: false       # watchlist never auto-grows
  require_approval_for_new_domains: true
outputs: [weekly_digest, living_wiki, source_map, stale_claim_report]
```

### 3.2 `Sources/<slug>.source.yaml`
```yaml
url: https://example.com/engineering-blog
name: Example Engineering Blog
role: expert_commentary
status: candidate                # see status taxonomy §1.3
discovered_from:
  topic: Local-first Document Agents
  run_id: discovery_2026_0604_001
score:
  relevance: 0.86
  authority: 0.72
  watchability: 0.81
  noise_risk: 0.35
extraction_health: good
suggested_mode: weekly_digest
recommended_action: add_to_watchlist_after_review
```

### 3.3 Review item (mirrored to `Review/pending/*.md` frontmatter)
```yaml
type: source_candidate
priority: high
status: pending
title: Add Example Engineering Blog to AI Agents topic
why_suggested:
  - 4 recent posts matched this topic
  - RSS feed available
  - extraction succeeded on sampled pages
suggested_action: watch_weekly_digest
evidence:
  - snapshot_id: snap_2026_0604_001
  - sample_items: 4
user_actions: [approve, save_as_candidate, mute_domain, reject]
```

---

## 4. `config.yaml` schema (`.shelf/config.yaml`)

Written by `shelf init`, loaded by `shelf.config.loader`. Secrets are **not** stored
here — only flags and non-sensitive endpoints. Tokens/keys go in the OS keychain
(keyring) in later phases.

```yaml
version: 1
workspace:
  name: ResearchLibrary
  root: /abs/path/to/ResearchLibrary
  created_at: "2026-06-05T12:00:00Z"
models:                          # OpenAI-compatible role profiles (plan §11.1)
  planner:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: ""                    # empty by default — pick a real one via `/model`
    capabilities: {tools: false, json_schema: partial, vision: false, embeddings: false}
  embeddings:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: ""                    # empty by default — pick a real one via `/model`
    capabilities: {tools: false, json_schema: false, vision: false, embeddings: true}
notion:
  enabled: false
  sync_mode: off                 # curated | metadata_only | full | off  (plan §7.4)
privacy:                         # egress gates (plan §11.3) — all off by default
  remote_search: false
  remote_llm: false
  remote_mcp: false
```

`capabilities` values: `json_schema` may be `true | partial | false` (string or
bool accepted on load); the rest are booleans. The gateway (Phase 2) must probe and
not assume these are accurate.
