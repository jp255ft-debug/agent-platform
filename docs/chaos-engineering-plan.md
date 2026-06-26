# 🔧 Plano de Chaos Engineering — Agent Platform (Versão Final Validada)

> **Data:** 16/06/2026
> **Objetivo:** Validar a resiliência do sistema sob condições extremas antes de apresentação B2B.
> **Base:** Comandos reais do `Makefile`, `docker-compose.yml` e simuladores existentes.

---

## 📋 Sumário Executivo

| Fase | Teste | Critério de Sucesso | Evidência Gerada |
|------|-------|---------------------|------------------|
| 1 | Carga extrema (200 req/s) | Latência p99 < 5s, 0 erros 5xx | Relatório de performance (Grafana) |
| 2 | Fuzzing on-chain (10k runs) | Todos os testes passam | Log do `forge test` |
| 3 | Queda do PostgreSQL | Reconciliação detecta discrepâncias | Relatório de reconciliação |
| 4 | Concorrência (double-spend) | Rate limiting bloqueia excessos | Logs com 429, script Lua retorna 0 |
| 5 | Queda do Kafka (Poison Pill) | Consumer continua após erro | Logs sem crash |
| 6 | Queda do Redis (fail-open) | Backend permite requisições | Logs com "fail-open" |
| 7 | WebSocket C10k | 100 conexões simultâneas aceitas | Logs sem "too many files" |
| 8 | SQL injection no JSONB | Payload rejeitado (422/400) | Resposta HTTP |
| 9 | Payload gigante (10MB) | Rejeitado com 413 (ou 422) | Resposta HTTP |
| 10 | Reentrância no PaymentVerifier | Padrão CEI verificado | Código fonte auditado |
| 11 | Replay cross-chain | `block.chainid` no domain separator | Código fonte verificado |
| 12 | Sobrecarga de /metrics | Prometheus continua scraping | Logs do Prometheus |
| 13 | Vazamento de memória (24h) | Memória estabiliza | `docker stats` |

---

## ⚠️ Pré-requisitos

Antes de qualquer teste, garanta que o ambiente está limpo e funcionando:

```bash
# Limpar ambiente anterior
make clean

# Subir infraestrutura completa (com dashboards)
make up-full

# Aguardar todos os healthchecks passarem
docker compose ps
# Todos os serviços devem estar "healthy"
```

---

## FASE 1: Teste de Carga Extrema

**Problema original:** `SIMULATOR_RATE=500 make simulate-all` não funciona.

**Correção:** Os simuladores usam argumentos CLI, não env vars. Execute diretamente no container `backend`.

```bash
# Inicia carga em background
docker compose exec -d backend python -m agents.simulator.agent_simulator \
    --agents 100 --rate 200 --duration 300

docker compose exec -d backend python -m agents.simulator.payment_simulator \
    --rate 100 --failure-rate 0.05 --duration 300

# Monitora em tempo real
docker compose logs -f backend | grep -E "429|500|ERROR"
```

**Métrica crítica:** `p99_latency` no Grafana (`agent-platform-performance.json`) deve ser < 5s.

---

## FASE 2: Fuzzing Matemático On-Chain

**Problema original:** `FOUNDRY_FUZZ_RUNS=10000` pode não ser reconhecido em versões antigas.

**Correção:** Use `--fuzz-runs` explicitamente.

```bash
cd contracts

for contract in AgentDelegation PaymentVerifier AgentReputationSBT StateChannelLib; do
    forge test --fuzz-runs 10000 --match-contract $contract -vvv
done
```

**Métrica crítica:** Todos os testes devem passar (`0 failed`).

---

## FASE 3: Engenharia de Caos (Queda de Banco)

**Problema original:** `docker kill` pode corromper dados; `make reconcile` falha se backend estiver fora.

**Correção:** Use `docker compose stop` (SIGTERM) para permitir graceful shutdown.

```bash
# Iniciar simulador em background
docker compose exec -d backend python -m agents.simulator.payment_simulator \
    --rate 50 --failure-rate 0.1 --duration 120

sleep 10

# Parar PostgreSQL gentilmente
docker compose stop postgres
sleep 10

# Reiniciar
docker compose start postgres
sleep 15
docker compose exec postgres pg_isready -U agent_user -d agent_platform

# Reiniciar backend (caiu junto)
docker compose start backend
sleep 10
curl -f http://localhost:8000/health

# Rodar reconciliação
docker compose exec backend python scripts/reconciliation/reconcile_payments.py
```

**Métrica crítica:** Relatório deve mostrar discrepâncias > 0, indicando que o sistema detectou a falha.

---

## FASE 4: Concorrência (Double-Spend)

**Teste:** 50 agentes simultâneos tentando consumir a mesma cota.

```bash
docker compose exec backend python -m agents.simulator.agent_simulator \
    --agents 50 --rate 300 --duration 30

# Verificar se rate limit bloqueou alguns
docker compose logs backend | grep "429"

# Testar manualmente o Lua script
docker compose exec redis redis-cli --eval \
    backend/app/infrastructure/cache/lua_scripts/rate_limit_check.lua \
    , rate_limit:test:agent1 10 1 $(date +%s) 1
# Deve retornar 1 (permitido) ou 0 (bloqueado)
```

