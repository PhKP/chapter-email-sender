# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Sends one chapter per cron invocation from *97 Things Every Software Architect Should Know* to a configured email address via the [Resend](https://resend.com) API. Tracks progress in `data/state.json` so it always resumes where it left off.

## Running the script

Requires env vars set (source `.env` first):

```bash
set -a && source .env && set +a

python3 sender.py           # Normal run
python3 sender.py --dry-run # Preview next chapter without sending or updating state
python3 sender.py --reset   # Reset progress to chapter 1
python3 sender.py --force   # Send even if a chapter was already sent today
```

## Docker

```bash
mkdir -p data
docker compose up -d          # Start (schedule set via CRON_SCHEDULE in .env)
docker compose up -d --build  # Rebuild after code changes
docker compose logs -f        # Tail logs
docker compose exec email-sender python3 /app/sender.py --dry-run
```

## Architecture

- **`sender.py`** — single-file script, no external dependencies (stdlib only). Entry point is `main()`.
- **`chapters.json`** — static data file with all 97 chapters (title, author, content). Never modified at runtime.
- **`data/state.json`** — runtime state: `last_chapter_sent` (int), `last_sent_date` (YYYY-MM-DD), `failed` (list of chapter numbers to retry).
- **`data/sender.log`** — append-only log file.
- **`data/sender.lock`** — exclusive lock file held for the duration of each run to prevent concurrent access to state.
- **`scrape_chapters.py`** — one-off utility to regenerate `chapters.json` from the web source.

The container uses [supercronic](https://github.com/aptible/supercronic) (not system cron) so logs stream to stdout. The `data/` directory is mounted as a Docker volume so state and logs survive rebuilds.

### Execution flow (`sender.py`)

1. Acquire exclusive lock on `data/sender.lock` (non-blocking — exits immediately if another instance holds it).
2. Skip if `last_sent_date` == today (idempotent — use `--force` to bypass).
3. If `failed` list is non-empty, retry the oldest failed chapter first.
4. Otherwise send the next chapter after `last_chapter_sent`.
5. On success: update state. On failure: append to `failed`, exit 1.

### DATA_DIR

Defaults to `./data/` relative to the script (`BASE_DIR / "data"`), so it always resolves correctly regardless of working directory. In Docker, the Dockerfile sets `DATA_DIR=/data` (the mounted volume), overriding this default. Override with the `DATA_DIR` env var.

## Required environment variables

| Variable | Description |
| --- | --- |
| `RESEND_API_KEY` | Resend API key (Sending access only) |
| `SENDER_EMAIL` | From address — must be on a Resend-verified domain |
| `SENDER_NAME` | Display name in the From field |
| `BOOK_TITLE` | Book title shown in the email header and footer |
| `RECIPIENT` | Delivery address |
| `TZ` | Timezone for the cron schedule (Docker only) |
| `CRON_SCHEDULE` | When to send, in cron syntax (Docker only) |

## Versioning

`VERSION` is baked into the Docker image at build time via `ARG VERSION=handbuild`. GitHub Actions passes the git tag automatically. When running natively, `sender.py` defaults to `"dev version"` if `VERSION` is not set.

## .claude directory

`.claude/` is a symlink to `~/.dotfiles/claude/email-sender/` — real files live there, not in the repo. This survives `git clean -xfd` (which removes the symlink but not the dotfiles). To recreate after a clean:

```bash
ln -s ~/.dotfiles/claude/email-sender .claude
```
