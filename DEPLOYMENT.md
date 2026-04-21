# Deployment Guide — Keluarga Mencatat

End-to-end steps to deploy the Telegram AI finance bot on your home server (`/Volumes/MyHDD/homeserver`).

The stack:
- **keluarga-bot** (aiogram 3, Python 3.12) — text/voice/photo handler, runs in Docker
- **ollama** (Docker container) — local LLM: `qwen2.5:3b` (text) + `llava:7b` (vision)
- **Google Sheets** — database (via `gspread` + service account)
- **faster-whisper** (inside the bot image) — voice transcription, model auto-downloaded on first use

---

## 0. Prerequisites

You need these BEFORE deploying. Check each one:

| Item | How to verify |
|---|---|
| Docker running | `docker info` succeeds |
| Home-server compose stack exists | `/Volumes/MyHDD/homeserver/docker-compose.yml` present, `app` network exists |
| Git / clone of this repo at `apps/keluarga mencatat/` | `ls "/Volumes/MyHDD/homeserver/apps/keluarga mencatat/app/main.py"` succeeds |
| Telegram bot token | Created via [@BotFather](https://t.me/BotFather) |
| Google Cloud Service Account JSON | Downloaded from GCP console, Sheets API enabled |
| Google Sheet shared with the service-account email as **Editor** | Check the Sheet's Share dialog |
| Each family member's Telegram user ID | Each person sends `/start` to [@userinfobot](https://t.me/userinfobot) and copies the ID |
| Disk ≥ 10 GB free | Ollama models (~7 GB) + Whisper (~500 MB) + image (~850 MB) |
| RAM ≥ 8 GB available to Docker | qwen (~2 GB) + llava (~5 GB) hot + bot runtime |

---

## 1. First-time setup (one-time, ~20 min of clicking + 10 min of pulling)

### 1.1 Place secrets

```bash
cd "/Volumes/MyHDD/homeserver/apps/keluarga mencatat"

# Google service-account JSON — must be at this exact path:
#   ./secrets/google_creds.json  (mode 600)
mkdir -p secrets
chmod 700 secrets
cp /path/to/your-service-account.json secrets/google_creds.json
chmod 600 secrets/google_creds.json
```

### 1.2 Create `.env`

```bash
cp .env.example .env
# then edit .env:
#   TELEGRAM_TOKEN=<from BotFather>
#   SHEET_ID=<from Google Sheets URL>
#   ALLOWED_USER_IDS=12345678,87654321   (comma-separated Telegram user IDs)
#   OLLAMA_BASE_URL=http://ollama:11434  (for Docker deployment)
```

All other keys in `.env.example` have sensible defaults.

### 1.3 Start Ollama + pull models

```bash
cd /Volumes/MyHDD/homeserver

docker compose \
  -f docker-compose.yml \
  -f "apps/keluarga mencatat/docker-compose.override.yml" \
  up -d ollama

# pull models (one-time, ~7 GB total, 10-20 min)
docker exec ollama ollama pull qwen2.5:3b
docker exec ollama ollama pull llava:7b

# verify
docker exec ollama ollama list
# should show both models
```

Models persist in `./data/ollama/` on the host and survive container restarts.

### 1.4 Initialize the Google Sheet header

Do this once, from the host (not in Docker yet):

```bash
cd "/Volumes/MyHDD/homeserver/apps/keluarga mencatat"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.init_sheet
# expected: "OK: sheet header ensured"
```

If this errors with **403**, the service account doesn't have access to the sheet — go back to prereqs.

### 1.5 Build and run the bot container

```bash
cd /Volumes/MyHDD/homeserver

docker compose \
  -f docker-compose.yml \
  -f "apps/keluarga mencatat/docker-compose.override.yml" \
  up -d --build keluarga-bot

docker logs -f keluarga-bot
# expected lines within ~10 seconds:
#   INFO main Bot started, polling...
#   INFO aiogram.dispatcher Run polling for bot @<yourbot>
```

### 1.6 Smoke test

From a whitelisted Telegram account, send `/start` to your bot. You should get a greeting within 3-5 seconds.

Then send `makan 50rb` — the row should land in the sheet within 10 seconds.

---

## 2. Everyday commands

All commands assume CWD is `/Volumes/MyHDD/homeserver`.

Define a shell alias to save typing:

```bash
alias kmcompose='docker compose -f docker-compose.yml -f "apps/keluarga mencatat/docker-compose.override.yml"'
```

| Action | Command |
|---|---|
| Start bot + Ollama | `kmcompose up -d ollama keluarga-bot` |
| Stop bot only | `kmcompose stop keluarga-bot` |
| Stop everything | `kmcompose stop keluarga-bot ollama` |
| Restart bot (after code change) | `kmcompose up -d --build keluarga-bot` |
| View logs live | `docker logs -f keluarga-bot` |
| View last 100 log lines | `docker logs --tail 100 keluarga-bot` |
| Check Ollama model list | `docker exec ollama ollama list` |
| Manual CSV backup | `docker exec keluarga-bot python -m scripts.backup_csv` |
| Shell into the bot | `docker exec -it keluarga-bot bash` |

Daily CSV backup runs automatically at **02:00 Asia/Jakarta** via an in-bot scheduler — files land in `./backups/transaksi_YYYYMMDD.csv` on the host.

---

## 3. After a code change

```bash
cd /Volumes/MyHDD/homeserver
kmcompose up -d --build keluarga-bot
docker logs -f keluarga-bot    # watch for "Bot started, polling..."
```

If tests exist and you want to run them before building:

```bash
cd "/Volumes/MyHDD/homeserver/apps/keluarga mencatat"
source .venv/bin/activate
python -m pytest tests/ -q
```

---

## 4. Updating models

To swap `qwen2.5:3b` → `qwen2.5:7b` (higher quality, more RAM):

```bash
docker exec ollama ollama pull qwen2.5:7b
# edit .env:
#   OLLAMA_TEXT_MODEL=qwen2.5:7b
kmcompose up -d --build keluarga-bot
```

To reclaim disk by removing an unused model:

```bash
docker exec ollama ollama rm qwen2.5:3b
```

---

## 5. Monitoring

Existing Prometheus/Grafana on the home server already scrape cAdvisor, so CPU/memory for `keluarga-bot` and `ollama` containers are visible in Grafana's default dashboards.

For bot-specific events, tail the structured JSON log:

```bash
docker exec keluarga-bot tail -f /app/logs/bot.log
```

Interesting log keys:
- `ai.extract_ok` — LLM extraction succeeded
- `ai.extract_fallback` — LLM failed, regex fallback used
- `ai.nominal_mismatch` — LLM and regex disagreed (investigate if frequent)
- `sheets.append` — row written
- `auth.rejected` — non-whitelisted user tried to message (log-and-ignore)
- `ocr.no_total` — LLaVA couldn't read a receipt (fallback flow triggers if caption present)
- `scheduler.ran` — daily backup fired

---

## 6. Backup & restore

### Sheet is the source of truth
Google Sheets is durable; this bot is a stateless writer. Losing the container loses no data.

### Local artefacts worth backing up
| Path (relative to project dir) | What | Restore |
|---|---|---|
| `.env` | Secrets | Re-create from `.env.example` template + copy values from a password manager |
| `secrets/google_creds.json` | GCP service account | Re-download from GCP console |
| `data/last_txn.json` | Per-user last-row pointer (for `/ubah`) | Not critical; if lost, users just can't edit their most-recent txn |
| `backups/` | Daily CSV exports | Copy elsewhere if you want off-host backups |
| `data/ollama/` | Pulled model weights | Skippable; re-pull with `ollama pull` |

### Off-host backup recipe (optional)

Set up a cron on another machine (or via rsync to your NAS):

```cron
0 3 * * * rsync -az "user@homeserver:/Volumes/MyHDD/homeserver/apps/keluarga mencatat/backups/" /path/to/offsite/backups/
```

---

## 7. Managing the whitelist

Adding a new family member:

1. They message [@userinfobot](https://t.me/userinfobot), copy their user ID.
2. Edit `.env`: append the ID, comma-separated.
3. `kmcompose up -d keluarga-bot` to pick up the new env.

Removing someone:
- Remove their ID from `ALLOWED_USER_IDS`, restart.
- Their existing rows in the sheet are NOT deleted.

---

## 8. Migrating to a different machine

1. `tar czf keluarga.tar.gz "apps/keluarga mencatat/.env" "apps/keluarga mencatat/secrets/" "apps/keluarga mencatat/data/" "apps/keluarga mencatat/backups/"`
2. Copy `keluarga.tar.gz` + the project source tree to the new host.
3. Extract into `apps/keluarga mencatat/`.
4. Run section 1.3 (start Ollama + pull models) and 1.5 (build + run bot). The sheet and all history carry over automatically since they live in Google.

---

## 9. Troubleshooting

### `403 from Sheets`
Share the sheet with the service-account email as **Editor**. The email is in `secrets/google_creds.json` under `client_email`.

### `Bot doesn't reply to my messages`
- Verify your Telegram user ID is in `ALLOWED_USER_IDS`.
- Verify no typos in `TELEGRAM_TOKEN` — a bad token produces `TelegramUnauthorizedError`.
- Check logs: `docker logs --tail 50 keluarga-bot | grep auth.rejected`.

### `Conflict: terminated by other getUpdates request`
Another instance is polling the same bot token. Kill it:
```bash
kmcompose stop keluarga-bot
pgrep -fl "app.main"      # kill any native python processes that might still be running
kmcompose up -d keluarga-bot
```

### `Photo OCR always says "tidak menemukan total"`
LLaVA struggles with some Indonesian struk layouts (handwritten, crumpled, low light). The bot now handles this: add a caption like `"makan siang di warteg"` to your photo, and when OCR fails, the bot asks for just the nominal — you reply `"25rb"` and it's saved with the correct category from your caption.

### `Voice note takes 30 seconds first time`
Whisper downloads the `small` model (~500 MB) from Hugging Face on first use. Subsequent voice notes are 3-5 seconds.

### `Text messages take 20+ seconds after sending a photo`
Memory pressure: the 7.6 GB Ollama container can't keep both qwen and llava resident simultaneously. The `keep_alive: 30m` helps but eviction still happens. Options:
- Raise the Ollama memory limit in `docker-compose.override.yml` if host has more RAM.
- Use a smaller vision model (`llava-phi3:3.8b`, ~2.4 GB).
- Accept the trade-off — it's only the first request after a model swap.

### `Sheets timeouts / retries`
3× exponential-backoff retry already built in (1s/2s/4s). After 3 fails, the bot replies "akan dicoba ulang otomatis" and queues the row to `data/failed_writes.jsonl`. If you see persistent Sheets 5xx: this is Google's problem, usually transient. Check https://status.cloud.google.com/.

### `Daily backup didn't fire`
Check `docker logs keluarga-bot | grep scheduler`. The in-bot scheduler sleeps until 02:00 Asia/Jakarta — if the container was restarted right before 02:00 it may have missed that day. Manual fallback: `docker exec keluarga-bot python -m scripts.backup_csv`.

---

## 10. Uninstalling cleanly

```bash
cd /Volumes/MyHDD/homeserver

# stop and remove containers
kmcompose stop keluarga-bot ollama
kmcompose rm -f keluarga-bot ollama

# (optional) remove image
docker rmi keluarga-bot:latest

# (optional) remove model weights (~7 GB)
rm -rf ./data/ollama

# your Google Sheet is untouched — delete it manually if you want
```

Service account and bot token remain on Google/Telegram side; revoke via GCP IAM and BotFather respectively.

---

## Appendix: File layout on host

```
/Volumes/MyHDD/homeserver/
├── docker-compose.yml                        # existing home-server stack
├── apps/
│   └── keluarga mencatat/                    # this project
│       ├── app/                              # Python source
│       ├── scripts/                          # init_sheet, backup_csv, pull models
│       ├── tests/                            # 43 unit tests
│       ├── Dockerfile
│       ├── docker-compose.override.yml       # merged in via -f flag
│       ├── .env                              # secrets (gitignored)
│       ├── secrets/google_creds.json         # GCP (gitignored)
│       ├── data/                             # last_txn.json, ollama models
│       ├── logs/bot.log                      # rotating JSON log
│       └── backups/                          # daily CSV exports
```
