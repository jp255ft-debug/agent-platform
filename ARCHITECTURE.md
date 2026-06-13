# Agent Platform — Architecture Overview

## 🏗️ System Context (C4 Level 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Platform System                        │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │  Agents   │───▶│   Backend    │───▶│  Event Store     │       │
│  │ (EOAs)    │    │  (FastAPI)   │    │  (PostgreSQL)    │       │
│  └──────────┘    └──────┬───────┘    └──────────────────┘       │
│                         │                                        │
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

## 🧱 Container Architecture (C4 Level 2)

### Backend (FastAPI)
```
┌────────────────────────────────────────────────────────────┐
│                    Backend Container                        │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  API Layer   │  │ Application  │  │ Infrastructure│     │
│  │  (REST/WS)   │──▶│   Layer     │──▶│    Layer     │     │
│  │              │  │ (Commands)   │  │ (DB, Redis,   │     │
│  │  - Endpoints │  │              │  │  Kafka, Web3) │     │
│  │  - Schemas   │  │ - Handlers  │  │              │     │
│  │  - Middleware │  │ - Services  │  │ - Event Store │     │
│  │  - WebSocket │  │ - Commands  │  │ - Cache      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Domain Layer                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐   │    │
│  │  │Aggregates│  │  Events  │  │  Repositories  │   │    │
│  │  │ - Agent  │  │ - Agent  │  │  (Protocols)   │   │    │
│  │  │ - Billing│  │ - Billing│  │                │   │    │
│  │  │ - Invoice│  │ - Payment│  │                │   │    │
│  │  └──────────┘  └──────────┘  └────────────────┘   │    │
│  └────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow

### Resource Consumption Flow
```
Agent                    Backend                    Blockchain
  │                        │                          │
  │  POST /consume         │                          │
  │  (x402 proof)          │                          │
  │───────────────────────▶│                          │
  │                        │  Verify idempotency      │
  │                        │  (Redis)                 │
  │                        │                          │
  │                        │  Check rate limit        │
  │                        │  (Redis Token Bucket)    │
  │                        │                          │
  │                        │  Verify payment          │
  │                        │─────────────────────────▶│
  │                        │  Verify tx receipt       │
  │                        │◀─────────────────────────│
  │                        │                          │
  │                        │  Create billing session  │
  │                        │  (Event Store)           │
  │                        │                          │
  │                        │  Publish event (Kafka)   │
  │                        │                          │
  │  200 OK (session_id)   │                          │
  │◀───────────────────────│                          │
```

### Delegation Flow (EIP-7702)
```
Agent                    Backend                 AgentDelegation
  │                        │                          │
  │  POST /delegate        │                          │
  │  (EIP-712 signature)   │                          │
  │───────────────────────▶│                          │
  │                        │  Verify signature        │
  │                        │  (off-chain)            │
  │                        │                          │
  │                        │  setDelegation()         │
  │                        │─────────────────────────▶│
  │                        │                          │
  │                        │  Store event             │
  │                        │  (Event Store)           │
  │                        │                          │
  │  200 OK                │                          │
  │◀───────────────────────│                          │
```

## 📊 Key Metrics

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Event Store | PostgreSQL 15 + JSONB | Immutable event log |
| Cache | Redis 7 | Rate limiting, idempotency, sessions |
| Stream | Kafka | Event distribution |
| Analytics | TimescaleDB | Time-series metrics |
| Smart Contracts | Solidity 0.8+ | On-chain verification |
| API | FastAPI (Python) | REST + WebSocket |

## 🔐 Security Boundaries

1. **API Gateway**: Rate limiting, signature verification
2. **Application Layer**: Input validation, idempotency
3. **Blockchain Layer**: On-chain verification, EIP-712 signatures
4. **Database Layer**: Encrypted connections, parameterized queries

## 📚 Related Documents

- `docs/adr/` — Architecture Decision Records
- `docs/domain-models/` — Domain model documentation
- `docs/diagrams/` — C4 and sequence diagrams
- `.ai/CLAUDE.md` — AI agent planning rules
- `.ai/AGENTS.md` — AI agent coding rules
