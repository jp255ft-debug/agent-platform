# Agent Platform 🤖⛓️

**A production-hardened backend infrastructure for autonomous AI agents with x402 micropayments, EIP-7702 delegation, and on-chain reputation.**

[![CI](https://github.com/jp255ft-debug/agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jp255ft-debug/agent-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![Kafka](https://img.shields.io/badge/Kafka-3.5-black.svg)](https://kafka.apache.org/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8+-blueviolet.svg)](https://soliditylang.org/)
[![Spec Compliance](https://img.shields.io/badge/Spec-100%25-brightgreen)](docs/adr/)

---

## 🔑 Keywords

`x402` `EIP-7702` `Event Sourcing` `CQRS` `Agent Platform` `State Channels` `Reconciliation` `FastAPI` `PostgreSQL` `Redis` `Kafka` `Solidity` `Foundry` `Base L2` `Soulbound Tokens` `Micropayments` `Autonomous Agents` `Blockchain` `Web3`

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Key Features](#-key-features)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Docker Commands](#-docker-commands)
- [Services](#-services)
- [API Endpoints](#-api-endpoints)
- [Kafka Topics](#-kafka-topics)
- [Smart Contracts](#-smart-contracts)
- [Development](#-development)
- [Reconciliation & Consistency](#-reconciliation--consistency)
- [Grafana Dashboards](#-grafana-dashboards)
- [Load Simulators](#-load-simulators)
- [Makefile Commands](#-makefile-commands)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

The **Agent Platform** is a production-ready backend infrastructure for autonomous agents that:

- **Consume compute resources** paying per-use via **x402** (on-chain micropayments)
- **Delegate authority** using **EIP-7702** (account delegation — adopted by Coinbase, now under Linux Foundation)
- **Build reputation** through **Soulbound Tokens (SBT)**
- **Operate on Base L2** (Ethereum Layer 2)

### Core Flow

```
1. Agent → POST /consume (with x402 proof)
2. Backend verifies payment on-chain
3. Creates billing session (Event Store)
4. Publishes event to Kafka
5. Agent receives session_id
```

### Why This Matters

The x402 protocol, donated by Coinbase to the **Linux Foundation** in April 2026, is now backed by **Google, Microsoft, Visa, Stripe, and Mastercard**. EIP-7702 is being actively integrated into Ethereum clients (Go-Ethereum already implements EIP-7702 pricing). This platform is built at the intersection of these two transformative standards.

---

## 🏗️ Architecture

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
│  │  ┌──────────────────────────────────────────────────┐    │    │
│  │  │         State Channels (off-chain scaling)       │    │    │
│  │  └──────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| **API** | FastAPI (Python) | REST + WebSocket |
| **Event Store** | PostgreSQL 15 + JSONB | Immutable event log |
| **Cache** | Redis 7 | Rate limiting, idempotency |
| **Stream** | Apache Kafka | Event distribution |
| **Analytics** | TimescaleDB | Time-series metrics |
| **Smart Contracts** | Solidity 0.8+ | On-chain verification |
| **Blockchain** | Base L2 (Sepolia) | Settlement layer |

---

## ✨ Key Features

### 🔒 Production Hardening
- **3 reconciliation scripts** ensuring off-chain/on-chain consistency (payments, delegations, state channels)
- **Rate limiting** with Redis Lua scripts (atomic operations)
- **Idempotency** guarantees for all payment operations
- **Health checks** for all services with Docker Compose
- **3 Grafana dashboards** for business, reconciliation, and performance monitoring

### 🤖 Multi-Agent Pipeline
- **Observe / Diagnose / Approve** operational boundary
- **SignalOS** connector-based architecture for signal resolution
- **Access Map** graph-based access/relationship layer
- **Event sourcing** with CQRS pattern (60+ PostgreSQL tables)

### ⛓️ Blockchain Integration
- **x402 micropayments** (Coinbase → Linux Foundation standard)
- **EIP-7702 delegation** (account abstraction)
- **Soulbound Tokens** for reputation
- **State channels** for off-chain scaling
- **EIP-712 typed signatures** for secure off-chain messages

### 📊 Observability
- **Prometheus** metrics export
- **Grafana** dashboards (pre-configured)
- **Kafka UI** for stream monitoring
- **Structured logging** with configurable levels

---

## 📋 Prerequisites

- **Docker** 24+ and **Docker Compose** v2+
- **Git**
- **Node.js** 18+ (for Solidity contracts with Foundry)
- **Python** 3.11+ (for local backend development)

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/jp255ft-debug/agent-platform.git
cd agent-platform

# 2. Configure environment variables
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 3. Start all services
docker compose up -d

# 4. Verify everything is healthy
docker compose ps
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0","services":{"database":"healthy","redis":"healthy"}}
```

---

## 🐳 Docker Commands

### Core Services

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Stop and remove volumes (destroys data)
docker compose down -v

# View logs for a specific service
docker compose logs -f backend
docker compose logs -f kafka

# Restart a service
docker compose restart backend
```

### Optional Services (Monitoring)

```bash
# Start with monitoring (Prometheus + Grafana + Kafka UI)
docker compose --profile full up -d

# Access interfaces:
# - Grafana: http://localhost:3000 (admin/admin)
# - Kafka UI: http://localhost:8080
# - Prometheus: http://localhost:9090
```

### Healthchecks

```bash
# Check all service status
docker compose ps

# Wait for service to become healthy
docker compose wait postgres
docker compose wait kafka
```

---

## 📦 Services

| Service | Container | Port | Healthcheck |
|---------|-----------|------|-------------|
| **PostgreSQL** | `agent-postgres` | `5432` | `pg_isready` |
| **Redis** | `agent-redis` | `6379` | `redis-cli ping` |
| **Zookeeper** | `agent-zookeeper` | `2181` | — |
| **Kafka** | `agent-kafka` | `9092` | `kafka-topics --list` |
| **Backend** | `agent-backend` | `8000` | `GET /health` |
| **TimescaleDB** ⚡ | `agent-timescaledb` | `5433` | `pg_isready` |
| **Prometheus** ⚡ | `agent-prometheus` | `9090` | — |
| **Grafana** ⚡ | `agent-grafana` | `3000` | — |
| **Kafka UI** ⚡ | `agent-kafka-ui` | `8080` | — |

> ⚡ = Requires `--profile full`

---

## 🌐 API Endpoints

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

## 📨 Kafka Topics

Topics are auto-created on startup:

| Topic | Partitions | Description |
|-------|-----------|-------------|
| `agent.registered` | 3 | New agent registered |
| `agent.delegated` | 3 | Agent delegation |
| `agent.reputation` | 3 | Reputation update |
| `billing.resource.consumed` | 3 | Resource consumed |
| `billing.session.settled` | 3 | Billing session finalized |
| `billing.invoice.generated` | 3 | Invoice generated |
| `billing.invoice.paid` | 3 | Invoice paid |
| `payment.verified` | 3 | Payment verified on-chain |

---

## 📜 Smart Contracts

Contracts are in `contracts/src/` and use **Foundry**:

| Contract | Description | Standard |
|----------|-------------|----------|
| `AgentDelegation.sol` | Agent delegation via EIP-7702 | EIP-7702 |
| `PaymentVerifier.sol` | x402 payment verification | x402 |
| `ReputationSBT.sol` | Reputation system with SBT | ERC-721 |
| `StateChannelLib.sol` | Off-chain state channel library | Custom |

### Foundry Commands

```bash
# Compile contracts
cd contracts
forge build

# Run tests (91+ tests passing)
forge test

# Deploy to Base Sepolia
forge script script/Deploy.s.sol --rpc-url https://sepolia.base.org --broadcast
```

---

## 💻 Development

### Backend Local (without Docker)

```bash
# Create virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

**Key variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka server |
| `WEB3_PROVIDER_URL` | `https://sepolia.base.org` | Blockchain RPC |
| `JWT_SECRET` | `change-me...` | JWT secret key |

---

## 🔄 Reconciliation & Consistency

The system implements **three reconciliation scripts** to ensure off-chain (PostgreSQL) events align with the blockchain:

| Type | Script | Description |
|------|--------|-------------|
| **Payments** | `reconcile_payments.py` | Compares Event Store invoices with on-chain x402 transactions |
| **Delegations** | `reconcile_delegations.py` | Verifies EIP-7702 delegation consistency |
| **State Channels** | `reconcile_state_channels.py` | Checks channel openings, updates, and closures |

### Run reconciliation manually

```bash
make reconcile
```

### Schedule via cron (production)

```cron
0 2 * * * cd /path/to/agent-platform && make reconcile >> /var/log/reconcile.log 2>&1
```

Reports generated in `reconciliation_reports/` (JSON and CSV).

---

## 📊 Grafana Dashboards

Three pre-configured dashboards in `monitoring/grafana/dashboards/`:

| Dashboard | Description |
|-----------|-------------|
| `agent-platform-overview.json` | Business metrics: requests, revenue, active agents |
| `agent-platform-reconciliation.json` | Discrepancy monitoring and alerts |
| `agent-platform-performance.json` | System performance (Redis, PostgreSQL, Kafka) |

**Auto-import via Docker Compose (profile `full`):**

```bash
docker compose --profile full up -d
# Access http://localhost:3000 (admin/admin)
```

---

## 🧪 Load Simulators

Use simulators to generate synthetic traffic and validate the system:

```bash
# Simulate agents consuming resources (billing)
make simulate-billing

# Simulate EIP-7702 delegations
make simulate-delegations

# Simulate on-chain payments (x402)
make simulate-payments

# Run all simulators in parallel
make simulate-all
```

Simulators log to `logs/simulator/` and can be configured via environment variables (e.g., `SIMULATOR_RATE`, `SIMULATOR_DURATION`).

---

## 🛠️ Makefile Commands

| Command | Description |
|---------|-------------|
| `make up` | Start core services (postgres, redis, kafka, backend) |
| `make up-full` | Start all services + dashboards (Grafana, Prometheus) |
| `make down` | Stop all services |
| `make test` | Run Python, Solidity, and Lua tests |
| `make test-backend` | Run pytest only |
| `make test-contracts` | Run forge test only |
| `make reconcile` | Run all three reconciliation scripts |
| `make simulate-all` | Run all three simulators |
| `make migrate` | Apply Alembic migrations |
| `make logs` | View real-time logs |
| `make clean` | Remove containers, volumes, and cache |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `ARCHITECTURE.md` | Detailed architecture (C4) |
| `docs/adr/` | Architecture Decision Records |
| `docs/domain-models/` | Domain models |
| `docs/diagrams/` | C4 and sequence diagrams |
| `docs/api/` | API documentation |
| `docs/reconciliation/procedures.md` | Reconciliation runbook |
| `docs/capacity-planning/` | Capacity planning docs |
| `.ai/CLAUDE.md` | AI planning rules |
| `.ai/AGENTS.md` | AI coding rules |

---

## 🤝 Contributing

1. Fork the project
2. Create a branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🌐 Other Languages

- [Português (Brasil)](README.pt-BR.md)
