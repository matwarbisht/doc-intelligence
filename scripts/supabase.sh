#!/usr/bin/env bash

set -euo pipefail

export VOLTA_FEATURE_PNPM="${VOLTA_FEATURE_PNPM:-1}"

if ! command -v docker >/dev/null 2>&1; then
  docker_desktop_bin="/Applications/Docker.app/Contents/Resources/bin"
  if [[ -x "${docker_desktop_bin}/docker" ]]; then
    export PATH="${docker_desktop_bin}:${PATH}"
  fi
fi

exec pnpm exec supabase "$@"
