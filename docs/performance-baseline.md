# Performance Baseline — Agent Platform

> **Data:** 26/06/2026
> **Ambiente:** Local (Hardware: Windows 11, Intel i7, 32GB RAM)
> **Ferramenta:** Locust 2.40+

---

## 📊 Resultados do Teste de Carga

### Cenário: 20 usuários simultâneos, 2 minutos de duração

| Métrica | Valor | SLO | Status |
|---------|-------|-----|--------|
| **Throughput** | 15.77 req/s | — | ✅ OK |
| **p50 Latência** | 8 ms | < 200ms | ✅ OK |
| **p95 Latência** | 68 ms | < 500ms | ✅ OK |
| **p99 Latência** | 230 ms | < 1000ms | ✅ OK |
| **Taxa de Erro** | 0.00 % | < 1% | ✅ OK |

### Por Endpoint

| Endpoint | p50 | p95 | p99 | Erro % |
|----------|-----|-----|-----|--------|
| `GET /health` | 7 ms | 46 ms | 150 ms | 0.00% |
| `POST /api/v1/consume` | 9 ms | 81 ms | 300 ms | 0.00% |
| `GET /api/v1/agents` | 15 ms | 92 ms | 290 ms | 0.00% |

---

## 🚀 Como Reproduzir

```bash
# 1. Subir infraestrutura
docker compose up -d

# 2. Aguardar healthcheck
docker compose ps

# 3. Instalar Locust
pip install locust

# 4. Executar teste
locust -f scripts/load-test/smoke_test.py \
  --host http://localhost:8000 \
  --headless -u 20 -r 5 --run-time 2m \
  --csv scripts/load-test/results/smoke_test
```

---

## 📈 Histórico de Baselines

| Data | Versão | Throughput | p95 | Erro % | Observações |
|------|--------|-----------|-----|--------|-------------|
| 26/06/2026 | v1.0.0 | 15.77 req/s | 68 ms | 0.00% | Primeiro baseline — smoke test (20 usuários, 2 min) |

---

## 🐛 Problemas Conhecidos

| Problema | Impacto | Status |
|----------|---------|--------|
| — | — | — |
