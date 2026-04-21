# Execution Plan — Keluarga Mencatat (Telegram AI Finance Bot)

## Context

A Telegram bot for a 2–3 person family that turns "chat → financial record" with zero friction. All AI runs locally (privacy-first, no paid APIs); Google Sheets is the database. Ships on the existing home-server Docker Compose stack at `/Volumes/MyHDD/homeserver/`, joining Postgres/Redis/Traefik/Grafana that already run there. Ollama and Whisper.cpp are not yet present and must be added.

**Timeline:** 2 days for core + 1 buffer day.
- **Day 1–2 (core, must-ship):** text input → AI extraction → Google Sheets, whitelist auth, confirmation flow, Docker deploy.
- **Day 3 (buffer/stretch):** receipt OCR via LLaVA, voice via Whisper.cpp, chat analytics, polish.

**Stack locked:** aiogram 3.x, Ollama (as a new Docker service, models: `qwen2.5:7b` for text, `llava:7b` for vision), Whisper.cpp compiled into the bot image, `gspread` for Sheets.

**Assumptions (Day 1 provisioning):** Telegram bot token, Google Service Account JSON, and family Telegram user IDs all need to be created on Day 1 — none exist yet.

---

## 1. MVP Breakdown

### ✅ INCLUDED in 2-day core
- Telegram bot handling **text messages only** ("makan 50rb", "beli bensin 100000 transport")
- Whitelist authorization (Telegram ID list in `.env`)
- LLM extraction: `nominal`, `kategori`, `tipe_transaksi`, `keterangan` via Ollama/qwen2.5
- Confidence-based confirmation flow (inline keyboard Ya/Tidak)
- Category override (inline keyboard with predefined categories)
- Google Sheets append with UUID transaction ID
- Duplicate detection (±1 min + same nominal + same user)
- Edit-last-transaction command (`/ubah 120000`, `/kategori transport`)
- Retry logic for Sheets (3× exponential backoff)
- Rotating file logs
- Docker Compose deploy integrated into existing home-server stack

### ⏩ DAY 3 BUFFER (stretch)
- Receipt OCR via LLaVA (image → nominal + merchant)
- Voice input via Whisper.cpp → text pipeline
- Chat analytics ("pengeluaran minggu ini", "total makanan bulan ini") — simple `gspread` query + formatted reply
- Daily CSV backup cron

### ❌ EXCLUDED (Phase 2)
- Multi-sheet / multi-family support
- Budgets and goals
- Charts / images in analytics
- Web dashboard
- Income forecasting
- Auto-split bills
- Natural-language backlog processing after downtime
- Encrypted credential vault (just `.env` for MVP)

### 🔥 Risky features (watch closely)
| Feature | Risk | Mitigation |
|---|---|---|
| LLaVA receipt OCR | Slow (10–30s), inconsistent on Indonesian receipts | Defer to Day 3, fall back to manual input; if still shaky, drop to Phase 2 |
| Whisper.cpp compile in Docker | Build can be finicky; model download ~500MB–1.5GB | Use `ggml-small` (multilingual); pre-download during image build |
| ≥98% text extraction accuracy | LLM hallucinates or returns wrong JSON | Strict JSON schema in prompt + regex fallback for "nominal" (`\d+[kr]?|\d+ ?(rb|ribu|jt|juta)`) |
| 10s response budget | qwen2.5:7b on CPU can take 5–15s | Keep prompt short; use `num_predict: 128`; warm-start model at boot |
| Google Sheets rate limits | 60 writes/min/user; rare but possible | Single-writer queue; retries already budgeted |

---

## 2. Technical Architecture Plan

### Component breakdown

```
┌────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│  Telegram (user)   │───▶│  aiogram Dispatcher │───▶│  AuthMiddleware  │
└────────────────────┘    └─────────────────────┘    └────────┬─────────┘
                                                              │
                          ┌───────────────────────────────────┴──────────────┐
                          │                                                  │
                          ▼                                                  ▼
                 ┌────────────────┐                              ┌────────────────────┐
                 │  MessageRouter │                              │  CommandRouter     │
                 │ (text/photo/   │                              │ (/start, /ubah,    │
                 │  voice)        │                              │  /kategori, /help) │
                 └────────┬───────┘                              └──────────┬─────────┘
                          │                                                 │
                          ▼                                                 │
                 ┌────────────────────┐                                     │
                 │  AIProcessingLayer │                                     │
                 │  - text: qwen2.5   │                                     │
                 │  - image: llava    │                                     │
                 │  - voice: whisper  │                                     │
                 └────────┬───────────┘                                     │
                          │                                                 │
                          ▼                                                 │
                 ┌────────────────────┐                                     │
                 │  ExtractionParser  │  ◀── regex fallback                 │
                 │  + validator       │  ◀── category normalizer            │
                 └────────┬───────────┘                                     │
                          │                                                 │
              confidence  │  OK                                             │
           ◀──────────────┤                                                 │
           │              │                                                 │
           ▼              ▼                                                 ▼
  ┌────────────────┐  ┌────────────────┐                         ┌────────────────────┐
  │ PendingStore   │  │ SheetsService  │◀────────────────────────│ StateService       │
  │ (in-mem FSM)   │  │ - duplicate    │                         │ (last_txn per user)│
  │ - confirm flow │  │ - retry×3      │                         └────────────────────┘
  └────────────────┘  └────────────────┘
                             │
                             ▼
                     ┌────────────────┐
                     │ Google Sheets  │
                     │   (gspread)    │
                     └────────────────┘

All layers emit to → Logger (rotating file) + Prometheus counters
```

