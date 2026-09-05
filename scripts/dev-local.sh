#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status_file="$(mktemp)"
trap 'find "${status_file}" -delete' EXIT

"${project_root}/scripts/supabase.sh" status -o env >"${status_file}"

set -a
source "${status_file}"
set +a

export DATABASE_URL="${DB_URL}"
export SUPABASE_URL="${API_URL}"
export SUPABASE_PUBLISHABLE_KEY="${ANON_KEY}"
export SUPABASE_SERVICE_ROLE_KEY="${SERVICE_ROLE_KEY}"
export VITE_SUPABASE_URL="${API_URL}"
export VITE_SUPABASE_PUBLISHABLE_KEY="${ANON_KEY}"
find "${status_file}" -delete
trap - EXIT

exec "${project_root}/scripts/dev.sh"
