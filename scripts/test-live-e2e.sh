#!/usr/bin/env bash

set -euo pipefail

api_url="${API_URL:-http://127.0.0.1:8000}"
sample_file="${E2E_SAMPLE_FILE:-examples/acme-quarterly-update.txt}"
question="${E2E_QUESTION:-How much did Acme Robotics recurring revenue grow?}"
timeout_seconds="${E2E_TIMEOUT_SECONDS:-360}"

if [[ ! -f "$sample_file" ]]; then
  echo "Example file not found: $sample_file" >&2
  exit 1
fi

if ! curl --fail --silent --show-error "$api_url/api/v1/health" >/dev/null; then
  echo "API is not reachable at $api_url. Start it with 'make dev-local'." >&2
  exit 1
fi

upload_response="$(curl --fail --silent --show-error \
  -F "file=@${sample_file}" \
  "$api_url/api/v1/documents")"

document_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["document"]["id"])' <<<"$upload_response")"
duplicate="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin)["duplicate"]).lower())' <<<"$upload_response")"

if [[ "$duplicate" == "true" ]]; then
  curl --fail --silent --show-error \
    -X POST "$api_url/api/v1/documents/$document_id/process" >/dev/null
fi

deadline=$((SECONDS + timeout_seconds))
status="queued"
while (( SECONDS < deadline )); do
  detail="$(curl --fail --silent --show-error "$api_url/api/v1/documents/$document_id")"
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$detail")"
  case "$status" in
    ready)
      break
      ;;
    *_failed)
      error="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((j["error"] for j in d["processing"] if j["error"]), "unknown failure"))' <<<"$detail")"
      echo "Processing failed in status '$status': $error" >&2
      exit 1
      ;;
  esac
  sleep 2
done

if [[ "$status" != "ready" ]]; then
  echo "Timed out after ${timeout_seconds}s waiting for document $document_id." >&2
  exit 1
fi

query_payload="$(python3 -c 'import json,sys; print(json.dumps({"query": sys.argv[1]}))' "$question")"
query_response="$(curl --fail --silent --show-error \
  -H 'content-type: application/json' \
  -d "$query_payload" \
  "$api_url/api/v1/query")"

python3 -c '
import json, sys
payload = json.load(sys.stdin)
if not payload.get("answer"):
    raise SystemExit("Query returned an empty answer.")
if not payload.get("sources"):
    raise SystemExit("Query returned no cited sources.")
print("Live end-to-end check passed: document={} sources={}".format(sys.argv[1], len(payload["sources"])))
print("Answer: {}".format(payload["answer"]))
' "$document_id" <<<"$query_response"
