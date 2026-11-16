export PATH := $(HOME)/.orbstack/bin:/usr/local/bin:/opt/homebrew/bin:$(PATH)
UV := /Users/john/.local/bin/uv
COMPOSE := docker compose --env-file .env -f docker/docker-compose.dual-stack.yml

.PHONY: sync init-env up-all up-b up-a down status logs replay serve-canvas verify test

sync:
	$(UV) sync --python 3.12 --extra dev

init-env:
	@if [ ! -f .env ]; then cp env.observability.example .env && echo "Created .env from env.observability.example"; else echo ".env already exists"; fi

up-all: init-env
	$(COMPOSE) --profile scheme-b --profile scheme-a up -d

up-b: init-env
	$(COMPOSE) --profile scheme-b up -d

up-a: init-env
	$(COMPOSE) --profile scheme-a up -d

down:
	$(COMPOSE) --profile scheme-b --profile scheme-a down

status:
	$(COMPOSE) --profile scheme-b --profile scheme-a ps

logs:
	$(COMPOSE) --profile scheme-b --profile scheme-a logs -f --tail=60

serve-canvas:
	$(UV) run obs-hub serve-canvas --port 8765

replay:
	$(UV) run obs-hub replay-boiler

verify:
	$(UV) run obs-hub verify-stack

test:
	$(UV) run pytest -v
