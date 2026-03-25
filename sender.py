#!/usr/bin/env python3
"""
Chapter email sender.
Sends one chapter per cron invocation. Keeps state in state.json.
"""

import argparse
import fcntl
import json
import logging
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
VERSION = os.environ.get("VERSION", "dev version")
CHAPTERS_FILE = BASE_DIR / "chapters.json"
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "sender.log"
LOCK_FILE = DATA_DIR / "sender.lock"


def load_config():
    required = ["RESEND_API_KEY", "SENDER_EMAIL", "SENDER_NAME", "RECIPIENT", "BOOK_TITLE"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    return {
        "resend_api_key": os.environ["RESEND_API_KEY"],
        "sender_email": os.environ["SENDER_EMAIL"],
        "sender_name": os.environ["SENDER_NAME"],
        "recipient": os.environ["RECIPIENT"],
        "book_title": os.environ["BOOK_TITLE"],
    }

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_state():
    if not STATE_FILE.exists():
        return {"last_chapter_sent": 0, "last_sent_date": None, "failed": []}
    return load_json(STATE_FILE)


def build_html(chapter, book_title):
    paragraphs = "".join(
        f"<p>{p.strip()}</p>"
        for p in chapter["content"].split("\n\n")
        if p.strip()
    )
    author = chapter.get("author", "")
    author_line = f"<p class='author'>By {author}</p>" if author else ""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 17px;
    line-height: 1.7;
    color: #1a1a1a;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }}
  .wrapper {{
    max-width: 620px;
    margin: 0 auto;
    padding: 40px 24px;
  }}
  .eyebrow {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #888;
    margin: 0 0 12px 0;
  }}
  h2 {{
    font-size: 26px;
    font-weight: 700;
    line-height: 1.3;
    margin: 0 0 32px 0;
    color: #111;
  }}
  p {{
    margin: 0 0 20px 0;
  }}
  .author {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 15px;
    font-style: italic;
    color: #444;
    margin-top: 32px;
    margin-bottom: 0;
  }}
  .footer {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
    color: #aaa;
    border-top: 1px solid #eee;
    margin-top: 24px;
    padding-top: 16px;
  }}
  .footer a {{
    color: #aaa;
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="eyebrow">{book_title} &middot; Chapter {chapter['chapter']}</div>
  <h2>{chapter['title']}</h2>
  {paragraphs}
  {author_line}
  <div class="footer">
    97 Things Every Software Architect Should Know is licensed under <a href="https://creativecommons.org/licenses/by/3.0/us/">Creative Commons Attribution 3.0</a><br>
    <br>
    Powered by <a href="https://github.com/PhKP/chapter-email-sender">chapter-email-sender</a> {VERSION}
  </div>
</div>
</body>
</html>"""


def send_email(config, chapter):
    author = chapter.get("author", "")
    plain = chapter["content"]
    if author:
        plain += f"\n\nBy {author}"
    plain += f"\n\n---\nLicensed under Creative Commons Attribution 3.0 — https://creativecommons.org/licenses/by/3.0/us/\nPowered by chapter-email-sender {VERSION} — https://github.com/PhKP/chapter-email-sender"

    payload = json.dumps({
        "from": f"{config['sender_name']} <{config['sender_email']}>",
        "to": [config["recipient"]],
        "subject": f"Chapter {chapter['chapter']}: {chapter['title']}",
        "text": plain,
        "html": build_html(chapter, config["book_title"]),
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {config['resend_api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "chapter-email-sender/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Resend returned {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Resend {e.code}: {body}") from e


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without sending or updating state")
    parser.add_argument("--reset", action="store_true", help="Reset state to start from chapter 1")
    parser.add_argument("--force", action="store_true", help="Bypass the already-sent-today guard")
    args = parser.parse_args()

    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("Another instance holds the lock — exiting to avoid state corruption.")
        lock_fd.close()
        sys.exit(1)

    try:
        _run(args)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _run(args):
    if args.reset:
        save_json(STATE_FILE, {"last_chapter_sent": 0, "last_sent_date": None, "failed": []})
        log.info("State reset. Will start from chapter 1 on next run.")
        return

    today = date.today()

    config = load_config()
    chapters = load_json(CHAPTERS_FILE)
    state = load_state()

    # Already sent something today
    if state["last_sent_date"] == str(today) and not args.force:
        log.info("Already sent a chapter today — skipping.")
        return

    # Find next chapter to send (retry failed ones first, then continue sequence)
    failed = state.get("failed", [])
    last_sent = state["last_chapter_sent"]

    # Build a lookup by chapter number
    chapters_by_num = {c["chapter"]: c for c in chapters}

    # Retry oldest failed chapter first
    if failed:
        next_chapter_num = failed[0]
        log.info(f"Retrying previously failed chapter {next_chapter_num}.")
    else:
        # Find next chapter after last sent
        sent_nums = set(
            c["chapter"] for c in chapters if c["chapter"] <= last_sent
        )
        remaining = [c for c in chapters if c["chapter"] not in sent_nums]
        if not remaining:
            log.info("All chapters have been sent. Nothing left to do.")
            return
        next_chapter_num = remaining[0]["chapter"]

    chapter = chapters_by_num.get(next_chapter_num)
    if not chapter:
        log.error(f"Chapter {next_chapter_num} not found in chapters.json.")
        return

    log.info(f"Sending chapter {chapter['chapter']}: {chapter['title']}")
    log.info(f"  To:      {config['recipient']}")
    log.info(f"  Subject: Chapter {chapter['chapter']}: {chapter['title']}")
    log.info(f"  Body:    {chapter['content'][:80]}{'...' if len(chapter['content']) > 80 else ''}")

    if args.dry_run:
        log.info("[DRY RUN] Email not sent, state not updated.")
        return

    try:
        send_email(config, chapter)
        log.info(f"Chapter {chapter['chapter']} sent successfully.")

        # Update state
        if next_chapter_num in failed:
            failed.remove(next_chapter_num)

        state["last_chapter_sent"] = max(last_sent, chapter["chapter"])
        state["last_sent_date"] = str(today)
        state["failed"] = failed
        save_json(STATE_FILE, state)

    except Exception as e:
        log.error(f"Failed to send chapter {chapter['chapter']}: {e}")
        if next_chapter_num not in failed:
            failed.append(next_chapter_num)
        state["failed"] = failed
        save_json(STATE_FILE, state)
        sys.exit(1)


if __name__ == "__main__":
    main()
