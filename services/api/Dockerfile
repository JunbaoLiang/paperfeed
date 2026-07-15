# PaperFeed online API — lightweight image, NO torch (spec A4/§14).
# Build from the repo root:  docker build -f services/api/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# HF Spaces runs containers as a non-root user (uid 1000).
RUN useradd -m -u 1000 app
WORKDIR /code

# Base dependency group only — the pipelines extra (torch etc.) is never installed here.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && chown -R app:app /code

COPY packages ./packages
COPY services ./services

USER app
ENV PATH="/code/.venv/bin:$PATH" \
    MODEL_CACHE_DIR=/tmp/paperfeed_models

EXPOSE 7860
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "7860"]