**Métrica crítica:** Número de requisições bloqueadas deve ser proporcional à taxa excedente. Se `rate=300` e limite=200 req/s, ~33% serão bloqueados.

---

## FASE 5: Queda do Kafka (Poison Pill)

```bash
# Enviar payload inválido
docker compose exec kafka /usr/bin/kafka-console-producer \
    --bootstrap-server localhost:9092 --topic agent.registered <<< '{"invalid": "payload"}'

# Verificar se consumer sobreviveu
docker compose logs backend | grep -E "ERROR|poison|unprocessable|skipping"

# Enviar mensagem válida para confirmar que o consumer ainda roda
echo '{"agent_id": "test-123", "metadata": {"name": "TestAgent"}}' | \
docker compose exec -T kafka /usr/bin/kafka-console-producer \
    --bootstrap-server localhost:9092 --topic agent.registered

docker compose logs backend --tail=20
```

**Critério:** O consumer deve logar um erro **mas continuar processando** a mensagem válida subsequente.

---

## FASE 6: Queda do Redis (Fail-Open)

```bash
docker compose stop redis

curl -s -X POST http://localhost:8000/api/v1/agents/register \
    -H "Content-Type: application/json" \
    -d '{"address": "0x1234567890abcdef"}' | python -m json.tool

docker compose logs backend | grep -E "Redis|fail.open"
```

**Critério:** O backend deve retornar `200` (ou `422` se o endereço for inválido) e logar um warning de "fail-open".

---

## FASE 7: WebSocket C10k

```bash
# Usando wscat (instalar se necessário: npm install -g wscat)
for i in {1..100}; do
    (wscat -c ws://localhost:8000/ws -x '{"type":"ping"}' -w 5 > /dev/null 2>&1 &)
done

docker compose logs backend --tail=50 | grep -E "WebSocket|error"
```

**Alternativa sem wscat:**
```bash
docker compose exec backend python -c "
import asyncio, websockets
async def connect():
    try:
        async with websockets.connect('ws://backend:8000/ws') as ws:
            await ws.send('{\"type\":\"ping\"}')
            await asyncio.sleep(1)
    except Exception as e:
        print(f'Error: {e}')
asyncio.run(asyncio.gather(*[connect() for _ in range(100)]))
"
```

**Critério:** Nenhum erro de "too many open files" ou timeout.

---

## FASE 8: Injeção SQL no JSONB

```bash
docker compose exec backend python -c "
import httpx
payload = {
    'agent_id': \"agent-1'; DROP TABLE events; --\",
    'metadata': {'name': \"' OR 1=1 --\"}
}
r = httpx.post('http://backend:8000/api/v1/agents/register', json=payload)
print(f'Status: {r.status_code}')
print(f'Response: {r.text[:300]}')
"
```

**Critério:** Retorna `422` (Unprocessable Entity) ou `400` (Bad Request).

---

## FASE 9: Payload Gigante (10MB)

```bash
dd if=/dev/zero bs=1M count=10 | base64 > /tmp/large_payload.txt

docker compose exec backend python -c "
import httpx, json
with open('/tmp/large_payload.txt') as f:
    payload = {'address': '0x123', 'metadata': {'data': f.read()}}
r = httpx.post('http://backend:8000/api/v1/agents/register', json=payload, timeout=5)
print(f'Status: {r.status_code}')
"
```

**Critério:** Idealmente `413 Payload Too Large`. Se retornar `200`, há risco de OOM.

---

## FASE 10: Reentrância no PaymentVerifier

Auditoria manual:

```bash
cd contracts

# Verificar ReentrancyGuard
grep -n "ReentrancyGuard" src/PaymentVerifier.sol

# Verificar ordem dos nonces (deve ser antes de qualquer call)
awk '/nonces\[msg.sender\]/ {print NR, $0}' src/PaymentVerifier.sol

# Verificar chamadas externas
grep -n "call\|transfer\|send" src/PaymentVerifier.sol
```

**Critério:** O nonce deve ser incrementado **antes** de qualquer `call` ou `transfer`.

---

## FASE 11: Replay Attack Cross-Chain

```bash
cd contracts
grep -n "DOMAIN_SEPARATOR" src/AgentDelegation.sol src/PaymentVerifier.sol
grep -n "chainid" src/AgentDelegation.sol src/PaymentVerifier.sol
```

**Critério:** O `DOMAIN_SEPARATOR` deve incluir `block.chainid`. Caso contrário, a mesma assinatura pode ser reutilizada em outras chains.

---

## FASE 12: Sobrecarga de /metrics

```bash
for i in {1..1000}; do
    curl -s http://localhost:8000/metrics > /dev/null 2>&1 &
done
wait

docker compose logs prometheus --tail=20 | grep -E "error|timeout"
```

**Critério:** O Prometheus deve continuar fazendo scrape sem erros.

---

