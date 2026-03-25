FROM python:3.12-slim

# Install supercronic — a cron daemon built for containers (logs to stdout)
ARG SUPERCRONIC_VERSION=0.2.44
ARG SUPERCRONIC_SHA1SUM=6eb0a8e1e6673675dc67668c1a9b6409f79c37bc
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL \
       "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
       -o /usr/local/bin/supercronic \
    && echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum -c - \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ARG VERSION=handbuild
ENV VERSION=$VERSION
ENV DATA_DIR=/data

WORKDIR /app
COPY sender.py chapters.json entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
