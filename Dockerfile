# ---------- Этап 1: сборка зависимостей ----------
FROM python:3.12-slim AS build
WORKDIR /build
COPY server/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- Этап 2: образ приложения ----------
FROM python:3.12-slim
LABEL org.opencontainers.image.title="alpha-api" \
      org.opencontainers.image.description="Alpha — серверная часть приложения учёта восхождений" \
      org.opencontainers.image.source="https://github.com/Haskeri/alpha-climbing"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALPHA_LOG_DIR=/app/logs \
    ALPHA_DATA_DIR=/app/data \
    ALPHA_CLIENT_DIR=/app/client

WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels \
    && useradd --uid 1000 --create-home alpha

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
