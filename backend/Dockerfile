FROM python:3.12-slim

# ffmpeg is not optional: every audio turn is normalised through it before it
# reaches a provider. Managed Python runtimes do not ship it and give you no
# root to install it, which is the reason this service is containerised at all.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

WORKDIR /srv

COPY pyproject.toml uv.lock ./

# --no-dev also leaves out the `pronunciation` group, so torch and transformers
# never enter the image. That is what keeps it small enough to cold-start in
# seconds instead of minutes.
RUN uv sync --locked --no-dev

COPY app ./app

# Audio and the SQLite file land here. On a host with an ephemeral filesystem
# this survives only until the next restart, which is fine for reply audio and
# is why sessions belong in a managed database instead.
RUN mkdir -p /srv/data/audio

ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Shell form deliberately: $PORT is injected at runtime by the host, and the
# exec form would pass it through as a literal string.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
