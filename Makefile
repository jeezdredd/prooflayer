# ProofLayer top-level Makefile.
# Most commands assume Docker Compose v2 (`docker compose ...`).

SERVER ?= seb0107@ubuntu-dev.local
SERVER_FALLBACK ?= seb0107@192.168.8.112

.PHONY: help dev down logs ps build seed sh fe-sh \
        deploy-server deploy-bootstrap deploy-cf deploy-redeploy \
        seed-server wiki

help:
	@echo "ProofLayer Makefile"
	@echo ""
	@echo "Local dev:"
	@echo "  make dev               start full stack (docker compose up -d)"
	@echo "  make down              stop everything"
	@echo "  make logs              tail logs (all services)"
	@echo "  make ps                show running containers"
	@echo "  make build             rebuild backend/frontend images"
	@echo "  make seed              run seed_demo_data + seed_known_fakes"
	@echo "  make seed-server       run seed commands on remote server"
	@echo "  make sh                shell into backend container"
	@echo "  make fe-sh             shell into frontend container"
	@echo ""
	@echo "Server deploy ($(SERVER)):"
	@echo "  make deploy-bootstrap  ship + run server-bootstrap.sh (one-time)"
	@echo "  make deploy-cf         ship + run cf-tunnel-setup.sh (interactive)"
	@echo "  make deploy-server     deploy ProofLayer from this checkout"
	@echo "  make deploy-redeploy   force redeploy without code change"
	@echo ""
	@echo "Misc:"
	@echo "  make wiki              open Obsidian wiki vault in Finder"

# ===== local dev =====
dev:
	docker compose up -d
	@echo "Backend  http://localhost:8000"
	@echo "Frontend http://localhost:5173"
	@echo "Flower   http://localhost:5555"
	@echo "MinIO    http://localhost:9001"

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

build:
	docker compose build backend celery_worker flower frontend

seed:
	docker compose exec backend python manage.py seed_demo_data
	docker compose exec backend python manage.py seed_known_fakes

sh:
	docker compose exec backend bash

fe-sh:
	docker compose exec frontend sh

# ===== server deploy =====
SSH := ssh -t -o StrictHostKeyChecking=accept-new $(SERVER)

deploy-bootstrap:
	scp deploy/server-bootstrap.sh deploy/cf-tunnel-setup.sh deploy/deploy.sh $(SERVER):~
	$(SSH) "bash ~/server-bootstrap.sh"

deploy-cf:
	$(SSH) "bash ~/cf-tunnel-setup.sh"

deploy-server:
	scp deploy/deploy.sh $(SERVER):~
	$(SSH) "sudo install -o seb0107 -m 0755 ~/deploy.sh /srv/_platform/deploy.sh"
	$(SSH) "/srv/_platform/deploy.sh prooflayer"

deploy-redeploy:
	$(SSH) "/srv/_platform/deploy.sh prooflayer"

seed-server:
	$(SSH) "cd /srv/prooflayer/current && docker compose -f deploy/compose.prod.yml exec -T backend python manage.py seed_demo_data"
	$(SSH) "cd /srv/prooflayer/current && docker compose -f deploy/compose.prod.yml exec -T backend python manage.py seed_known_fakes"
	$(SSH) "cd /srv/prooflayer/current && docker compose -f deploy/compose.prod.yml exec -T backend python manage.py seed_users"

wiki:
	@open "wiki" 2>/dev/null || echo "wiki/ dir at $(PWD)/wiki - open as Obsidian vault"
