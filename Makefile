.PHONY: install dev dev-web dev-api db-start db-stop db-status db-reset db-test db-verify build test lint typecheck format check clean

install:
	pnpm install
	cd apps/api && ../../scripts/uv.sh sync --dev

dev:
	./scripts/dev.sh

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

db-reset:
	./scripts/supabase.sh db reset

db-test:
	cd apps/api && TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres ../../scripts/uv.sh run pytest -m integration

db-verify: db-reset db-test

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
