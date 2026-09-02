.PHONY: install dev dev-web dev-api build test lint typecheck format check clean

install:
	pnpm install
	cd apps/api && uv sync --dev

dev:
	./scripts/dev.sh

dev-web:
	pnpm dev:web

dev-api:
	pnpm dev:api

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
