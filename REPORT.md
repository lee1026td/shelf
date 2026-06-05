# shelf 구현 리포트 (Phase 0 + Phase 1)

> 이 문서는 지금까지 구현한 내용을 **Phase 단위로** 정리한 리포트입니다.
> 각 Phase마다 **① 목표 → ② 구현 내용 → ③ 실제 산출물 → ④ 직접 확인 방법 →
> ⑤ 발견·수정한 이슈** 순서로 적어, 코드를 열어보지 않아도 무엇이 만들어졌고 어떻게
> 검증하는지 따라올 수 있도록 했습니다. 본문의 콘솔 출력/파일 내용은 모두 실제로
> 실행해 캡처한 것입니다.

- 제품 정의·원칙·전체 로드맵: `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`
- 데이터 스키마: `SCHEMA.md` · 명령 목록: `COMMANDS.md` · 작업 보드: `TASKS.md`
- 현재 테스트: **102개 전부 통과**

---

## 0. 한눈에 보기

| 구분 | 상태 | 핵심 |
|---|---|---|
| **Phase 0** 워크스페이스 골격 | ✅ 완료 | `shelf init`, 디렉토리 레이아웃, SQLite, config, `/status`, **REPL** |
| **Phase 1** 로컬 라이브러리 | ✅ 완료 | `/clip`(URL→Item), `/import`(로컬 파일→Items), 파싱, 스냅샷, 원장(ledger) |
| Phase 2~7 | ⏳ stub | LLM/discovery/watcher/TUI/Notion/MCP — 인터페이스만, 호출 시 `FeatureNotReady` |

핵심 설계 원칙(헌법)은 모든 구현에 공통 적용됩니다: **로컬이 정본(canonical)**,
Notion은 선택적 표면 / **쓰기 전 계획·승인** / **discover는 자유, watch는 신중** /
**모든 주장에 출처(citation)** / **외부 전송은 항상 가시화** / **TUI 우선**.

---

## 검증 방법 (How to verify) — 5분 안에 직접 확인

```powershell
# 1) 설치
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2) 테스트 (102개)
.\.venv\Scripts\python.exe -m pytest -q

# 3) 워크스페이스 만들고 라이브러리에 자료 넣어보기
.\.venv\Scripts\shelf.exe init .\MyLibrary
.\.venv\Scripts\shelf.exe import .\some_folder --workspace .\MyLibrary   # 로컬 파일 가져오기
.\.venv\Scripts\shelf.exe clip https://example.com --workspace .\MyLibrary  # URL 저장
.\.venv\Scripts\shelf.exe status --workspace .\MyLibrary                 # 상태 확인

# 4) REPL (그 디렉토리에서 'shelf'만 입력)
cd .\MyLibrary; ..\.venv\Scripts\shelf.exe
#   shelf> /status   /import <path>   /clip <url>   /help   /exit
```

> 이 리포트의 모든 예시는 저장소 안의 `_demo/`(gitignore됨) 워크스페이스에서 실제로
> 생성한 결과입니다. 직접 재현하려면 위 절차를 따라 하시면 동일하게 나옵니다.

---

# Phase 0 — 워크스페이스 골격 + 기반

## 0.1 목표

"사용자가 자연어 주제를 던지면 source를 발견하고 cited artifact로 편찬한다"는 제품의
**바닥(state 관리)** 을 먼저 단단히 깐다. LLM 답변 품질이 아니라 **library state를 얼마나
안정적으로 관리하는가**가 제품 품질이므로(기획서 §6), 저장소·워크스페이스·설정·상태표시를
가장 먼저 진짜로 만들고 나머지는 phase별 stub로 둔다.

## 0.2 구현 내용 (모듈별)

