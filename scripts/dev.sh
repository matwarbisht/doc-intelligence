#!/usr/bin/env bash

set -euo pipefail

# Give each background job its own process group so reloaders and package-manager
# children can be stopped together.
set -m

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Volta requires this flag before its pnpm shim becomes available.
export VOLTA_FEATURE_PNPM=1

if command -v pnpm >/dev/null 2>&1 && pnpm --version >/dev/null 2>&1; then
  pnpm_command=(pnpm)
elif command -v corepack >/dev/null 2>&1; then
  pnpm_command=(corepack pnpm)
else
  echo "pnpm was not found. Install pnpm 10 and try again." >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  uv_command="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  uv_command="${HOME}/.local/bin/uv"
else
  echo "uv was not found. Install it from https://docs.astral.sh/uv/ and try again." >&2
  exit 1
fi

check_port() {
  local port="$1"
  local service="$2"
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null; then
    echo "${service} could not start because port ${port} is already in use." >&2
    echo "Inspect it with: lsof -nP -iTCP:${port} -sTCP:LISTEN" >&2
    echo "Stop the owning process, then run make dev-local again." >&2
    exit 1
  fi
}

stop_group() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] || return 0
  kill -TERM -- "-${pid}" 2>/dev/null || return 0
  for _ in {1..20}; do
    kill -0 -- "-${pid}" 2>/dev/null || return 0
    sleep 0.1
  done
  kill -KILL -- "-${pid}" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM
  stop_group "${api_pid:-}"
  stop_group "${web_pid:-}"
  wait "${api_pid:-}" "${web_pid:-}" 2>/dev/null || true
}

shutdown() {
  cleanup
  exit 0
}

trap cleanup EXIT
trap shutdown INT TERM

check_port 8000 "API"
check_port 5173 "Frontend"

echo "Starting Document Intelligence"
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop both servers."
echo

(
  cd "${project_root}/apps/api"
  "${uv_command}" run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
api_pid=$!

(
  cd "${project_root}"
  "${pnpm_command[@]}" --filter @doc-intelligence/web dev --host 127.0.0.1 --strictPort
) &
web_pid=$!

while kill -0 "${api_pid}" 2>/dev/null && kill -0 "${web_pid}" 2>/dev/null; do
  sleep 0.5
done

if ! kill -0 "${api_pid}" 2>/dev/null; then
  wait "${api_pid}" || exit_code=$?
  echo "API server exited; stopping the frontend." >&2
else
  wait "${web_pid}" || exit_code=$?
  echo "Frontend server exited; stopping the API." >&2
fi

exit "${exit_code:-1}"
