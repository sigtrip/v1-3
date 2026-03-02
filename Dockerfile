FROM python:3.11-slim

# ── Системные зависимости ────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libssl-dev libffi-dev \
        ffmpeg libportaudio2 libasound2-dev \
        git curl \
    && rm -rf /var/lib/apt/lists/*

# ── Папка приложения ─────────────────────────────────────
WORKDIR /app

# ── Зависимости (кэшируем слой) ─────────────────────────
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# ── Копируем проект ──────────────────────────────────────
COPY . .

# ── Создаём необходимые директории ───────────────────────
RUN mkdir -p logs config builds/replicas assets data

# ── Порты: 8080 — веб-дашборд, 55771 — P2P ──────────────
EXPOSE 8080 55771

# ── Healthcheck ──────────────────────────────────────────
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python health_check.py || exit 1

# ── Запуск: headless + dashboard ─────────────────────────
CMD ["python", "main.py", "--no-gui", "--dashboard"]
