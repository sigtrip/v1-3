
FROM python:3.11-slim

# ── Системные зависимости ────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libssl-dev libffi-dev \
        ffmpeg libportaudio2 libasound2-dev \
        git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN mkdir -p logs config builds/replicas assets data

EXPOSE 8080 55771

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python health_check.py || exit 1

CMD ["python", "main.py", "--no-gui", "--dashboard"]