| 모듈 | 책임 |
|---|---|
| `shelf.errors` | 사용자向 에러 계층. CLI가 `ShelfError`만 잡아 traceback 대신 깔끔한 메시지+exit 1. stub은 `FeatureNotReady(phase=N)` |
| `shelf.config` | dataclass 설정 모델 + YAML 로드/저장. local-only 기본값 |
| `shelf.workspace` | 디렉토리 레이아웃 정의(`layout`), 경로/탐색(`paths`), 생성(`initializer`) |
| `shelf.store` | SQLite 메타데이터 — 8개 핵심 객체 스키마, counts, CRUD, 마이그레이션 |
| `shelf.ui` | Rich 출력 컴포넌트(상태 패널 + 상태바). 표현 전용 |
| `shelf.cli` | Typer 진입점, `init`/`status`/`version`/`chat`, 통일된 에러 처리 |
| `shelf.repl` | bare `shelf` 진입 REPL(thin shell) |
| `shelf.services` | CLI와 REPL이 공유하는 앱 서비스(`gather_status`) |
| `shelf.library` | 도메인 값 객체(dataclass) — 저장소와 무관 |

## 0.3 산출물 ① — 로컬 디렉토리 레이아웃 (`shelf init`이 생성)

`shelf init <경로>`를 실행하면 기획서 §7.3의 구조가 그대로 만들어집니다. Notion 없이도
완전히 동작하는 **사람이 읽을 수 있는 정본 형태**입니다.

```
<root>/
  Dashboard.md
  Inbox/            review_queue.md
  Topics/           (주제별: topic.yaml, README.md, sources.md, candidates.md, digests/, compilations/, watch_runs/)
  Sources/          (<slug>.source.yaml)
  Items/            YYYY/MM/<slug>.md      ← 수집된 글/문서
  Wiki/             (living wiki 페이지)
  Digests/  Compilations/
  Review/           pending/ approved/ rejected/ stale_claims/
  Ledgers/          source_ledger.jsonl   claim_ledger.jsonl   (append-only 감사 로그)
  .shelf/           (기계 상태 — 정본 아님)
    config.yaml     library.sqlite   jobs.sqlite
    index/  snapshots/  normalized/  cache/
```

## 0.4 산출물 ② — `.shelf/config.yaml` (실제 생성물)

`shelf init`이 쓴 기본 설정입니다. **완전 local-only**(Notion off, 모든 remote off)이며,
민감정보(토큰/키)는 여기 저장하지 않습니다(추후 OS 키체인).

```yaml
version: 1
workspace:
  name: Library2
  root: C:\Users\pc21\Desktop\shelf\_demo\Library2
  created_at: '2026-06-05T10:27:25Z'
models:
  planner:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3:32b
    capabilities: {tools: false, json_schema: partial, vision: false, embeddings: false}
  embeddings:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: nomic-embed-text
    capabilities: {tools: false, json_schema: false, vision: false, embeddings: true}
notion:
  enabled: false
  sync_mode: 'off'          # YAML의 off→False 함정 방어를 위해 문자열로 저장
privacy:
  remote_search: false
  remote_llm: false
  remote_mcp: false
```

## 0.5 산출물 ③ — SQLite 메타데이터 스키마 (`.shelf/library.sqlite`)

기획서 §6.1의 **8개 핵심 객체 전부**를 테이블로 만들었습니다(스키마 전문은 `SCHEMA.md` §1
및 `src/shelf/store/schema.sql`).

| 테이블 | 의미 | 비고 |
|---|---|---|
| `topics` | 추적 주제 | slug, intent, collections(JSON), discovery/output policy |
| `sources` | 추적 가능한 출처 | 상태 7종(pinned/watched/candidate/ephemeral/muted/rejected/failing), 9개 score 축 |
| `items` | 수집된 글/문서 | status='new'면 inbox로 집계, `local_path` |
| `item_topics` | item↔topic 다대다 | |
| `snapshots` | 수집 당시 콘텐츠 버전 | content hash, raw/normalized 경로 |
| `claims` | 출처 근거 주장 | evidence_refs, stale_status |
| `review_items` | 사용자가 판단할 단위 | status='pending'면 review로 집계 |
| `compilations` | 편찬 산출물 | kind(brief/market_map/...) |
| `watch_runs` | watcher 실행 결과 | |

