# syntax=docker/dockerfile:1
# Cloud Run image for the legal chatbot API. uv for fast, reproducible installs.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8080
# Cloud Run sets $PORT; bind to it.
CMD ["sh", "-c", "uvicorn htl.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
