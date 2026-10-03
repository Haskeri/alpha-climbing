# syntax=docker/dockerfile:1
# ---------- Этап 1: виртуальное окружение с зависимостями (uv) ----------
FROM python:3.15-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /build
COPY server/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv --python /usr/local/bin/python3 \
    && VIRTUAL_ENV=/opt/venv uv pip install -r requirements.txt

# ---------- Этап 2: образ приложения ----------
FROM python:3.15-slim
LABEL org.opencontainers.image.title="alpha-api" \
      org.opencontainers.image.description="Alpha — серверная часть приложения учёта восхождений" \
      org.opencontainers.image.source="https://github.com/Haskeri/alpha-climbing"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALPHA_LOG_DIR=/app/logs \
    ALPHA_DATA_DIR=/app/data \
    ALPHA_CLIENT_DIR=/app/client

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
RUN useradd --uid 1000 --create-home alpha

# исходные файлы проекта: серверная и клиентская части
COPY server/ /app/
COPY client/ /app/client/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && mkdir -p /app/logs /app/data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--preload", \
     "--access-logfile", "-", "wsgi:app"]