> 설계 의도: **SQLite는 인덱스, 파일시스템(Markdown/YAML)이 정본.** 스키마는 나중에
> 파일시스템에서 SQLite를 재구성(rebuild)할 수 있도록 설계 — DB가 날아가도 라이브러리는 생존.

## 0.6 산출물 ④ — `/status` 와 REPL

`shelf status`(= `/status`)는 Rich 패널 + 기획서 §4.2의 정규 상태바를 출력합니다:

```
[Shelf: ~/ResearchLibrary] [model: qwen3:32b] [remote: off] [sources: 0] [inbox: 0] [review: 0]
```

또한 당신의 의도("그 디렉토리에서 `shelf`만 치면 REPL")를 반영해, 워크스페이스 안에서
bare `shelf`(또는 `shelf chat`)가 **REPL(thin shell)** 로 진입합니다. `/status`·`/help`·
`/clip`·`/import`·`/exit`는 실제 동작하고, 아직 미구현인 슬래시/자유텍스트는 담당 phase를
안내합니다. (풀 Textual command-palette TUI는 Phase 5.)

## 0.7 Phase 0에서 발견·수정한 이슈 (적대적 멀티에이전트 리뷰)

구현 후 7개 차원 × 독립검증 리뷰를 돌려 **9건**을 수정했습니다. 가장 중요한 발견은
**cp949 콘솔 크래시**였습니다:

> 이 PC의 콘솔 코드페이지가 **cp949(한국어 Windows)** 인데, Rich는 `✓ ✗ … —` 같은
> 비-cp949 글자를 출력할 때 `UnicodeEncodeError`로 **크래시**합니다(박스문자만 ASCII로
> 자동 다운그레이드, 본문 텍스트는 안 함). → 콘솔에 닿는 모든 **정적 텍스트를 ASCII로**
> 통일하고, 재발 방지 테스트(`test_encoding.py`)를 추가.

그 외: `status`가 DB 없을 때 raw traceback 대신 깔끔히 실패, YAML `off`→bool 함정,
따옴표 친 `"false"`가 `True`로 읽히던 config 버그, 파이프 입력의 BOM 처리 등.

---

# Phase 1 — 로컬 라이브러리 모드 (`/clip`, `/import`)

## 1.1 목표

Notion·웹검색·LLM 없이도, **로컬 파일과 URL을 라이브러리로 가져와** 출처가 보존된 Item으로
저장한다. 즉 "수집(ingestion)"의 실제 동작을 만든다. (기획서 Phase 1: `/clip`, `/import`,
HTML/PDF 파싱, 로컬 Markdown 출력, source ledger.)

## 1.2 처리 파이프라인

`/clip`(URL)과 `/import`(로컬 파일)는 같은 골격을 공유합니다:

```
입력(URL 또는 파일)
  → fetch        (URL: HttpFetcher / 파일: read_bytes)        # 원본 bytes
  → detect_kind  (content-type 우선, 없으면 확장자)            # html|markdown|text|pdf
  → parse        (BeautifulSoup / pypdf / markdown / text)     # ParsedDocument(title, text)
  → write_snapshot   .shelf/snapshots/<hash>.<ext>             # 원본 (content-hash 중복제거)
                     .shelf/normalized/<hash>.<kind>.md        # 정규화 텍스트
  → write_item       Items/YYYY/MM/<slug>.md                   # YAML frontmatter + 본문
  → DB 기록          items / (clip은) sources / snapshots       # SQLite 인덱스
  → append_ledger    Ledgers/source_ledger.jsonl               # append-only 감사 로그
```

- **clip**은 URL의 도메인을 `ephemeral` source로 만들어 둡니다(나중에 `/track`으로 승격 가능).
- **import**의 항목은 `source_id=NULL`(로컬 파일은 watch 대상 source가 아니므로) — 원칙
  "discover는 자유, watch는 신중"의 반영.
