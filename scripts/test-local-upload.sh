#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status_file="$(mktemp)"
trap 'find "${status_file}" -delete' EXIT

"${project_root}/scripts/supabase.sh" status -o env >"${status_file}"

set -a
# Supabase emits shell-safe KEY=value pairs for the local stack.
source "${status_file}"
set +a

cd "${project_root}/apps/api"
TEST_DATABASE_URL="${DB_URL}" \
TEST_SUPABASE_URL="${API_URL}" \
TEST_SUPABASE_SERVICE_ROLE_KEY="${SERVICE_ROLE_KEY}" \
  ../../scripts/uv.sh run pytest -m integration
