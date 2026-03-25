#!/bin/sh
set -e

BASE_URL="https://raw.githubusercontent.com/PhKP/email-sender/main"

echo "Downloading docker-compose.yml..."
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

if [ -f .env ]; then
  echo ".env already exists — skipping (not overwriting your config)."
else
  echo "Downloading .env.example as .env..."
  curl -fsSL "$BASE_URL/.env.example" -o .env
  echo ""
  echo "Next: edit .env and fill in your values, then run:"
  echo "  mkdir -p data && docker compose up -d"
fi