### Data flow (text message, happy path, step-by-step)
1. User sends `"makan siang 50rb"` to bot.
2. aiogram receives update → `AuthMiddleware` checks `message.from_user.id` against whitelist; unknown users = silent drop.
3. `MessageRouter` classifies content_type = `text` → dispatches to `text_handler`.
4. `text_handler` calls `ai.extract_text(message.text, user)` → POSTs to `http://ollama:11434/api/chat` with schema-constrained prompt.
5. Ollama returns JSON `{nominal, tipe, kategori, keterangan, confidence}`.
6. `ExtractionParser` validates schema, normalizes nominal (`"50rb" → 50000`), normalizes category against allowed list.
7. If `confidence < 0.8` → store as pending in `PendingStore` (in-memory dict keyed by `(user_id, message_id)`) and reply with inline keyboard: `[✅ Ya] [❌ Tidak] [✏️ Ubah kategori]`.
8. If confident → call `sheets.append(row)`:
   - Duplicate check: query last 5 rows, match `user + nominal + timestamp within 60s` → if match, ask "duplikat, tetap simpan?".
   - Append with retry (3×, exp backoff 1s/2s/4s).
   - Save `(user_id → row_id)` in `StateService` for `/ubah`.
9. Reply: `"✅ Tercatat: Pengeluaran Rp50.000 – Makanan"`.
10. Log: timestamp, user, raw_input, extracted_json, sheet_row_id, latency_ms.

### Async vs sync
- **Async (aiogram asyncio):** Telegram I/O, Ollama HTTP, Whisper stdout pipe (via `asyncio.create_subprocess_exec`), gspread calls wrapped in `loop.run_in_executor` (gspread is sync).
- **Sync-in-executor:** gspread (no async client worth adding for MVP). Single ThreadPoolExecutor(max_workers=2) — one family, low volume; no contention.
- **No background workers / Celery / Redis queue** for MVP. Overkill for 2–3 users.

---

## 3. Folder Structure

```
apps/keluarga mencatat/
├── PRD.md
├── README.md                          # setup, run, troubleshoot
├── Dockerfile                         # bot image (python + whisper.cpp)
├── docker-compose.override.yml        # merges into homeserver docker-compose.yml
├── .env.example
├── .env                               # gitignored — secrets
├── .gitignore
├── requirements.txt
├── pyproject.toml                     # optional, ruff/black config
│
├── app/
│   ├── __init__.py
│   ├── main.py                        # aiogram bootstrap, DI wiring
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                # pydantic-settings, loads .env
│   │   └── categories.py              # list of predefined categories
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── middleware/
│   │   │   ├── auth.py                # whitelist check
│   │   │   └── logging.py             # per-update logger
│   │   ├── handlers/
│   │   │   ├── start.py               # /start, /help
│   │   │   ├── text.py                # text messages → extraction
│   │   │   ├── photo.py               # Day 3: receipt OCR
│   │   │   ├── voice.py               # Day 3: voice → whisper → text path
│   │   │   ├── confirm.py             # callback_query for Ya/Tidak
│   │   │   ├── edit.py                # /ubah, /kategori
│   │   │   └── analytics.py           # Day 3: /minggu, /bulan, free-text query
│   │   └── keyboards.py               # inline keyboard builders
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── ollama_client.py           # httpx async client, /api/chat
│   │   ├── prompts.py                 # extraction prompt, categorization prompt
│   │   ├── text_extractor.py          # main entrypoint: text → TxnDraft
│   │   ├── image_extractor.py         # Day 3: photo → TxnDraft (llava)
│   │   ├── whisper_client.py          # Day 3: subprocess to whisper.cpp
│   │   └── regex_fallback.py          # backup nominal parser
│   │
│   ├── sheets/
│   │   ├── __init__.py
│   │   ├── client.py                  # gspread auth + lazy singleton
│   │   ├── service.py                 # append, get_last_n, update_row
│   │   ├── models.py                  # TxnRow dataclass
│   │   └── dedup.py                   # duplicate detector
│   │
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py                  # TxnDraft, TxnConfirmed, Category enum
│   │   ├── validator.py               # schema + business-rule validation
│   │   └── normalizer.py              # "50rb"→50000, category matching
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── pending_store.py           # in-mem: pending confirmations
│   │   └── last_txn_store.py          # in-mem: last txn per user (for /ubah)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                  # rotating file logger
│       ├── retry.py                   # exp-backoff decorator
│       ├── uuid_gen.py                # trx-YYYYMMDD-NNN
│       └── time.py                    # Asia/Jakarta helpers
│
├── scripts/
│   ├── download_whisper_model.sh      # pulls ggml-small.bin
│   ├── pull_ollama_models.sh          # ollama pull qwen2.5:7b llava:7b
│   └── init_sheet.py                  # creates header row if empty
│
└── tests/
    ├── test_normalizer.py             # "50rb", "1.5jt", etc.
    ├── test_validator.py
    ├── test_dedup.py
    └── test_regex_fallback.py
```