- 둘 다 Item은 `status='new'`로 들어가 **inbox**에 쌓이고, 사용자가 나중에 검토(Phase 5).

## 1.3 구현 모듈 (`shelf.ingestion`)

| 파일 | 역할 |
|---|---|
| `base.py` | `FetchResult`, `ParsedDocument`, `Fetcher`/`Parser` 프로토콜, `PARSER_VERSION` |
| `parsers.py` | `detect_kind` + `parse_html/markdown/text/pdf` (순수 함수, 네트워크 無) |
| `fetch.py` | `HttpFetcher` (http/https/file 허용, 그 외 스킴 차단, 크기 상한) |
| `writers.py` | `write_item`(frontmatter), `write_snapshot`(중복제거), `append_source_ledger` |
| `clip.py` | `clip_url()` 서비스 + `ClipOutcome` |
| `importer.py` | `import_path()` 서비스 + `ImportOutcome`/`ImportedFile` |

부가: `shelf.util`(slugify/sha256/utc), `shelf.store.add_snapshot`+`savepoint`,
`shelf.ui.ingest_view`(결과 렌더), CLI `shelf clip`/`shelf import`, REPL `/clip`/`/import`.

## 1.4 산출물 — 실제 실행 결과

### (a) `shelf import <폴더>` — 로컬 파일 4종(md/txt/pdf/html) 가져오기

```
       imported 4 file(s) from C:\Users\pc21\Desktop\shelf\_demo\samples
+-----------------------------------------------------------------------------+
| Kind     | Title                          | Item path                       |
|----------+--------------------------------+---------------------------------|
| markdown | Research Notes                 | Items/2026/06/research-notes.md  |
| text     | Plain text note about watchers | Items/2026/06/plain-text-note-.. |
| pdf      | shelf (가칭)                    | Items/2026/06/shelf-가칭.md      |
| html     | Local-First Document Agents    | Items/2026/06/local-first-doc-.. |
+-----------------------------------------------------------------------------+
```

> PDF는 실제 제품기획서 PDF의 1쪽을 잘라 넣은 것으로, pypdf가 본문 텍스트를 추출했습니다.
> 한국어 제목 `shelf (가칭)`은 파일명에 그대로 보존됩니다(`shelf-가칭.md`). 좁은 콘솔에서
> 비-cp949 글자가 섞이면 `??`로 **degrade(안전)** 되지만, 파일 내용(UTF-8)은 온전합니다.

### (b) `shelf clip file:///.../sample_article.html` — URL 저장

```
+------------------------ clipped -------------------------+
|    Title  Local-First Document Agents                    |
|   Source  local-file (ephemeral)                         |
|     Item  Items/2026/06/local-first-document-agents-2.md |
| Snapshot  74f3f22e9e7d7c4f...                            |
+----------------------------------------------------------+
```

> `file://`는 의도적으로 허용(로컬-우선: 로컬 파일도 clip 가능). `ftp://` 등 다른 스킴은 차단.
> 같은 콘텐츠를 import(html)와 clip(html)으로 두 번 넣었더니 **스냅샷 파일은 1개로 중복제거**
> (해시 동일), Item만 `-2` 접미사로 별개 생성됩니다.

### (c) 생성된 Item 파일 (실제 내용)

`Items/2026/06/research-notes.md` (markdown import):

```markdown
---
title: Research Notes
url: file:///C:/Users/pc21/Desktop/shelf/_demo/samples/notes.md
captured_at: '2026-06-05T10:27:26Z'
kind: markdown
summary: '# Research Notes'
---

# Research Notes

- topic-first discovery
- semantic diff
- compilation
```

`Items/2026/06/local-first-document-agents-2.md` (html clip):

