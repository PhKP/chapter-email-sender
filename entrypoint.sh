#!/bin/sh
set -e

: "${CRON_SCHEDULE:?CRON_SCHEDULE is not set — check your .env file}"

echo "${CRON_SCHEDULE} python3 /app/sender.py" > /app/crontab

exec supercronic /app/crontab