## FASE 13: Vazamento de Memória (24h)

```bash
nohup docker compose exec backend python -m agents.simulator.agent_simulator \
    --agents 10 --rate 10 --duration 86400 > billing_24h.log 2>&1 &

nohup docker compose exec backend python -m agents.simulator.payment_simulator \
    --rate 10 --failure-rate 0.05 --duration 86400 > payment_24h.log 2>&1 &

for hour in {1..24}; do
    sleep 3600
    echo "=== Hora $hour ==="
    docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" \
        | grep -E "backend|redis|postgres|kafka"
done
```

**Critério:** O uso de memória do container `backend` deve estabilizar (não crescer linearmente).

---

## 📋 Script de Automação Final

O script `run_chao_tests.sh` (na raiz do projeto) automatiza todos os testes:

```bash
chmod +x run_chao_tests.sh
./run_chao_tests.sh
```

Ele executa na ordem:
1. Limpeza e setup (`make clean && make up-full`)
2. Fuzzing on-chain (5000 runs por contrato)
3. Carga extrema (50 agentes, 100 req/s, 60s)
4. Queda do Redis (fail-open)
5. Queda do PostgreSQL + reconciliação
6. Queda do Kafka (poison pill)
7. Concorrência (double-spend)
8. SQL injection
9. Payload gigante
10. Reconciliação final

Todos os logs são salvos em `logs_chao_YYYYMMDD_HHMMSS/`.

---

## 🎯 Recomendações Finais

1. **Antes da demonstração B2B:** Execute o script completo e salve todos os logs.
2. **Prepare um vídeo de 3 minutos** mostrando o Grafana sob carga e a reconciliação detectando discrepâncias.
3. **Inclua no pitch:** "Nosso sistema sobrevive à queda do banco de dados e ainda detecta automaticamente o que foi perdido."
4. **Se algum teste falhar:** Corrija antes da apresentação. As falhas mais comuns são:
   - Falta de `block.chainid` no domain separator
   - Falta de tratamento de exceção no consumer Kafka
   - Falta de `try/except` para Redis

---

## 📊 Relatório Executivo para Compradores

Após executar os testes, compile um relatório com:

1. **Resumo dos resultados** (tabela com status de cada fase)
2. **Evidências** (prints do Grafana, logs de reconciliação, saída do `forge test`)
3. **Métricas de performance** (latência p99, throughput, taxa de erro)
4. **Vulnerabilidades encontradas e corrigidas** (se houver)
5. **Recomendações** para produção (ex: aumentar limite de arquivos, configurar fail-open)

### Exemplo de tabela de resultados

| Fase | Status | Observação |
|------|--------|------------|
| 1 | ✅ PASS | p99 latência = 1.2s, 0 erros 5xx |
| 2 | ✅ PASS | 10.000 fuzz runs, 0 falhas |
| 3 | ✅ PASS | Reconciliação detectou 7 discrepâncias (esperado) |
| 4 | ✅ PASS | Rate limit bloqueou 34% das requisições |
| 5 | ✅ PASS | Consumer ignorou mensagem inválida e continuou |
| 6 | ✅ PASS | Fail-open com warning (Redis indisponível) |
| 7 | ✅ PASS | 100 conexões WebSocket aceitas |
| 8 | ✅ PASS | Payload rejeitado (422) |
| 9 | ✅ PASS | Payload rejeitado (413) |
| 10 | ✅ PASS | ReentrancyGuard presente, nonce antes de call |
| 11 | ✅ PASS | `block.chainid` no domain separator |
| 12 | ✅ PASS | Prometheus scrape continua |
| 13 | ⚠️  | Aguardando 24h (em andamento) |

### Proposta de valor para CTOs

| Problema do CTO | Nossa Solução (comprovada pelo script) |
|-----------------|----------------------------------------|
| "Meu sistema não escala com agentes simultâneos." | Teste de carga com 50 agentes a 100 req/s. |
| "Meus contratos podem ter vulnerabilidades." | Fuzzing com 5000 cenários aleatórios. |
| "Se o banco cair, perco dados." | Event Sourcing + reconciliação automática. |
| "Agentes podem gastar em double-spend." | Rate limiting atômico com Redis Lua. |
| "Kafka cai e perco mensagens." | Consumer resilient (Poison Pill testado). |

### Como usar na apresentação B2B

1. **Antes da reunião:** Execute `./run_chao_tests.sh` e salve o diretório `logs_chao_*`.
2. **Extraia as evidências:** Relatório de reconciliação, log do fuzzing com 0 falhas, print do Grafana sob carga.
3. **Monte um PDF de 3 páginas:**
   - Página 1: Resumo executivo (tabela de resultados)
   - Página 2: Evidências técnicas (prints dos logs)
   - Página 3: Arquitetura de resiliência (diagrama C4)
4. **Durante a reunião:** Mostre o script rodando ao vivo. Destaque: *"Nosso sistema sobrevive à queda do banco de dados e ainda detecta automaticamente o que foi perdido."*

---

**O Agent Platform está pronto para o mundo real.** 🚀
