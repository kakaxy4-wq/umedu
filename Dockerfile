FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CQ_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Pyodide, CodeMirror и шрифты кладутся в образ: сайт не ходит на чужие CDN
ARG SKIP_VENDOR=0
RUN if [ "$SKIP_VENDOR" != "1" ]; then bash scripts/fetch_vendor.sh; fi
RUN useradd --system --home /app umedu && mkdir -p /data && chown umedu /data
USER umedu
VOLUME /data
EXPOSE 8000
HEALTHCHECK CMD curl -sf http://127.0.0.1:8000/healthz || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