```markdown
---
title: Local-First Document Agents
url: file:///C:/Users/pc21/Desktop/shelf/_demo/samples/sample_article.html
captured_at: '2026-06-05T10:27:27Z'
kind: html
source: local-file
summary: Local-First Document Agents
---

Local-First Document Agents

Local-first agents keep raw snapshots, parsed text, and a source ledger in a local canonical store.

Notion is an optional surface, not the canonical archive.
```

### (d) `Ledgers/source_ledger.jsonl` (append-only 감사 로그, 실제 내용)

import 4건 + clip 1건이 출처/대상/해시까지 기록됩니다. 한국어 경로/제목은 `ensure_ascii=False`로 보존:

```json
{"event": "import", "at": "2026-06-05T10:27:26Z", "file": ".../notes.md", "item": "Items/2026/06/research-notes.md", "item_id": 1, "kind": "markdown"}
{"event": "import", "at": "2026-06-05T10:27:26Z", "file": ".../readme.txt", "item": "Items/2026/06/plain-text-note-about-watchers-and-weekly-digests.md", "item_id": 2, "kind": "text"}
{"event": "import", "at": "2026-06-05T10:27:26Z", "file": ".../sample.pdf", "item": "Items/2026/06/shelf-가칭.md", "item_id": 3, "kind": "pdf"}
{"event": "import", "at": "2026-06-05T10:27:27Z", "file": ".../sample_article.html", "item": "Items/2026/06/local-first-document-agents.md", "item_id": 4, "kind": "html"}
{"event": "clip", "at": "2026-06-05T10:27:27Z", "url": "file:///.../sample_article.html", "source": "local-file", "item": "Items/2026/06/local-first-document-agents-2.md", "item_id": 5, "hash": "74f3f22e...", "kind": "html"}
```

### (e) 스냅샷 디렉토리 (`.shelf/`) — 원본 + 정규화

```
.shelf/snapshots/<hash>.md        ← markdown 원본
.shelf/snapshots/<hash>.html      ← html 원본
.shelf/snapshots/<hash>.pdf       ← pdf 원본 (바이트 그대로)
.shelf/snapshots/<hash>.txt       ← text 원본
.shelf/normalized/<hash>.markdown.md   ← 정규화 텍스트 (kind별로 키 분리)
.shelf/normalized/<hash>.html.md
.shelf/normalized/<hash>.pdf.md
.shelf/normalized/<hash>.text.md
```

### (f) `shelf status` — 가져온 결과가 카운트에 반영

```
+----------------- shelf status ------------------+
|       Workspace  Library2                       |
|            Root  ~/Desktop/shelf/_demo/Library2 |
| Model (planner)  qwen3:32b                      |
|          Remote  off                            |
|          Schema  v1                             |
|          Topics  0   Sources  1   Items  5      |
|     Inbox (new)  5   Pending review  0          |
+-------------------------------------------------+
[Shelf: ~/Desktop/shelf/_demo/Library2] [model: qwen3:32b] [remote: off] [sources: 1] [inbox: 5] [review: 0]
```

- **Items 5** = import 4 + clip 1, 모두 `inbox`(status='new').
- **Sources 1** = clip이 만든 `local-file` ephemeral source 1개(import는 source 안 만듦).

## 1.5 데이터 모델 매핑 (파일 ↔ DB)

| 디스크 (정본) | SQLite (인덱스) |
|---|---|
| `Items/YYYY/MM/<slug>.md` | `items.local_path` (상대·POSIX 경로) |
| `.shelf/snapshots/<hash>.<ext>` | `snapshots.raw_path` |
| `.shelf/normalized/<hash>.<kind>.md` | `snapshots.normalized_path` |
| `Ledgers/source_ledger.jsonl` | (감사 로그, DB와 병행) |
| clip의 도메인 | `sources` (status='ephemeral') |

경로는 모두 **워크스페이스 루트 기준 상대 POSIX 경로**로 저장 → 라이브러리를 통째로 옮겨도 유효.