---

## 4. Detailed Task Breakdown (JIRA-style)

### DAY 1 — 8h target (Core path: text → Sheets)

**T1.1 — Provision all credentials [HIGH, 1h]**
- Create Telegram bot via @BotFather, copy token. 8655029536:AAEuf1023dhdwp-pNpuX1zuqmxeHdwSbB4g
- Create GCP project, enable Sheets API, create Service Account, download JSON key.
project-catatapps-4bc24e4c7ad6.json
- Create `Transaksi` Google Sheet, share with service account email (Editor).
- Collect each family member's Telegram ID (send `/start` to @userinfobot).
96948242, 2036995756
- **AC:** `.env` populated with `TELEGRAM_TOKEN`, `GOOGLE_CREDS_PATH`, `SHEET_ID`, `ALLOWED_USER_IDS=1234,5678`.


**T1.2 — Repo skeleton + dependencies [HIGH, 0.5h]**
- Create folder structure from §3.
- `requirements.txt`: `aiogram==3.13.*`, `httpx`, `gspread==6.*`, `google-auth`, `pydantic-settings`, `python-dotenv`, `tenacity`, `pytz`.
- Commit `.env.example` and `.gitignore`.
- **AC:** `pip install -r requirements.txt` succeeds in a clean venv.

**T1.3 — Config loader [HIGH, 0.5h]**
- `app/config/settings.py` with pydantic-settings loading `.env`.
- `app/config/categories.py`: `makanan, transport, belanja, tagihan, hiburan, kesehatan, pendidikan, gaji, lainnya`.
- **AC:** `from app.config.settings import settings; print(settings.telegram_token)` works.

**T1.4 — aiogram bootstrap + auth middleware [HIGH, 1h]**
- `app/main.py`: Dispatcher, register middleware, handlers, start polling.
- `app/bot/middleware/auth.py`: silently drop if `user.id not in settings.allowed_user_ids`.
- `/start` handler replies `"Halo <name>! Kirim pencatatan apa aja."`.
- **AC:** Whitelisted user gets reply on `/start`. Non-whitelisted user gets nothing (and log line `rejected user=X`).

**T1.5 — Sheets client + append [HIGH, 1.5h]**
- `app/sheets/client.py`: lazy `gspread.service_account_from_dict` singleton.
- `app/sheets/service.py`: `append(row: TxnRow)`, `get_last_n(user_id, n=5)`, `update_row(row_id, **fields)`.
- Wrap sync calls with `asyncio.to_thread`.
- Retry decorator (tenacity) with 3 attempts, exp backoff 1s/2s/4s.
- `scripts/init_sheet.py` writes header row if sheet empty.
- **AC:** `python -m scripts.init_sheet` creates header. Manual `append()` from REPL writes a row.

**T1.6 — Domain models + normalizer + validator [HIGH, 1h]**
- `TxnDraft` (pre-confirmation): nominal, tipe, kategori, keterangan, confidence, raw_input, source (text/photo/voice).
- `TxnRow` (sheet shape): id_transaksi, tanggal, tipe_transaksi, kategori, nominal, keterangan, pengguna.
- `normalizer.py`:
  - nominal: `"50rb"|"50 ribu"|"50k"→50000`, `"1.5jt"|"1,5 juta"→1500000`, plain digits.
  - category: case-insensitive match against allowed list; fuzzy nearest via simple ratio.
- `validator.py`: nominal>0, tipe∈{pemasukan,pengeluaran}, kategori∈allowed, date present.
- **AC:** `tests/test_normalizer.py` covers 10+ Indonesian shorthand variants; all pass.

**T1.7 — Ollama docker service + model pull [HIGH, 0.5h]**
- Add `ollama` service to `docker-compose.override.yml` with volume `./data/ollama:/root/.ollama`, port `11434`, network `app`.
- `scripts/pull_ollama_models.sh`: `docker exec ollama ollama pull qwen2.5:7b && docker exec ollama ollama pull llava:7b` (llava for Day 3).
- **AC:** `curl http://localhost:11434/api/tags` lists `qwen2.5:7b`.

