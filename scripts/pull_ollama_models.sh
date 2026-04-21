#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${OLLAMA_CONTAINER:-ollama}"

echo "Pulling qwen2.5:7b (text extraction model, ~4.7GB)..."
docker exec "$CONTAINER" ollama pull qwen2.5:7b

echo "Pulling llava:7b (vision model for receipts, ~4.7GB)..."
docker exec "$CONTAINER" ollama pull llava:7b

echo "Done. Verify with: curl -s http://localhost:11434/api/tags | jq ."
