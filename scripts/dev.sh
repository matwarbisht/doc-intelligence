#!/usr/bin/env bash

set -euo pipefail

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

cleanup() {
  trap - EXIT INT TERM
  kill "${api_pid:-}" "${web_pid:-}" 2>/dev/null || true
  wait "${api_pid:-}" "${web_pid:-}" 2>/dev/null || true
}

shutdown() {
  cleanup
  exit 0
}

trap cleanup EXIT
trap shutdown INT TERM

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
  "${pnpm_command[@]}" --filter @doc-intelligence/web dev --host 127.0.0.1
) &
web_pid=$!

wait "${api_pid}" "${web_pid}"
