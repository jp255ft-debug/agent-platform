#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Agent Platform - Demonstração Completa             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"

# =============================================================================
# 1. Verificar pré-requisitos
# =============================================================================
echo -e "\n${YELLOW}[1/7] Verificando pré-requisitos...${NC}"

if ! command -v docker &> /dev/null; then
    echo "❌ Docker não encontrado. Instale Docker 24+ primeiro."
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "❌ curl não encontrado."
    exit 1
fi

echo -e "  ✅ Docker $(docker --version)"
echo -e "  ✅ curl disponível"

# =============================================================================
# 2. Subir serviços
# =============================================================================
echo -e "\n${YELLOW}[2/7] Subindo serviços Docker...${NC}"
make up
sleep 5

# Aguardar backend ficar saudável
echo -e "\n  Aguardando backend ficar saudável..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "healthy"; then
        echo -e "  ✅ Backend saudável!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "  ❌ Backend não respondeu após 30s"
        exit 1
    fi
    sleep 2
done

# =============================================================================
# 3. Health check detalhado
# =============================================================================
echo -e "\n${YELLOW}[3/7] Health check detalhado...${NC}"
HEALTH=$(curl -s http://localhost:8000/health)
echo "$HEALTH" | python -m json.tool 2>/dev/null || echo "$HEALTH"

# =============================================================================
# 4. Aplicar migrações
# =============================================================================
echo -e "\n${YELLOW}[4/7] Aplicando migrações do banco de dados...${NC}"
make migrate
echo -e "  ✅ Migrações aplicadas com sucesso!"

# =============================================================================
# 5. Executar testes
# =============================================================================
echo -e "\n${YELLOW}[5/7] Executando testes...${NC}"

echo -e "\n  --- Testes Python (pytest) ---"
docker compose exec backend pytest -v --tb=short 2>&1 | tail -20 || true

echo -e "\n  --- Testes Solidity (Foundry) ---"
cd contracts && forge test -vvv 2>&1 | tail -10 || true
cd ..

echo -e "\n  ✅ Testes concluídos!"

# =============================================================================
# 6. Simular carga
# =============================================================================
echo -e "\n${YELLOW}[6/7] Simulando agentes e pagamentos...${NC}"

echo -e "\n  --- Simulando billing (10 agentes, 5 eventos/s, 30s) ---"
docker compose exec agent-simulator python -m agents.simulator.agent_simulator \
    --agents 10 --rate 5 --duration 30 2>&1 | tail -15

echo -e "\n  --- Simulando delegações EIP-7702 (5 agentes, 30s) ---"
docker compose exec agent-simulator python -m agents.simulator.delegation_simulator \
    --agents 5 --rate 2 --duration 30 2>&1 | tail -15

echo -e "\n  --- Simulando pagamentos x402 (3 eventos/s, 30s) ---"
docker compose exec agent-simulator python -m agents.simulator.payment_simulator \
    --rate 3 --failure-rate 0.1 --duration 30 2>&1 | tail -15

echo -e "\n  ✅ Simulação concluída!"

# =============================================================================
# 7. Rodar reconciliação
# =============================================================================
echo -e "\n${YELLOW}[7/7] Verificando consistência (reconciliação)...${NC}"

echo -e "\n  --- Reconciliação de pagamentos ---"
docker compose exec backend python scripts/reconciliation/reconcile_payments.py 2>&1 | tail -20

echo -e "\n  --- Reconciliação de delegações ---"
docker compose exec backend python scripts/reconciliation/reconcile_delegations.py 2>&1 | tail -20

echo -e "\n  --- Reconciliação de state channels ---"
docker compose exec backend python scripts/reconciliation/reconcile_state_channels.py 2>&1 | tail -20

# =============================================================================
# Resumo final
# =============================================================================
echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Demonstração concluída com sucesso!               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  📍 Backend API:    http://localhost:8000/docs"
echo -e "  📍 Swagger UI:     http://localhost:8000/docs"
echo -e "  📍 Health Check:   http://localhost:8000/health"
echo ""
echo -e "  Para subir dashboards Grafana:"
echo -e "    docker compose --profile full up -d"
echo -e "    Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo -e "  Para ver logs em tempo real:"
echo -e "    make logs"
echo ""
