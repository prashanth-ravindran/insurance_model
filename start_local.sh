#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Start the local Chubb Arabia underwriting workbench.

Usage:
  ./start_local.sh

Environment overrides:
  BACKEND_HOST              default: 127.0.0.1
  BACKEND_PORT              default: 8000
  FRONTEND_HOST             default: 127.0.0.1
  FRONTEND_PORT             default: 5173
  UNDERWRITING_MODEL_ROWS   default: 2500
  VITE_API_BASE_URL         default: http://$BACKEND_HOST:$BACKEND_PORT
  .env                     loaded automatically when present
  GEMINI_API_KEY            required only for real unstructured extraction
  GEMINI_EXTRACTION_MODEL   default: gemini-3.5-flash
  UNSTRUCTURED_UPLOAD_DIR   default: artifacts/uploads
  UNSTRUCTURED_MAX_UPLOAD_MB default: 25
  START_STREAMLIT           default: 0; set to 1 to also start analytics app
  STREAMLIT_PORT            default: 8501

Examples:
  ./start_local.sh
  BACKEND_PORT=8010 FRONTEND_PORT=5174 ./start_local.sh
  START_STREAMLIT=1 ./start_local.sh
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    line="${line#export }"
    [[ "$line" == *=* ]] || continue
    local key="${line%%=*}"
    local value="${line#*=}"
    key="$(printf '%s' "$key" | tr -d '[:space:]')"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -n "${!key+x}" ]]; then
      continue
    fi
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"
    local first_char="${value:0:1}"
    local last_char="${value: -1}"
    if [[ ${#value} -ge 2 && "$first_char" == "$last_char" && ( "$first_char" == '"' || "$first_char" == "'" ) ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$env_file"
}

load_env_file "$ROOT_DIR/.env"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
UNDERWRITING_MODEL_ROWS="${UNDERWRITING_MODEL_ROWS:-2500}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
START_STREAMLIT="${START_STREAMLIT:-0}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

require_file() {
  local path="$1"
  local hint="$2"
  if [[ ! -e "$path" ]]; then
    echo "Missing $path" >&2
    echo "$hint" >&2
    exit 1
  fi
}

require_command() {
  local command_name="$1"
  local hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing command: $command_name" >&2
    echo "$hint" >&2
    exit 1
  fi
}

port_is_free() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PYCHECK'
import socket
import sys
host, port = sys.argv[1], int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PYCHECK
}

check_port() {
  local name="$1"
  local host="$2"
  local port="$3"
  if ! port_is_free "$host" "$port"; then
    echo "$name port is already in use: $host:$port" >&2
    echo "Choose another port, for example: ${name^^}_PORT=$((port + 1)) ./start_local.sh" >&2
    exit 1
  fi
}

wait_for_url() {
  local label="$1"
  local url="$2"
  for _ in $(seq 1 80); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$label ready: $url"
      return 0
    fi
    sleep 0.25
  done
  echo "$label did not become ready: $url" >&2
  return 1
}

require_command python3 "Install Python 3 and create the project virtual environment."
require_command npm "Install Node.js/npm, then run: cd frontend && npm install"
require_command curl "Install curl or use the service URLs printed by this script manually."
require_file "$ROOT_DIR/.venv/bin/uvicorn" "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
require_file "$ROOT_DIR/frontend/node_modules" "Run: cd frontend && npm install"

check_port backend "$BACKEND_HOST" "$BACKEND_PORT"
check_port frontend "$FRONTEND_HOST" "$FRONTEND_PORT"
if [[ "$START_STREAMLIT" == "1" ]]; then
  require_file "$ROOT_DIR/.venv/bin/streamlit" "Run: .venv/bin/pip install -r requirements.txt"
  check_port streamlit "$BACKEND_HOST" "$STREAMLIT_PORT"
fi

pids=()
cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if (( ${#pids[@]} > 0 )); then
    echo
    echo "Stopping local services..."
    for pid in "${pids[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
    wait "${pids[@]}" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

mkdir -p artifacts/quotes artifacts/uploads

echo "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
UNDERWRITING_MODEL_ROWS="$UNDERWRITING_MODEL_ROWS" \
  "$ROOT_DIR/.venv/bin/uvicorn" underwriting_system.api:app \
  --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
pids+=("$!")

echo "Starting React workbench on http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$ROOT_DIR/frontend"
  VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
pids+=("$!")

if [[ "$START_STREAMLIT" == "1" ]]; then
  echo "Starting Streamlit analytics app on http://${BACKEND_HOST}:${STREAMLIT_PORT}"
  "$ROOT_DIR/.venv/bin/streamlit" run app.py \
    --server.address "$BACKEND_HOST" --server.port "$STREAMLIT_PORT" \
    --server.headless true &
  pids+=("$!")
fi

wait_for_url "Backend" "http://${BACKEND_HOST}:${BACKEND_PORT}/health"
wait_for_url "Frontend" "http://${FRONTEND_HOST}:${FRONTEND_PORT}"
if [[ "$START_STREAMLIT" == "1" ]]; then
  wait_for_url "Streamlit" "http://${BACKEND_HOST}:${STREAMLIT_PORT}/_stcore/health"
fi

cat <<EOF

Local services are running.
  Underwriting API:       http://${BACKEND_HOST}:${BACKEND_PORT}
  Underwriting workbench: http://${FRONTEND_HOST}:${FRONTEND_PORT}
EOF
if [[ "$START_STREAMLIT" == "1" ]]; then
  echo "  Analytics app:          http://${BACKEND_HOST}:${STREAMLIT_PORT}"
fi
cat <<'EOF'

Press Ctrl-C to stop all services.
EOF

wait