## 1.6 직접 확인 방법

```powershell
# 임의 폴더(md/html/txt/pdf 섞여 있어도 됨)를 가져오고 결과 보기
.\.venv\Scripts\shelf.exe import .\내문서폴더 --workspace .\MyLibrary
.\.venv\Scripts\shelf.exe status --workspace .\MyLibrary
# 생성물 직접 열어보기:  MyLibrary\Items\...  /  MyLibrary\Ledgers\source_ledger.jsonl
# 계획만 보고 안 쓰기:
.\.venv\Scripts\shelf.exe import .\내문서폴더 --workspace .\MyLibrary --dry-run
```

## 1.7 적대적 리뷰와 수정 (22건 검증 → 핵심 수정 반영)

Phase 1도 6개 차원 × 독립검증(29 에이전트) 리뷰를 돌렸고, 확인된 22건(다수는 같은 버그의
다른 관점)을 아래와 같이 **모두 코드/테스트로 반영**했습니다.

| 심각도 | 발견 | 수정 |
|---|---|---|
| **High** | `parse_html`이 `<body>` 없는 조각 HTML에서 `<title>`을 본문에 누설 | `<title>`을 본문 추출 전에 제거 + 회귀 테스트 |
| **High** | `import .`가 워크스페이스 **자기 자신**(`.shelf/`, `Items/`)을 재수집(자기복제) | `Workspace.is_internal_path()`로 내부 경로 전부 제외 + 테스트 |
| Medium | 쿼리스트링 URL(`report.pdf?v=2`)에서 확장자 판별 실패 | `urlsplit().path`로 쿼리/프래그먼트 제거 |
| Medium | `HttpFetcher`가 `file://`·`ftp://` 등 임의 스킴 허용 | http/https/file 허용목록, 그 외 차단(+크기 상한) |
| Medium | 한 파일 실패가 같은 트랜잭션의 다른 행을 오염(부분 커밋) | 파일별 SQLite `SAVEPOINT`(원자성) + 테스트 |
| Low | `parse_pdf`가 pypdf의 `DependencyError`(비 PyPdfError) 미포착 → /clip raw 크래시 | 모든 pypdf 예외를 `IngestionError`로 래핑 |
| Low | `slugify`가 Windows 예약어(con/nul/com1...) 파일명 생성 가능 | 예약어면 `_` 접두사 |
| Low | 정규화 스냅샷이 kind 구분 없이 digest만으로 중복제거 → 다른 파싱과 충돌 가능 | 파일명에 kind 포함(`<hash>.<kind>.md`) |
| Low | `read_bytes()`/`response.read()` 무제한(거대 파일 OOM) | import/fetch에 크기 상한 |
| (테스트 갭) | 자기복제·스냅샷 중복제거·content-type 우선·상대경로·dry-run 파일미생성·`ensure_safe_streams` 등 미검증 | 회귀 테스트 다수 추가 |

**검증**: 수정 후 실제 콘솔에서 `shelf import <라이브러리>`를 돌리면 내부 파일 20개를
**"inside workspace library"** 로 전부 건너뛰고 아무것도 추가하지 않습니다(Items 5 유지) —
자기복제 버그가 닫혔음을 확인했습니다.

추가로, Phase 1은 임의 콘텐츠(웹 글 제목 등 비-ASCII)를 다루므로, 콘솔이 비-cp949 글자에서
크래시하지 않도록 `ensure_safe_streams()`(stdout/stderr `errors='backslashreplace'`)를
진입점에 추가했습니다. 우리 메시지는 ASCII로 유지하되, **사용자 콘텐츠는 안전하게 degrade**됩니다.

## 1.8 추가된 의존성 (Phase가 처음 필요로 할 때만 추가하는 원칙)

- `beautifulsoup4` — HTML 본문/제목 추출 (stdlib `html.parser` 사용, lxml 불필요)
- `pypdf` — PDF 텍스트 추출
- (이전 Phase) `typer`, `rich`, `pyyaml`, `prompt_toolkit`