**T1.8 — Text extractor (Ollama client + prompt) [HIGH, 1.5h]**
- `app/ai/ollama_client.py`: async httpx POST to `/api/chat`, `format: "json"`, `options: {num_predict: 128, temperature: 0.1}`.
- `app/ai/prompts.py`: system prompt in Indonesian, specifies exact JSON schema, includes category list, few-shot examples (3 examples).
- `app/ai/text_extractor.py`: `extract(raw: str, user: str) → TxnDraft`. Runs Ollama, parses JSON, falls back to `regex_fallback.py` if JSON invalid or nominal missing.
- `regex_fallback.py`: extracts nominal via regex, guesses tipe from keywords (`gaji|bonus`→pemasukan, else pengeluaran), category=`lainnya`, confidence=0.5.
- **AC:** Given `"makan 50rb"`, returns `{nominal:50000, tipe:"pengeluaran", kategori:"makanan", confidence:>=0.8}` in <8s.

**T1.9 — Text handler E2E wiring [HIGH, 0.5h]**
- `app/bot/handlers/text.py`: receive message → extract → validate → append to Sheets → reply with summary.
- **AC:** Sending `"beli bensin 100rb"` from Telegram results in a row in Google Sheets within 10s and a confirmation reply.

---

### DAY 2 — 8h target (Confirmation flow, dedup, edit, Docker)

**T2.1 — Inline keyboard confirmation flow [HIGH, 2h]**
- `app/bot/keyboards.py`: `confirm_kb()` with Ya/Tidak/Ubah kategori; `category_kb()` with all categories.
- `app/state/pending_store.py`: in-memory `dict[(user_id, msg_id) → TxnDraft]` with 5-min TTL (asyncio task or lazy expiry on read).
- `app/bot/handlers/confirm.py`: callback_query handlers for `confirm:yes`, `confirm:no`, `confirm:edit_cat`, `set_cat:<name>`.
- Trigger: if `draft.confidence < 0.8` OR `draft.source == "photo"`.
- **AC:** Low-confidence text triggers keyboard. Pressing Ya appends to Sheets. Pressing Ubah kategori shows category keyboard, selecting updates draft, then appends.

**T2.2 — Duplicate detection [HIGH, 1h]**
- `app/sheets/dedup.py`: `is_duplicate(draft, recent_rows)` → same user + same nominal + |timestamp diff| < 60s.
- On match: reply with inline keyboard `[Ya, tetap simpan] [Batal]`.
- **AC:** Sending `"kopi 20rb"` twice within 30s prompts duplicate confirmation on second send.

**T2.3 — Edit last transaction [HIGH, 1h]**
- `app/state/last_txn_store.py`: `dict[user_id → row_id]`, persisted also as `last_txn.json` on disk (survives restart).
- Command parser for `/ubah 120000`, `/kategori transport`, or free-form `"ubah terakhir jadi 120 ribu"`.
- `app/bot/handlers/edit.py`: calls `sheets.update_row(last_row_id, **fields)`.
- **AC:** After adding a txn, `/ubah 75000` updates its nominal field in the sheet.

**T2.4 — Logging + error UX [HIGH, 1h]**
- `app/utils/logger.py`: `RotatingFileHandler` at `./logs/bot.log`, 10MB × 5. JSON format.
- Wrap all handlers in try/except → log + reply with friendly Indonesian fallback message from §6.
- **AC:** Killing Ollama mid-request results in user seeing `"Sistem AI sedang sibuk, coba lagi ya"` and an error logged with traceback.

**T2.5 — Dockerfile [HIGH, 1h]**
- Base: `python:3.12-slim`. Install build tools, clone whisper.cpp, `make`, download `ggml-small.bin` in a separate layer (Day 3 bonus — safe to skip if voice is cut).
- COPY app, pip install, CMD `python -m app.main`.
- Healthcheck: HTTP probe on an internal `/health` endpoint (optional) OR log-based liveness.
- **AC:** `docker build .` succeeds. Image < 2GB.

**T2.6 — Docker Compose integration [HIGH, 1h]**
- `docker-compose.override.yml` in project dir, merges with home-server compose:
  - `keluarga-bot` service, depends_on `ollama`, networks: `app`.
  - `ollama` service (first time), volume to persist models.
- Env vars from `.env` in project dir, credential JSON mounted read-only.
- **AC:** From `/Volumes/MyHDD/homeserver/`, running `docker compose -f docker-compose.yml -f apps/keluarga\ mencatat/docker-compose.override.yml up -d keluarga-bot ollama` brings up both; bot responds in Telegram.

**T2.7 — Smoke test + README [HIGH, 1h]**
- Manual test matrix: 10 varied text inputs covering shorthand, Indonesian spellings, edge cases (decimals, no nominal, income keywords).
- `README.md`: setup (credentials), run (`docker compose up`), troubleshooting (model not pulled, Sheets 403, whitelist).
- **AC:** All 10 inputs produce correct rows OR correctly trigger confirmation/fallback.

