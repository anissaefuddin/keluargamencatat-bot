# Keluarga Mencatat — Telegram AI Finance Bot

A private Telegram bot for 2–3 person families: send `"makan 50rb"` → it extracts, categorizes, and appends to Google Sheets. All AI runs locally (Ollama).

## Quick start (local dev, no Docker)

```bash
# 1. Put creds in place
cp .env.example .env
# edit .env with TELEGRAM_TOKEN, SHEET_ID, ALLOWED_USER_IDS, GOOGLE_CREDS_PATH

# 2. Put the Google service-account JSON at ./secrets/google_creds.json
#    and share your sheet with the service account email (Editor)

# 3. Install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Init sheet header
python -m scripts.init_sheet

# 5. Start Ollama (host) and pull models
# in another terminal:
ollama serve
ollama pull qwen2.5:7b

# 6. Run the bot
python -m app.main
```

## Run via Docker (home-server)

From `/Volumes/MyHDD/homeserver`:

```bash
docker compose \
  -f docker-compose.yml \
  -f "apps/keluarga mencatat/docker-compose.override.yml" \
  up -d ollama keluarga-bot

# one-time: pull the models
./apps/keluarga\ mencatat/scripts/pull_ollama_models.sh

docker logs -f keluarga-bot
```

## Project layout

```
app/
  config/     pydantic-settings + category list
  bot/        aiogram handlers + middleware + keyboards
  ai/         Ollama client, prompts, regex fallback
  sheets/     gspread client, service, dedup
  domain/     TxnDraft/TxnRow, normalizer, validator
  state/      pending confirmations + last txn per user
  utils/      logger, time, uuid
scripts/    init_sheet, pull ollama models
tests/      normalizer + validator unit tests
```

## Commands

- `/start`, `/help`
- `/ubah 75000` — change nominal of last transaction
- `/kategori transport` — change category of last transaction

## Troubleshooting

**403 from Sheets** — share the sheet with the service-account email (from `secrets/google_creds.json` → `client_email`) as Editor, and enable Sheets API in GCP console.

**Bot doesn't reply** — check `ALLOWED_USER_IDS` includes your Telegram user id (get it from @userinfobot).

**Ollama timeouts** — first request loads the model into RAM (10–30s). Warm-up happens at boot; check logs for `ollama.warm_up_ok`.

**Empty `.env` fails to start** — pydantic-settings requires `TELEGRAM_TOKEN` and `SHEET_ID` at minimum.

## Day 3 stretch features (not yet implemented)

- Receipt OCR via LLaVA (`app/bot/handlers/photo.py` — stub)
- Voice transcription via Whisper.cpp (`app/ai/whisper_client.py` — stub)
- Chat analytics (`/minggu`, `/bulan`)
- Daily CSV backup cron