> Docling/Unstructured(기획서의 1순위)와 trafilatura는 더 풍부한 파서로, **다음 단계 업그레이드**로
> 남겨 두었습니다. 지금은 경량·순수 파이썬 조합으로 실제 동작 + 빠른 테스트를 우선했습니다.

---

## 2. 테스트 (102개 전부 통과)

| 파일 | 개수 | 검증 대상 |
|---|---:|---|
| `test_config.py` | 6 | 기본값(local-only), YAML 라운드트립, `off` 함정, 문자열 boolean |
| `test_workspace.py` | 7 | 레이아웃 생성, `--force` 보존, 탐색(cwd/`$SHELF_HOME`) |
| `test_store.py` | 8 | 전체 테이블 생성, counts, CRUD, 컨텍스트매니저 커밋 |
| `test_status.py` | 4 | 상태바 포맷/홈 축약, 패널 렌더 |
| `test_cli.py` | 12 | `--help`/version/init→status, 0이 아닌 counts, 손상 DB 깔끔실패, bare shelf→REPL |
| `test_repl.py` | 15 | 슬래시 디스패치, 루프, BOM/mojibake, `/clip`·`/import` |
| `test_stubs.py` | 14 | 각 stub이 올바른 phase로 `FeatureNotReady` |
| `test_encoding.py` | 6 | 콘솔 ASCII 계약 + `ensure_safe_streams` |
| `test_util.py` | 6 | slugify(유니코드/예약어/fallback), sha256 |
| `test_ingestion.py` | 13 | 파서(html/md/text/pdf), clip, import, dry-run, 유니코드 |
| `test_ingestion_hardening.py` | 11 | 리뷰 회귀: title 누설, 자기복제 제외, 스냅샷 중복제거, 스킴 차단, SAVEPOINT 원자성, 상대경로 |
| **합계** | **102** | |

---

## 3. 현재 상태 — 완료 / 부분 / 보류

**완료(진짜 동작·테스트됨)**
- Phase 0: 패키지 골격, `init`/`status`/`version`/`chat`, REPL(thin shell), Rich UI,
  워크스페이스 레이아웃, SQLite(8객체), config, `gather_status` 공유 서비스
- Phase 1: `/clip`(URL→Item), `/import`(파일/폴더→Items), html/md/text/pdf 파싱,
  스냅샷(중복제거)+정규화, source ledger, `--dry-run`, 리뷰 하드닝 전부

**부분(토대만, 나머지 보류)**
- Phase 1 잔여: `Topics/`·`Sources/` YAML writer, 마크다운 인덱스 rebuild → 주제 개념이
  본격화되는 discovery(Phase 3)와 함께 구현 예정

**보류(의도적 stub — 호출 시 `FeatureNotReady`)**
- LLM gateway(P2) · 토픽 discovery/deep-research(P3) · watcher 데몬(P4) ·
  풀 Textual TUI(P5) · Notion sync(P6) · MCP(P7)

---

## 4. 다음 단계 제안

1. **Phase 2 — LLM gateway**: OpenAI-compatible 클라이언트 + capability probe + 요약카드.
   이게 들어오면 import/clip한 Item에 **요약(summary)** 을 실제 생성하고, REPL 자유텍스트
   chat이 동작하기 시작합니다.
2. **Phase 3 — 토픽 discovery**: 자연어 주제 → 웹검색 → source 후보 → scoring → 초기 brief.
   제품의 핵심 wedge가 처음으로 end-to-end 작동.
3. (대안) Phase 1 잔여 마무리: `/inbox`로 수집물 훑기 + `Topics`/`Sources` YAML 동기화.

> 작업 트리는 모두 untracked(커밋 안 함), `.venv`·`_demo/`는 gitignore. 원하시면
> 지금까지를 phase별 커밋으로 정리해 드릴 수 있습니다.