---

### DAY 3 — buffer / stretch (8h)

**T3.1 — Receipt OCR via LLaVA [MEDIUM, 3h]**
- `app/bot/handlers/photo.py`: download photo from Telegram, send base64 to Ollama `/api/generate` with `llava:7b`.
- Prompt: "Extract total amount in IDR and merchant name from this receipt. Return JSON."
- Pipe result into same `TxnDraft` → confirm flow (always force confirmation on photos, regardless of confidence).
- **AC:** Sending a receipt photo replies with proposed txn within 15s and asks for confirmation.

**T3.2 — Voice input via Whisper.cpp [MEDIUM, 3h]**
- In Dockerfile: clone `ggerganov/whisper.cpp`, `make`, download `ggml-small.bin` (multilingual, ~500MB).
- `app/ai/whisper_client.py`: download Telegram voice `.ogg`, `ffmpeg` to 16kHz wav, subprocess `./main -m models/ggml-small.bin -l id -f <wav>`, parse stdout.
- `app/bot/handlers/voice.py`: voice → transcript → pipe through `text_extractor` → normal flow.
- **AC:** Sending "makan siang lima puluh ribu" voice note produces a txn draft.

**T3.3 — Chat analytics [MEDIUM, 1.5h]**
- `app/bot/handlers/analytics.py`: commands `/minggu`, `/bulan`, `/kategori makanan`.
- Fetches all rows via gspread, filters in-memory (data is small), returns formatted Indonesian text summary.
- **AC:** `/minggu` returns total + per-category breakdown for current ISO week.

**T3.4 — Polish + daily CSV backup [LOW, 0.5h]**
- Host cron: `0 2 * * * docker exec keluarga-bot python -m scripts.backup_csv` → writes `./backups/transaksi_YYYYMMDD.csv`.
- **AC:** Manually running script produces a CSV matching sheet contents.

---

## 5. API & Data Contract

### Telegram message parsing (input)
Handler dispatch is by `message.content_type`:
- `text` → `text_handler`
- `photo` → `photo_handler` (takes largest size)
- `voice` → `voice_handler`
- Everything else → ignored with reply `"Kirim teks, foto struk, atau voice note ya"`.

Commands (prefix `/`): `start`, `help`, `ubah`, `kategori`, `minggu`, `bulan`.
Free-form edits detected via regex on text: `^ubah terakhir\b`, `^kategori tadi\b`.

### AI output JSON schema (strict, enforced with Ollama `format: "json"`)
```json
{
  "nominal": 50000,
  "tipe_transaksi": "pengeluaran",
  "kategori": "makanan",
  "keterangan": "makan siang",
  "confidence": 0.92
}
```
- `nominal`: positive integer, IDR whole rupiah (no decimals, no "Rp").
- `tipe_transaksi`: enum `"pemasukan" | "pengeluaran"`.
- `kategori`: must be one of the predefined list; fallback `"lainnya"`.
- `keterangan`: string, may be empty.
- `confidence`: float 0.0–1.0. Threshold: `<0.8` → user confirmation; `<0.5` → regex fallback also runs and results compared.

### Google Sheets row mapping
| Column | Sheet header | Source |
|---|---|---|
| A | id_transaksi | `trx-{YYYYMMDD}-{3-digit counter or short uuid}` |
| B | tanggal | `datetime.now(tz=Asia/Jakarta).isoformat()` |
| C | tipe_transaksi | from AI |
| D | kategori | from AI (normalized) |
| E | nominal | integer from AI |
| F | keterangan | from AI, fallback to raw input |
| G | pengguna | `@{telegram_username}` or `id:{user_id}` if no username |

### Validation rules
- `nominal > 0` and `< 1_000_000_000` (Rp 1 miliar — guard against hallucinations).
- `tipe_transaksi ∈ {pemasukan, pengeluaran}`.
- `kategori ∈ allowed_categories`; unknown → coerce to `lainnya`.
- `pengguna` must match whitelisted ID (enforced at middleware).
- Empty `keterangan` is allowed; all other fields required.
- Duplicate rule: (same user) ∧ (same nominal) ∧ (|Δt| < 60s) → prompt user.

---

## 6. Error Handling Strategy

