# Performance Baseline — Agent Platform

> **Data:** 26/06/2026
> **Ambiente:** Local (Hardware: Windows 11, Intel i7, 32GB RAM)
> **Ferramenta:** Locust 2.40+

---

## 📊 Resultados do Teste de Carga

### Cenário 1: 20 usuários simultâneos, 2 minutos de duração

| Métrica | Valor | SLO | Status |
|---------|-------|-----|--------|
| **Throughput** | 15.77 req/s | — | ✅ OK |
| **p50 Latência** | 8 ms | < 200ms | ✅ OK |
| **p95 Latência** | 68 ms | < 500ms | ✅ OK |
| **p99 Latência** | 230 ms | < 1000ms | ✅ OK |
| **Taxa de Erro** | 0.00 % | < 1% | ✅ OK |

#### Por Endpoint

| Endpoint | p50 | p95 | p99 | Erro % |
|----------|-----|-----|-----|--------|
| `GET /health` | 7 ms | 46 ms | 150 ms | 0.00% |
| `POST /api/v1/consume` | 9 ms | 81 ms | 300 ms | 0.00% |
| `GET /api/v1/agents` | 15 ms | 92 ms | 290 ms | 0.00% |

### Cenário 2: 100 usuários simultâneos, 3 minutos de duração (Breakpoint)

| Métrica | Valor | SLO | Status |
|---------|-------|-----|--------|
| **Throughput** | 72.43 req/s | — | ✅ OK |
| **p50 Latência** | 17 ms | < 200ms | ✅ OK |
| **p95 Latência** | 850 ms | < 500ms | ❌ **ACIMA DO SLO** |
| **p99 Latência** | 1.5 s | < 1000ms | ❌ **ACIMA DO SLO** |
| **Taxa de Erro** | 0.00 % | < 1% | ✅ OK |

#### Por Endpoint

| Endpoint | p50 | p95 | p99 | Erro % |
|----------|-----|-----|-----|--------|
| `GET /health` | 13 ms | 710 ms | 1.3 s | 0.00% |
| `POST /api/v1/consume` | 17 ms | 1.0 s | 1.6 s | 0.00% |
| `GET /api/v1/agents` | 26 ms | 1.1 s | 1.5 s | 0.00% |

#### Análise do Breakpoint

- **Throughput escala linearmente**: 20u → 15.77 req/s, 100u → 72.43 req/s (~4.6x mais usuários = ~4.6x mais throughput)
- **Latência degrada sob carga**: p95 salta de 68ms (20u) para 850ms (100u) — indicativo de contenção em recursos compartilhados (DB pool, Redis, Gunicorn workers)
- **Zero falhas**: mesmo com 100 usuários, não houve erros HTTP — sistema resiliente
- **Gargalo identificado**: p95 > 500ms sugere que workers Gunicorn (4 atuais) podem estar saturados. Recomendação: aumentar workers ou escalar horizontalmente

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

| Data | Versão | Cenário | Throughput | p95 | Erro % | Observações |
|------|--------|---------|-----------|-----|--------|-------------|
| 26/06/2026 | v1.0.0 | 20 usuários / 2 min | 15.77 req/s | 68 ms | 0.00% | Primeiro baseline — smoke test |
| 26/06/2026 | v1.0.0 | 100 usuários / 3 min | 72.43 req/s | 850 ms | 0.00% | Breakpoint — p95 acima do SLO (500ms) |

---

## 🐛 Problemas Conhecidos

| Problema | Impacto | Status |
|----------|---------|--------|
| — | — | — |
