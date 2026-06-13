# Agent Platform 🤖⛓️

**Plataforma descentralizada para agentes autônomos com pagamento por consumo (x402), delegação EIP-7702 e reputação on-chain.**

[![CI](https://github.com/your-org/agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/agent-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![Kafka](https://img.shields.io/badge/Kafka-3.5-black.svg)](https://kafka.apache.org/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8+-blueviolet.svg)](https://soliditylang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Pré-requisitos](#-pré-requisitos)
- [Setup Rápido](#-setup-rápido)
- [Comandos Docker](#-comandos-docker)
- [Serviços](#-serviços)
- [Endpoints da API](#-endpoints-da-api)
- [Tópicos Kafka](#-tópicos-kafka)
- [Smart Contracts](#-smart-contracts)
- [Desenvolvimento](#-desenvolvimento)
- [Troubleshooting](#-troubleshooting)
- [Documentação](#-documentação)

---

## 🎯 Visão Geral

O **Agent Platform** é uma infraestrutura backend para agentes autônomos que:

- **Consomem recursos computacionais** pagando por uso via **x402** (micro-pagamentos on-chain)
- **Delegam autoridade** usando **EIP-7702** (delegação de conta)
- **Acumulam reputação** através de **Soulbound Tokens (SBT)**
- **Operam em Base L2** (Ethereum Layer 2)

### Fluxo Principal

```
1. Agente → POST /consume (com proof x402)
2. Backend verifica pagamento on-chain
3. Cria sessão de billing (Event Store)
4. Publica evento no Kafka
5. Agente recebe session_id
```

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Platform System                        │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │  Agents   │───▶│   Backend    │───▶│  Event Store     │       │
│  │ (EOAs)    │    │  (FastAPI)   │    │  (PostgreSQL)    │       │
│  └──────────┘    └──────┬───────┘    └──────────────────┘       │
│                         │                                        │
│                  ┌──────▼───────┐    ┌──────────────────┐       │
│                  │    Redis     │    │     Kafka        │       │
│                  │ (Cache/RL)   │    │ (Event Stream)   │       │
│                  └──────────────┘    └────────┬─────────┘       │
│                                               │                  │
│                  ┌────────────────────────────▼──────────┐       │
│                  │         TimescaleDB                    │       │
│                  │       (Analytics)                      │       │
│                  └───────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Blockchain (Base L2)                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │    │
│  │  │AgentDelegation│  │PaymentVerifier│  │ReputationSBT │   │    │
│  │  │  (EIP-7702)   │  │   (x402)     │  │   (ERC-721)  │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Stack Tecnológica

| Componente | Tecnologia | Função |
|-----------|-----------|--------|
| **API** | FastAPI (Python) | REST + WebSocket |
| **Event Store** | PostgreSQL 15 + JSONB | Log de eventos imutável |
| **Cache** | Redis 7 | Rate limiting, idempotência |
| **Stream** | Apache Kafka | Distribuição de eventos |
| **Analytics** | TimescaleDB | Métricas time-series |
| **Smart Contracts** | Solidity 0.8+ | Verificação on-chain |
| **Blockchain** | Base L2 (Sepolia) | Camada de settlement |

---

## 📋 Pré-requisitos

- **Docker** 24+ e **Docker Compose** v2+
- **Git**
- **Node.js** 18+ (para contratos Solidity com Foundry)
- **Python** 3.11+ (para desenvolvimento backend local)

---

## 🚀 Setup Rápido

```bash
# 1. Clone o repositório
git clone https://github.com/your-org/agent-platform.git
cd agent-platform

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env se necessário (valores padrão funcionam para dev local)

# 3. Inicie todos os serviços
docker compose up -d

# 4. Verifique se tudo está saudável
docker compose ps
curl http://localhost:8000/health

# Resposta esperada:
# {"status":"healthy","version":"0.1.0","services":{"database":"healthy","redis":"healthy"}}
```

---

## 🐳 Comandos Docker

### Serviços Principais

```bash
# Iniciar todos os serviços
docker compose up -d

# Parar todos os serviços
docker compose down

# Parar e remover volumes (destrói dados)
docker compose down -v

# Ver logs de um serviço específico
docker compose logs -f backend
docker compose logs -f kafka

# Reiniciar um serviço
docker compose restart backend
```

### Serviços Opcionais (Monitoramento)

```bash
# Iniciar com monitoramento (Prometheus + Grafana + Kafka UI)
docker compose --profile full up -d

# Acessar interfaces:
# - Grafana: http://localhost:3000 (admin/admin)
# - Kafka UI: http://localhost:8080
# - Prometheus: http://localhost:9090
```

### Healthchecks

```bash
# Verificar status de todos os serviços
docker compose ps

# Aguardar serviço ficar saudável
docker compose wait postgres
docker compose wait kafka
```

---

## 📦 Serviços

| Serviço | Container | Porta | Healthcheck |
|---------|-----------|-------|-------------|
| **PostgreSQL** | `agent-postgres` | `5432` | `pg_isready` |
| **Redis** | `agent-redis` | `6379` | `redis-cli ping` |
| **Zookeeper** | `agent-zookeeper` | `2181` | — |
| **Kafka** | `agent-kafka` | `9092` | `kafka-topics --list` |
| **Backend** | `agent-backend` | `8000` | `GET /health` |
| **TimescaleDB** ⚡ | `agent-timescaledb` | `5433` | `pg_isready` |
| **Prometheus** ⚡ | `agent-prometheus` | `9090` | — |
| **Grafana** ⚡ | `agent-grafana` | `3000` | — |
| **Kafka UI** ⚡ | `agent-kafka-ui` | `8080` | — |

> ⚡ = Requer `--profile full`

---

## 🌐 Endpoints da API

### Health Check

```bash
GET /health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### Agents

```bash
POST /api/v1/agents/register
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x..."
}
```

```bash
POST /api/v1/agents/delegate
Content-Type: application/json

{
  "agent": "0x...",
  "delegate": "0x...",
  "signature": "0x..."
}
```

### Consumption (x402)

```bash
POST /api/v1/consume
Content-Type: application/json

{
  "agent_address": "0x...",
  "resource_type": "compute",
  "units": 10,
  "tx_hash": "0x...",
  "amount": "1000000000000000"
}
```

### Billing

```bash
GET /api/v1/invoices/{agent_address}
GET /api/v1/invoices/{agent_address}/pending
```

---

## 📨 Tópicos Kafka

Os seguintes tópicos são criados automaticamente na inicialização:

| Tópico | Partições | Descrição |
|--------|-----------|-----------|
| `agent.registered` | 3 | Novo agente registrado |
| `agent.delegated` | 3 | Delegação de agente |
| `agent.reputation` | 3 | Atualização de reputação |
| `billing.resource.consumed` | 3 | Recurso consumido |
| `billing.session.settled` | 3 | Sessão de billing finalizada |
| `billing.invoice.generated` | 3 | Fatura gerada |
| `billing.invoice.paid` | 3 | Fatura paga |
| `payment.verified` | 3 | Pagamento verificado on-chain |

---

## 📜 Smart Contracts

Os contratos estão em `contracts/src/` e utilizam **Foundry**:

| Contrato | Descrição | Padrão |
|----------|-----------|--------|
| `AgentDelegation.sol` | Delegação de agentes via EIP-7702 | EIP-7702 |
| `PaymentVerifier.sol` | Verificação de pagamentos x402 | x402 |
| `ReputationSBT.sol` | Sistema de reputação com SBT | ERC-721 |

### Comandos Foundry

```bash
# Compilar contratos
cd contracts
forge build

# Rodar testes
forge test

# Deploy para Base Sepolia
forge script script/Deploy.s.sol --rpc-url https://sepolia.base.org --broadcast
```

---

## 💻 Desenvolvimento

### Backend Local (sem Docker)

```bash
# Criar virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Instalar dependências
cd backend
pip install -r requirements.txt

# Rodar migrations
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

### Variáveis de Ambiente

Copie `.env.example` para `.env` e ajuste conforme necessário:

```bash
cp .env.example .env
```

**Variáveis principais:**

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Conexão PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | Conexão Redis |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Servidor Kafka |
| `WEB3_PROVIDER_URL` | `https://sepolia.base.org` | RPC Blockchain |
| `JWT_SECRET` | `change-me...` | Chave secreta JWT |

---

## 🔧 Troubleshooting

### Kafka não fica healthy

```bash
# Verificar logs
docker compose logs kafka

# Problema comum: listeners na mesma porta
# Solução: PLAINTEXT (9092) e PLAINTEXT_HOST (9093) em portas diferentes
```

### Backend não inicia

```bash
# Verificar dependências
docker compose logs backend

# Certifique-se de que postgres, redis e kafka estão healthy
docker compose ps
```

### Portas ocupadas

```bash
# Verificar o que está usando a porta
netstat -ano | findstr :5432

# Mudar portas no .env
POSTGRES_PORT=5433
```

### Reset completo

```bash
# Parar tudo e remover volumes
docker compose down -v

# Reconstruir imagens
docker compose build --no-cache

# Iniciar novamente
docker compose up -d
```

---

## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| `ARCHITECTURE.md` | Arquitetura detalhada (C4) |
| `docs/adr/` | Decision Records |
| `docs/domain-models/` | Modelos de domínio |
| `docs/diagrams/` | Diagramas C4 e sequência |
| `docs/api/` | Documentação da API |
| `docs/reconciliation/procedures.md` | Runbook de reconciliação |
| `.ai/CLAUDE.md` | Regras de planejamento para AI |
| `.ai/AGENTS.md` | Regras de codificação para AI |

---

## 🔄 Reconciliação e Consistência

O sistema implementa **três tipos de reconciliação** para garantir que eventos off‑chain (PostgreSQL) estejam alinhados com a blockchain:

| Tipo | Script | Descrição |
|------|--------|-----------|
| **Pagamentos** | `reconcile_payments.py` | Compara faturas no Event Store com transações on‑chain (x402) |
| **Delegações** | `reconcile_delegations.py` | Verifica consistência de delegações EIP‑7702 |
| **State Channels** | `reconcile_state_channels.py` | Confere aberturas, atualizações e fechamentos de canais |

### Executar reconciliação manual

```bash
make reconcile
```

### Agendar no cron (produção)

```cron
0 2 * * * cd /path/to/agent-platform && make reconcile >> /var/log/reconcile.log 2>&1
```

Relatórios gerados em `reconciliation_reports/` (JSON e CSV).

---

## 📊 Dashboards Grafana

Três dashboards prontos para uso, localizados em `monitoring/grafana/dashboards/`:

| Dashboard | Descrição |
|-----------|-----------|
| `agent-platform-overview.json` | Métricas de negócio: requisições, receita, agentes ativos |
| `agent-platform-reconciliation.json` | Monitoramento de discrepâncias e alertas |
| `agent-platform-performance.json` | Performance do sistema (Redis, PostgreSQL, Kafka) |

**Importar automaticamente via Docker Compose (profile `full`):**

```bash
docker compose --profile full up -d
# Acesse http://localhost:3000 (admin/admin)
```

---

## 🧪 Simuladores de Carga e Teste

Utilize os simuladores para gerar tráfego sintético e validar o sistema:

```bash
# Simular agentes consumindo recursos (billing)
make simulate-billing

# Simular delegações EIP-7702
make simulate-delegations

# Simular pagamentos on-chain (x402)
make simulate-payments

# Executar todos os simuladores em paralelo
make simulate-all
```

Os simuladores registram logs em `logs/simulator/` e podem ser configurados via variáveis de ambiente (ex: `SIMULATOR_RATE`, `SIMULATOR_DURATION`).

---

## 🛠️ Makefile – Comandos Rápidos

| Comando | Descrição |
|---------|-----------|
| `make up` | Iniciar serviços essenciais (postgres, redis, kafka, backend) |
| `make up-full` | Iniciar todos os serviços + dashboards (Grafana, Prometheus) |
| `make down` | Parar todos os serviços |
| `make test` | Executar testes Python, Solidity e Lua |
| `make test-backend` | Apenas pytest |
| `make test-contracts` | Apenas forge test |
| `make reconcile` | Rodar os três scripts de reconciliação |
| `make simulate-all` | Executar os três simuladores |
| `make migrate` | Aplicar migrações Alembic |
| `make logs` | Ver logs em tempo real |
| `make clean` | Remover containers, volumes e cache |

---

## ✅ Badges de Status

[![CI](https://github.com/your-org/agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/agent-platform/actions/workflows/ci.yml)
[![Solidity Tests](https://img.shields.io/badge/Solidity-91%20tests%20passing-brightgreen)](contracts/)
[![Python Coverage](https://img.shields.io/badge/Coverage-85%25-brightgreen)](backend/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Spec Compliance](https://img.shields.io/badge/Spec-100%25-brightgreen)](docs/adr/)

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/amazing-feature`)
3. Commit suas mudanças (`git commit -m 'feat: add amazing feature'`)
4. Push para a branch (`git push origin feature/amazing-feature`)
5. Abra um Pull Request

---

## 📄 Licença

MIT License — veja o arquivo [LICENSE](LICENSE) para detalhes.
