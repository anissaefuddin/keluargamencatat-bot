# Keluarga Mencatat — Telegram AI Finance Bot

Private Telegram bot for a 2–3 person family. Send text, voice, or receipt photos → extracted and logged to Google Sheets. All AI runs locally (Ollama + faster-whisper).

## Features

- **💬 Text**: `makan siang 50rb` → extracts nominal + auto-categorizes
- **🎤 Voice notes**: bahasa Indonesia transcription via faster-whisper → same pipeline
- **🧾 Receipt photo**: LLaVA reads total + merchant → always asks confirmation
- **📊 Analytics**: `/minggu`, `/bulan`, `/laporan <kategori>`
- **✏️ Corrections**: `/ubah 75000`, `/kategori transport`
- **🔁 Duplicate detection**: same user + same amount within 60s → prompts
- **📂 Daily CSV backup**: fires at 02:00 Asia/Jakarta to `backups/transaksi_YYYYMMDD.csv`
- **🔐 Whitelist auth**: only pre-approved Telegram IDs get a response

## Quick start (local, currently-running mode)

```bash
cd "/Volumes/MyHDD/homeserver/apps/keluarga mencatat"
source .venv/bin/activate

# one-time setup
python -m scripts.init_sheet        # creates sheet header

# run bot (writes to logs/bot.stdout)
python -u -m app.main > logs/bot.stdout 2>&1 &
```

## Ollama setup

The `ollama` Docker container must be running on `homeserver_app` network on port 11434:

```bash
cd /Volumes/MyHDD/homeserver
docker compose \
  -f docker-compose.yml \
  -f "apps/keluarga mencatat/docker-compose.override.yml" \
  up -d ollama

# one-time model pulls (models persist in ./data/ollama)
docker exec ollama ollama pull qwen2.5:3b     # ~1.9GB — text extraction
docker exec ollama ollama pull llava:7b        # ~4.7GB — receipt OCR
```

## Dockerized bot deployment

The bot currently runs natively. To switch to Docker:

```bash
# build
docker build -t keluarga-bot:latest "/Volumes/MyHDD/homeserver/apps/keluarga mencatat"

# run via compose (merges with homeserver compose)
cd /Volumes/MyHDD/homeserver
docker compose \
  -f docker-compose.yml \
  -f "apps/keluarga mencatat/docker-compose.override.yml" \
  up -d keluarga-bot
```

Note: the Dockerized bot reaches Ollama via `http://ollama:11434` (set in the compose override). When running natively, it uses `http://localhost:11434` (from `.env`).

## Project layout

```
app/
  config/       settings + category list
  bot/          aiogram handlers + middleware + keyboards
    handlers/   start, text, confirm, edit, analytics, photo, voice
  ai/           ollama_client, prompts, text_extractor (+cross-check),
                regex_fallback, image_extractor (LLaVA), whisper_client
  sheets/       gspread client, service, dedup, analytics
  domain/       models, normalizer ("50rb"→50000), validator
  state/        pending confirmations + last txn per user
  utils/        logger, time, uuid, scheduler
scripts/      init_sheet, backup_csv, pull_ollama_models.sh
tests/        normalizer, validator, extractor cross-check  (35 tests)
```

## Commands

| Command | What it does |
|---|---|
| `/start`, `/help` | Greeting + usage |
| `/minggu` | Total + per-kategori breakdown for current week |
| `/bulan` | Same for current month |
| `/laporan makanan` | Last 30 days detail for a category |
| `/ubah 75000` | Change nominal of last transaction |
| `/kategori transport` | Change category of last transaction |

## Performance notes (tested on this homeserver)

- **Text**: 3–5s hot, 15–20s cold (model reload)
- **Voice**: 25s (includes Whisper decode + LLM); subsequent 3–5s
- **Photo OCR**: 60–120s first time (LLaVA cold load); 5–15s subsequent
- **Docker image**: 850MB

## Memory trade-off

Ollama container has 7.6GB limit; qwen2.5:3b (~2GB) + llava:7b (~5GB) together are tight. Models use `keep_alive: 30m` so they stay resident for the session, but if both are used close together, one may evict the other on re-entry. Next request after eviction takes 15-60s to reload. For faster switching, raise the Ollama container memory or pin a smaller vision model.

## Troubleshooting

**403 from Sheets** — share the sheet with the service-account email (`keluargamencatat@project-catatapps.iam.gserviceaccount.com`) as **Editor**, and make sure Sheets API is enabled in the GCP console.

**Analytics shows Rp0** — the sheet has currency formatting on column E; this is handled via `UNFORMATTED_VALUE` reads. If you see it return, verify your gspread version is 6.x.

**Bot silent** — check `ALLOWED_USER_IDS` includes your Telegram user ID (get yours from @userinfobot). The middleware drops unknowns silently.

**Ollama timeouts** — first photo OCR can take 2 minutes for LLaVA to load. The bot acknowledges "Lagi baca struknya..." immediately so you know it's working.

**Conflict: terminated by other getUpdates** — another bot instance is polling. Kill with `pkill -f "Python.*app.main"` then relaunch.

## Environment

Required `.env` keys:
- `TELEGRAM_TOKEN` — from @BotFather
- `SHEET_ID` — from the Google Sheet URL
- `ALLOWED_USER_IDS` — comma-separated Telegram user IDs
- `GOOGLE_CREDS_PATH` — path to service-account JSON (default `./secrets/google_creds.json`)
- `OLLAMA_BASE_URL` — `http://localhost:11434` native, `http://ollama:11434` in Docker
- `OLLAMA_TEXT_MODEL` — default `qwen2.5:3b`
- `OLLAMA_VISION_MODEL` — default `llava:7b`
- `CONFIDENCE_THRESHOLD` — default `0.8` (below → ask user to confirm)