| Scenario | Detection | Retry | Fallback UX (Indonesian) |
|---|---|---|---|
| **Ollama timeout / 5xx** | httpx timeout 20s, status != 200 | 1 retry with temperature=0 | After retry fail: try regex_fallback; if that also fails → `"Sistem AI sedang sibuk, coba ketik lagi ya"` |
| **AI returns invalid JSON** | `json.JSONDecodeError` or schema mismatch | None (wasteful) | Run regex_fallback; if nominal found → show confirmation keyboard; else → `"Belum kebaca, coba format: 'makan 50rb' ya"` |
| **AI low confidence (<0.8)** | `draft.confidence < 0.8` | N/A | `"Benar Rp50.000 kategori Makanan?"` + inline keyboard |
| **OCR fail (LLaVA)** | No nominal extracted or confidence < 0.5 | None | `"Saya kurang yakin baca struknya, boleh ketik nominalnya?"` + set pending state awaiting text |
| **Voice unclear (Whisper)** | empty transcript or confidence from whisper < threshold | None | `"Audio kurang jelas, bisa ulangi atau ketik saja?"` |
| **Sheets append fail (API 5xx / network)** | gspread APIError | 3× exp backoff (1s/2s/4s) via tenacity | After 3 fails: reply `"Gagal simpan ke Sheets, dicoba ulang otomatis"`; enqueue in local `failed_writes.jsonl`; background task retries every 60s |
| **Sheets auth fail (403)** | gspread APIError status 403 | No retry (won't help) | `"Masalah izin Sheets, cek service account"`; admin alert log WARN |
| **Duplicate detected** | dedup check matches | N/A | `"Transaksi ini sepertinya duplikat, tetap simpan?"` + Ya/Batal |
| **Unknown user** | `user.id not in whitelist` | N/A | Silent drop; log INFO |
| **Bot crash / server offline** | process dies | Docker `restart: unless-stopped` | Telegram buffers messages; on restart they arrive as `getUpdates` backlog and are handled |
| **Rate limit (Telegram 429)** | aiogram TelegramRetryAfter | Sleep for `retry_after`, then retry once | Log WARN |

### Retry logic specifics
- **Sheets writes:** `tenacity.retry(stop=stop_after_attempt(3), wait=wait_exponential(1, max=4))`.
- **Ollama calls:** 1 retry max (latency budget tight). On second fail → regex fallback.
- **Dead-letter queue:** `./data/failed_writes.jsonl` — one line per failed `TxnRow`. Background `asyncio.create_task` retries every 60s; moves to `./data/processed_writes.jsonl` on success. Size capped at 1000 entries.

---

## 7. State Management Strategy

### Where state lives
| State | Store | Persistence | Why |
|---|---|---|---|
| Pending confirmations | In-memory `dict[(user_id, msg_id) → TxnDraft]` | Ephemeral (5-min TTL) | Low volume, restart losing these is fine |
| Last transaction per user (for `/ubah`) | In-memory + `./data/last_txn.json` snapshot | Persisted on write | Must survive container restart |
| Dead-letter queue | `./data/failed_writes.jsonl` | Disk | Survive restart, don't lose data |
| Whitelist | `.env` | Config | Loaded at boot |

### Confirmation flow (state machine)
```
[NEW]  user sends input
  │
  ▼
extract → TxnDraft
  │
  ├─ confidence >= 0.8 AND source==text ──▶ [AUTO_APPEND] ──▶ sheet + reply summary
  │
  └─ else ──▶ [PENDING]
                │  (key: (user_id, msg_id), TTL 5m)
                │  bot shows inline keyboard
                │
                ├─ [confirm:yes]  ──▶ [AUTO_APPEND]
                ├─ [confirm:no]   ──▶ [CANCELLED] drop, reply "ok batal"
                └─ [confirm:edit_cat] ──▶ [AWAITING_CATEGORY]
                                            │
                                            └─ [set_cat:X] ──▶ [AUTO_APPEND]
```

- `PendingStore`: dict keyed by `(user_id, bot_message_id)`; the bot message is the one with the keyboard, so callback queries carry this key.
- TTL: on every read, purge entries older than 5 min.
- No FSM library needed for MVP — aiogram's FSMContext is overkill for this one-step flow; plain dict suffices.

### Correction flow
- `/ubah 120000` → parse → `sheets.update_row(last_txn_store[user_id], nominal=120000)` → reply "diubah".
- `/kategori transport` → same pattern, updates kategori.
- Free-form `"ubah terakhir jadi 150 ribu"` → regex extracts nominal → same update.
- If no last txn for user → reply `"Belum ada transaksi terakhir"`.

---

## 8. Security Implementation Plan

### Telegram whitelist
- `ALLOWED_USER_IDS=12345,67890,24680` in `.env` (comma-separated ints).
- `AuthMiddleware` parses once at boot into `set[int]`.
- Unknown user → `return` (no reply, no error shown to them). Log at INFO with `user_id` and first 50 chars of message.
- Optional: rate-limit per user to 30 msgs/min (aiogram `ThrottlingMiddleware` — skip for MVP, family scope is trusted).

### Credential storage
- `.env` at project root, mode `600`, git-ignored.
- Google Service Account JSON at `./secrets/google_creds.json`, mode `600`, git-ignored, mounted read-only into container.
- Dockerfile never COPIes `.env` or `secrets/`.
- `pydantic-settings` loads `.env` → validates required fields or crashes early.
- No hardcoded tokens anywhere; CI grep check: `grep -rE '(AIza|ghp_|xoxb|[0-9]{10}:[A-Za-z0-9_-]{35})' app/` in pre-commit (Day 3 polish).

### Logging policy
- **DO log:** user_id (not username), content_type, raw input (to debug extraction), extracted JSON, sheet row_id, latency, errors + full traceback.
- **DO NOT log:** Telegram token, Google creds (no path, no JSON body), full credential file contents, any env vars on startup (log sanitized keys only).
- Log destination: `./logs/bot.log` (rotating, 10MB × 5 files). Not shipped offsite.
- Log format: JSON lines for machine-parsing + grafana-loki later if wanted.

---

## 9. DevOps & Deployment Plan

### Integration with existing home-server stack
- **Do not edit** `/Volumes/MyHDD/homeserver/docker-compose.yml` — add a `docker-compose.override.yml` at `apps/keluarga mencatat/` that will be merged via `-f` flag or placed at root as a secondary compose.
- Add two services:
  - `keluarga-bot` (built from local Dockerfile, network `app`, depends on `ollama`).
  - `ollama` (image `ollama/ollama:latest`, volume `./data/ollama`, port `11434:11434`, network `app`, restart `unless-stopped`).
- No Traefik routing needed (bot polls Telegram, no inbound HTTP).
- Whisper model downloaded during image build (Day 3).

### `docker-compose.override.yml` sketch (target file content)
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports: ["11434:11434"]
    volumes:
      - ./data/ollama:/root/.ollama
    networks: [app]
    restart: unless-stopped

  keluarga-bot:
    build:
      context: ./apps/keluarga mencatat
    container_name: keluarga-bot
    env_file: ./apps/keluarga mencatat/.env
    volumes:
      - ./apps/keluarga mencatat/secrets:/app/secrets:ro
      - ./apps/keluarga mencatat/data:/app/data
      - ./apps/keluarga mencatat/logs:/app/logs
    networks: [app]
    depends_on: [ollama]
    restart: unless-stopped
```

### Startup flow
1. `docker compose up -d ollama` — starts Ollama, first run downloads nothing (fast).
2. `./apps/keluarga\ mencatat/scripts/pull_ollama_models.sh` — pulls `qwen2.5:7b` and `llava:7b` (one-time, ~8GB total; takes 5–15 min).
3. `docker compose up -d --build keluarga-bot` — builds and runs the bot.
4. Bot logs `"Bot started, polling..."` → test with `/start` from a whitelisted Telegram account.

### Environment variables (`.env.example`)
```
TELEGRAM_TOKEN=
GOOGLE_CREDS_PATH=/app/secrets/google_creds.json
SHEET_ID=
SHEET_TAB_NAME=Transaksi
ALLOWED_USER_IDS=
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_TEXT_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=llava:7b
LOG_LEVEL=INFO
TZ=Asia/Jakarta
CONFIDENCE_THRESHOLD=0.8
```

---

## 10. Risks & Mitigation (Technical, critical view)

| Risk | Likelihood | Impact | Mitigation / simplification |
|---|---|---|---|
| **qwen2.5:7b too slow on CPU (>15s)** | HIGH | Blows 10s SLA, bad UX | Keep prompt under 300 tokens, `num_predict: 128`, `temperature: 0.1`. Warm-start with a throwaway request on boot. If still slow → downgrade to `qwen2.5:3b` (faster, slightly less accurate). If unacceptable → **regex-only path for text** (covered by fallback), reserve LLM only for ambiguous inputs. |
| **LLM returns malformed JSON despite `format:json`** | MEDIUM | Parse crashes | Wrap in try/except, fall through to regex_fallback. Don't retry LLM — burns time. |
| **Whisper.cpp Docker build fails** | MEDIUM | Voice broken | Voice is Day 3 stretch. If build fails in 30 min, cut voice entirely, document as Phase 2. |
| **LLaVA receipt OCR accuracy <50% on real Indonesian struk** | HIGH | Feature unusable | Always force manual confirmation on photos; if confirmation rate is terrible in testing, mark as "experimental" and leave it. |
| **Google Sheets API quota hit** | LOW | Writes fail | 60 writes/min/user; family scope won't hit this. Retries + DLQ handle transient. |
| **Ollama container OOM** | MEDIUM | Crashes | Set `mem_limit: 10g` on ollama service; monitor with existing Prometheus stack. |
| **Telegram polling disconnects** | LOW | Messages missed | aiogram handles reconnect; Telegram retains updates for 24h via `getUpdates`. |
| **Family member sends something weird that crashes handler** | MEDIUM | Bot dies | Global exception handler in aiogram middleware logs and replies generic fallback; container `restart: unless-stopped`. |
| **Solo dev gets stuck on credential setup (Sheets API)** | HIGH | Day 1 burns | T1.1 is literally first task; if stuck >1h, skip to local SQLite stub for sheet + swap later (fail-safe — but only if really blocked). |
| **Duplicate detection false positives** | LOW | User annoyance | Only prompt (never block); user can always say Ya. |

### "What will likely fail in 3 days?"
1. **Voice transcription quality for Indonesian** — `ggml-small` is OK, not great; expect 80–90% not 92%. Accept and move on.
2. **Receipt OCR on non-standard receipts** — handwritten, small shops, low light will fail. Force manual confirm.
3. **10s end-to-end on cold start** — first LLM request after idle can be 20s+. Warm-start mitigates but doesn't fully solve.

---

## 11. Suggested Simplifications

These are ranked by how much time they save vs how much they degrade MVP value. Adopt top-down as needed.

1. **Cut voice from MVP entirely** (saves ~3h + build risk). Users can already talk-to-text via their phone keyboard → sends text. Communicate: "voice coming in v2".
2. **Cut LLaVA receipt OCR from MVP** (saves ~3h + accuracy frustration). Replace with `/foto` command that saves the image to disk with a Telegram link for later manual entry. Ships on Day 3 if any time left.
3. **Replace chat analytics with fixed commands** (saves ~1h). `/minggu` and `/bulan` only, no free-text queries. Natural-language analytics is Phase 2.
4. **Drop Ollama for text, use regex-only + keyword table** (saves ~2h, big speed win). Most inputs follow predictable patterns like `"X Y ribu"`. Only invoke LLM when regex yields nothing. Benchmark: if regex covers ≥80% of your family's inputs in testing, prefer this. The LLM then becomes a fallback, not the default.
5. **Skip Docker for Day 1–2, run with `python -m app.main` locally** (saves ~1h). Dockerize on Day 3 after it works. Lower risk of wasting time on image build quirks.
6. **No dead-letter queue — just log and alert user** (saves ~1h). For a family with 2–3 users, a Sheets outage that lasts > retry budget is rare; user can re-send.
7. **No FSM / callback data versioning** — encode callbacks as plain strings (`confirm:yes`, `set_cat:makanan`). aiogram CallbackData helper is clean but adds a small learning curve.
8. **Single-sheet append, no monthly rolling sheets** — all history in one tab. If it gets huge later, migrate; irrelevant for MVP volume.

### Recommended "safe MVP" cut-down for a nervous solo dev
Day 1: Credentials → skeleton → Sheets append → whitelist → text handler with **regex-first, LLM-fallback** → ship locally (no Docker).
Day 2: Confirmation keyboard → dedup → `/ubah` → Dockerize → README.
Day 3: Pick ONE of: voice, photo, analytics. Do it well. Leave the others for Phase 2.

---

## Critical files to create (quick index)

| Purpose | Path |
|---|---|
| Entry point | `app/main.py` |
| Config | `app/config/settings.py`, `app/config/categories.py` |
| Auth | `app/bot/middleware/auth.py` |
| Text handler (core) | `app/bot/handlers/text.py` |
| Confirmation | `app/bot/handlers/confirm.py`, `app/bot/keyboards.py` |
| Edit | `app/bot/handlers/edit.py` |
| LLM | `app/ai/ollama_client.py`, `app/ai/prompts.py`, `app/ai/text_extractor.py` |
| Regex fallback | `app/ai/regex_fallback.py` |
| Sheets | `app/sheets/service.py`, `app/sheets/dedup.py` |
| Domain | `app/domain/normalizer.py`, `app/domain/validator.py`, `app/domain/models.py` |
| State | `app/state/pending_store.py`, `app/state/last_txn_store.py` |
| Tests | `tests/test_normalizer.py` (the one that matters most) |
| Deploy | `Dockerfile`, `docker-compose.override.yml`, `.env.example` |
| Init | `scripts/init_sheet.py`, `scripts/pull_ollama_models.sh` |

---

## Verification (end-to-end test plan)

After Day 2:
1. `docker compose up -d ollama keluarga-bot`
2. Check logs: `docker logs keluarga-bot | grep "polling"`
3. From whitelisted account, send `/start` → expect reply.
4. From non-whitelisted account, send `/start` → expect no reply; check logs show `rejected`.
5. Send `"makan siang 50rb"` → within 10s, row appears in Sheet, reply summary correct.
6. Send same message again within 30s → duplicate prompt appears.
7. Send `"bayar listrik"` (no nominal) → confidence-low prompt OR fallback "format contoh".
8. Send `/ubah 75000` → last row's nominal becomes 75000 in Sheet.
9. Send gibberish `"asdfasdf"` → polite fallback reply, no crash, log has error context.
10. Stop Ollama: `docker stop ollama`. Send text → bot replies `"AI sedang sibuk"`. Restart Ollama → next message works.

After Day 3 (stretch verifications):
- Receipt photo → OCR prompt → confirm → row appears.
- Voice note "makan 50 ribu" → transcript → extraction → confirm → row appears.
- `/minggu` → totals reply correct.
- Daily cron backup file appears in `./backups/`.
