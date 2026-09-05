.PHONY: install dev dev-local dev-web dev-api db-start db-stop db-status db-migrate db-reset db-test db-test-upload db-verify auth-ownership-dry-run auth-ownership-apply safeguards-cleanup-dry-run safeguards-cleanup-apply live-e2e build test lint typecheck format check clean

install:
	pnpm install
	cd apps/api && ../../scripts/uv.sh sync --dev

dev:
	./scripts/dev.sh

dev-local:
	./scripts/dev-local.sh

dev-web:
	pnpm dev:web

dev-api:
	pnpm dev:api

db-start:
	./scripts/supabase.sh start

db-stop:
	./scripts/supabase.sh stop

db-status:
	./scripts/supabase.sh status

db-migrate:
	./scripts/supabase.sh migration up --local

db-reset:
	./scripts/supabase.sh db reset

db-test:
	cd apps/api && TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres ../../scripts/uv.sh run pytest -m integration

db-test-upload:
	./scripts/test-local-upload.sh

db-verify: db-reset db-test-upload

auth-ownership-dry-run:
	@test -n "$${CLAIM_OWNER_ID:-}" || (echo "Set CLAIM_OWNER_ID to an existing Supabase Auth user UUID." >&2; exit 1)
	cd apps/api && DATABASE_URL="$${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}" ../../scripts/uv.sh run python -m app.commands.claim_legacy_ownership --owner-id "$${CLAIM_OWNER_ID}"

auth-ownership-apply:
	@test -n "$${CLAIM_OWNER_ID:-}" || (echo "Set CLAIM_OWNER_ID to an existing Supabase Auth user UUID." >&2; exit 1)
	cd apps/api && DATABASE_URL="$${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}" ../../scripts/uv.sh run python -m app.commands.claim_legacy_ownership --owner-id "$${CLAIM_OWNER_ID}" --apply

safeguards-cleanup-dry-run:
	cd apps/api && DATABASE_URL="$${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}" ../../scripts/uv.sh run python -m app.commands.cleanup_safeguards --retention-days "$${RETENTION_DAYS:-30}"

safeguards-cleanup-apply:
	cd apps/api && DATABASE_URL="$${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}" ../../scripts/uv.sh run python -m app.commands.cleanup_safeguards --retention-days "$${RETENTION_DAYS:-30}" --apply

live-e2e:
	./scripts/test-live-e2e.sh

build:
	pnpm build

test:
	pnpm test

lint:
	pnpm lint

typecheck:
	pnpm typecheck

format:
	pnpm format

check:
	pnpm format:check
	pnpm lint
	pnpm typecheck
	pnpm test
	pnpm build

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name dist -o -name coverage \) -prune -exec rm -rf {} +
