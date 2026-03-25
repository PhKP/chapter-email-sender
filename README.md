# Chapter Email Sender

Sends one chapter per cron invocation from *97 Things Every Software Architect Should Know* to a configured email address. Keeps state between runs so it always picks up where it left off.

Chapters sourced from: <https://yoshi389111.github.io/kinokobooks/soft_en/index.html>

## Quick Start

### 1. Get the files

```bash
curl -fsSL https://raw.githubusercontent.com/PhKP/chapter-email-sender/main/setup.sh | sh
```

This downloads `docker-compose.yml` and creates a `.env` template for you to fill in.

### 2. Configure `.env`

```dotenv
RESEND_API_KEY=re_...         # From resend.com — Sending access only
SENDER_EMAIL=noreply@...      # Must be on a domain verified in Resend
SENDER_NAME="97 Things Every Software Architect Should Know"
BOOK_TITLE="97 Things Every Software Architect Should Know"
RECIPIENT=you@example.com
TZ=Europe/Copenhagen          # Your timezone
CRON_SCHEDULE="0 7 * * 1-5"   # When to send — weekdays at 07:00
```

**Resend setup:** Create an account at [resend.com](https://resend.com), verify your sending domain, and create an API key with **Sending access** only.

### 3. Start

```bash
docker compose up -d
```

The container pulls the pre-built image from `ghcr.io/phkp/chapter-email-sender:latest` and runs on the schedule you configured. A `data/` directory will be created automatically to store state and logs.

## Useful Commands

```bash
# View live logs
docker compose logs -f

# Preview next chapter without sending
docker compose exec email-sender python3 /app/sender.py --dry-run

# Force send, bypassing the already-sent-today guard
docker compose exec email-sender python3 /app/sender.py --force

# Reset progress to chapter 1
docker compose exec email-sender python3 /app/sender.py --reset
```

## Updating

To pull the latest image and restart the container:

```bash
docker compose pull && docker compose up -d
```

State and progress in `./data/` are preserved across updates.

## How It Works

1. Checks `data/state.json` to see if a chapter was already sent today — skips if so.
2. Retries previously failed chapters first, then continues in sequence.
3. On success: updates state. On failure: marks chapter as failed, exits with code 1.

State and logs are written to `./data/` on the host and survive container restarts and rebuilds.

## Development

Requires Python 3.9+ and no external packages.

```bash
cp .env.example .env  # fill in your values
set -a && source .env && set +a

python3 sender.py           # Normal run
python3 sender.py --dry-run # Preview without sending
python3 sender.py --force   # Send even if already sent today
python3 sender.py --reset   # Reset progress to chapter 1
```

When building locally with Docker, `docker-compose.override.yml` is picked up automatically and adds the `build:` context — no extra flags needed.

## Project Structure

Key files (not exhaustive):

```txt
chapter-email-sender/
├── sender.py            # Main script — no external dependencies
├── chapters.json        # All 97 chapters (title, author, content)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh        # Writes crontab from CRON_SCHEDULE at container startup
└── .env.example         # Template for .env
```

Runtime files in `data/` (gitignored): `state.json`, `sender.log`, `sender.lock`.
