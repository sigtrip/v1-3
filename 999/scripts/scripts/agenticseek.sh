#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AS_DIR="$ROOT_DIR/external/agenticseek"

if [[ ! -d "$AS_DIR" ]]; then
  echo "[agenticseek] not found at $AS_DIR"
  echo "Run: git submodule update --init --recursive"
  exit 1
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

ARGOS_WORK_DIR="${ARGOS_AGENTICSEEK_WORK_DIR:-$ROOT_DIR}"
ARGOS_BACKEND_PORT="${ARGOS_AGENTICSEEK_BACKEND_PORT:-7777}"

# Автонастройка config.ini из .env Argos
python3 "$(dirname "$0")/agenticseek_autoconfig.py"

ensure_agenticseek_env() {
  local env_file="$AS_DIR/.env"
  if [[ -f "$env_file" ]]; then
    return 0
  fi

  cat > "$env_file" <<EOF
SEARXNG_BASE_URL="http://searxng:8080"
REDIS_BASE_URL="redis://redis:6379/0"
WORK_DIR="$ARGOS_WORK_DIR"
OLLAMA_PORT="11434"
LM_STUDIO_PORT="1234"
BACKEND_PORT="$ARGOS_BACKEND_PORT"
CUSTOM_ADDITIONAL_LLM_PORT="11435"
OPENAI_API_KEY='${OPENAI_API_KEY:-}'
DEEPSEEK_API_KEY='${DEEPSEEK_API_KEY:-}'
OPENROUTER_API_KEY='${OPENROUTER_API_KEY:-}'
TOGETHER_API_KEY='${TOGETHER_API_KEY:-}'
GOOGLE_API_KEY='${GOOGLE_API_KEY:-${GEMINI_API_KEY:-}}'
ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'
EOF

  echo "[agenticseek] created $env_file"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

start_full() {
  ensure_agenticseek_env
  (cd "$AS_DIR" && bash ./start_services.sh full)
}

start_backend_only() {
  ensure_agenticseek_env
  (cd "$AS_DIR" && compose_cmd --profile backend up -d backend)
}

stop_all() {
  (cd "$AS_DIR" && compose_cmd down || true)
}

status_all() {
  (cd "$AS_DIR" && compose_cmd ps)
}

health() {
  curl -fsS "http://127.0.0.1:${ARGOS_BACKEND_PORT}/health" || true
}

query_test() {
  local resp
  set +e
  resp="$(curl -sS -X POST "http://127.0.0.1:${ARGOS_BACKEND_PORT}/query" \
    -H 'Content-Type: application/json' \
    -d '{"query":"hi","tts_enabled":false}')"
  local code=$?
  set -e
  if [[ $code -ne 0 ]]; then
    echo "[agenticseek] query test failed: backend недоступен"
    return 1
  fi
  if [[ "$resp" == *"Internal Server Error"* ]]; then
    echo "[agenticseek] query test: backend отвечает 500"
    echo "[agenticseek] проверь LLM-провайдер в external/agenticseek/config.ini (обычно ollama)"
    echo "[agenticseek] и доступность host.docker.internal:11434 или API-ключей"
    return 2
  fi
  echo "$resp"
}

usage() {
  cat <<EOF
Usage: scripts/agenticseek.sh <start|start-backend|stop|status|health>

  start          Start full AgenticSeek stack (backend+frontend+searxng+redis)
  start-backend  Start only backend profile (port ${ARGOS_BACKEND_PORT})
  stop           Stop AgenticSeek containers
  status         Show container status
  health         Check backend health endpoint
  query-test     Check /query endpoint with a minimal prompt
EOF
}

cmd="${1:-}"
case "$cmd" in
  start) start_full ;;
  start-backend) start_backend_only ;;
  stop) stop_all ;;
  status) status_all ;;
  health) health ;;
  query-test) query_test ;;
  *) usage; exit 1 ;;
esac
