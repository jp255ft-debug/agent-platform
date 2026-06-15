.PHONY: help up up-full down build migrate test test-backend test-contracts test-lua \
        reconcile reconcile-payments reconcile-delegations reconcile-channels \
        simulate simulate-billing simulate-delegations simulate-payments simulate-pix simulate-all \
        pix-qrcode pix-webhook pix-status \
        logs clean

# Cores para output
GREEN := \033[0;32m
NC := \033[0m

help:
	@echo "$(GREEN)Agent Platform - Comandos Disponíveis$(NC)"
	@echo ""
	@echo "--- Serviços ---"
	@echo "  make up              - Iniciar serviços essenciais (postgres, redis, kafka, backend)"
	@echo "  make up-full         - Iniciar todos os serviços + dashboards (Grafana, Prometheus)"
	@echo "  make down            - Parar todos os serviços"
	@echo "  make build           - Reconstruir imagens Docker"
	@echo "  make migrate         - Executar migrações Alembic"
	@echo ""
	@echo "--- Testes ---"
	@echo "  make test            - Rodar todos os testes (Python, Solidity, Lua)"
	@echo "  make test-backend    - Rodar apenas testes Python"
	@echo "  make test-contracts  - Rodar apenas testes Solidity (Foundry)"
	@echo ""
	@echo "--- Pix (Pagamentos Brasileiros) ---"
	@echo "  make pix-qrcode      - Gerar QR Code Pix (exemplo)"
	@echo "  make pix-webhook     - Simular webhook de confirmação Pix"
	@echo "  make pix-status      - Verificar status de pagamento Pix"
	@echo "  make simulate-pix    - Simular carga de pagamentos Pix"
	@echo ""
	@echo "--- Reconciliação ---"
	@echo "  make reconcile       - Rodar os três scripts de reconciliação"
	@echo ""
	@echo "--- Simuladores ---"
	@echo "  make simulate-all    - Executar todos os simuladores"
	@echo ""
	@echo "--- Utilitários ---"
	@echo "  make logs            - Ver logs de todos os serviços"
	@echo "  make clean           - Remover containers, volumes e cache"
	@echo ""

up:
	docker compose up -d
	@echo "$(GREEN)✅ Serviços essenciais iniciados. Acesse: http://localhost:8000/health$(NC)"

up-full:
	docker compose --profile full up -d
	@echo "$(GREEN)✅ Todos os serviços (incluindo dashboards) iniciados.$(NC)"
	@echo "Grafana: http://localhost:3000 (admin/admin)"

down:
	docker compose down

build:
	docker compose build --no-cache

migrate:
	docker compose exec backend alembic upgrade head
	@echo "$(GREEN)✅ Migrações aplicadas.$(NC)"

# Testes
test: test-backend test-contracts test-lua

test-backend:
	docker compose exec backend pytest -v --cov=app --cov-report=term-missing

test-contracts:
	cd contracts && forge test -vvv

test-lua:
	@echo "Testando scripts Lua Redis..."
	@docker compose exec redis redis-cli --eval backend/app/infrastructure/cache/lua_scripts/rate_limit_check.lua , 10 1 5 test_key
	@echo "$(GREEN)✅ Testes Lua concluídos.$(NC)"

# Reconciliação
reconcile: reconcile-payments reconcile-delegations reconcile-channels

reconcile-payments:
	docker compose exec backend python scripts/reconciliation/reconcile_payments.py

reconcile-delegations:
	docker compose exec backend python scripts/reconciliation/reconcile_delegations.py

reconcile-channels:
	docker compose exec backend python scripts/reconciliation/reconcile_state_channels.py

# Pix (Pagamentos Brasileiros)
pix-qrcode:
	@echo "Gerando QR Code Pix de exemplo..."
	@curl -s -X POST http://localhost:8000/api/v1/pix/qrcode \
		-H "Content-Type: application/json" \
		-d '{"amount": 10.50, "description": "Teste de pagamento", "payer_name": "Cliente Exemplo", "expires_in": 3600}' | python -m json.tool

pix-webhook:
	@echo "Simulando webhook de confirmação Pix..."
	@curl -s -X POST http://localhost:8000/api/v1/pix/webhook \
		-H "Content-Type: application/json" \
		-d '{"id": "test_123", "status": "paid", "amount": 10.50, "payer_name": "Cliente Exemplo", "paid_at": "2026-06-13T10:00:00Z"}' | python -m json.tool

pix-status:
	@echo "Verificando status de pagamento Pix..."
	@curl -s http://localhost:8000/api/v1/pix/test_123/status | python -m json.tool

simulate-pix:
	docker compose exec agent-simulator python -m agents.simulator.pix_simulator --rate 5 --duration 60

# Simuladores
simulate-all: simulate-billing simulate-delegations simulate-payments

simulate-billing:
	docker compose exec agent-simulator python -m agents.simulator.agent_simulator --agents 10 --rate 5 --duration 60

simulate-delegations:
	docker compose exec agent-simulator python -m agents.simulator.delegation_simulator --agents 5 --rate 2 --duration 60

simulate-payments:
	docker compose exec agent-simulator python -m agents.simulator.payment_simulator --rate 3 --failure-rate 0.1 --duration 60

# Utilitários
logs:
	docker compose logs -f

clean:
	docker compose down -v
	docker system prune -f
	@echo "$(GREEN)✅ Ambiente limpo.$(NC)"
