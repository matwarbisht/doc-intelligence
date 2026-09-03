#!/usr/bin/env bash

set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv_command="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  uv_command="${HOME}/.local/bin/uv"
else
  echo "uv was not found. Install it from https://docs.astral.sh/uv/ and try again." >&2
  exit 1
fi

exec "${uv_command}" "$@"
