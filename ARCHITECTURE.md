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
│  │  │ - Provider│  │ - Provider│ │                │   │    │
│  │  │ - API Key│  │ - API Key│  │                │   │    │
│  │  └──────────┘  └──────────┘  └────────────────┘   │    │
│  └────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```


## 🏭 DePIN Procurement Domain

### ProviderAggregate (Event Sourced)

O `ProviderAggregate` gerencia o ciclo de vida completo de um provedor DePIN:

```
┌─────────────────────────────────────────────────────────────┐
│                    ProviderAggregate                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  State Machine                       │    │
│  │                                                      │    │
│  │    PENDING ──(stake ≥ 10 USDC)──▶ ACTIVE            │    │
│  │       │                              │              │    │
│  │       │                              ├──▶ SUSPENDED │    │
│  │       │                              │   (health)   │    │
│  │       │                              │              │    │
│  │       │                              ├──▶ SLASHED   │    │
│  │       │                              │   (penalty)  │    │
│  │       │                              │              │    │
│  │       │                              └──▶ INACTIVE  │    │
│  │       │                                  (unstake)  │    │
│  │       └─────────────────────────────────────────────┘    │
│  │                                                          │
│  │  GPUSpecs { model, vram_gb, tflops_fp16, price_per_hour }│
│  │  Stake: uint256 (micro USDC)                             │
│  │  Reputation: uint8 (0-100)                               │
│  │  TotalUptime: uint256 (seconds)                          │
│  └──────────────────────────────────────────────────────────┘
```

### Eventos do Provedor

| Evento | Gatilho | Efeito |
|--------|---------|--------|
| `ProviderRegistered` | Registro do nó | Cria agregado em PENDING |
| `ProviderStaked` | Stake ≥ 10 USDC | Transição para ACTIVE |
| `ProviderStatusChanged` | Health check / admin | ACTIVE ↔ SUSPENDED |
| `HealthReported` | Telemetria periódica | Atualiza uptime |
| `GPUSpecsUpdated` | Upgrade de hardware | Atualiza specs |
| `SlashingApplied` | Violação de SLA | Penaliza stake + reputação |
| `ProviderUnstaked` | Saída voluntária | Transição para INACTIVE |
| `ProviderJobCompleted` | Fim de sessão GPU | Registra job |

---

## 🔄 Data Flow

### DePIN Procurement Flow (GPU Lease)
```
Autonomous Agent          Backend              ProviderAggregate       Blockchain
      │                      │                       │                    │
      │  POST /consume       │                       │                    │
      │  (x402 proof)        │                       │                    │
      │─────────────────────▶│                       │                    │
      │                      │  Verify provider      │                    │
      │                      │  is ACTIVE + staked   │                    │
      │                      │──────────────────────▶│                    │
      │                      │  Check GPU specs      │                    │
      │                      │◀──────────────────────│                    │
      │                      │                       │                    │
      │                      │  Verify x402 payment  │                    │
      │                      │───────────────────────────────────────────▶│
      │                      │                       │                    │
      │                      │  Create BillingSession│                    │
      │                      │  (ResourceConsumedV2) │                    │
      │                      │                       │                    │
      │                      │  Publish → Kafka      │                    │
      │                      │  (billing.resource    │                    │
      │                      │   .consumed.v2)       │                    │
      │                      │                       │                    │
      │                      │  Payment Simulator    │                    │
      │                      │  verifica crédito     │                    │
      │                      │  vs orçamento delegado│                    │
      │                      │                       │                    │
      │  ┌── within budget ──┤  Emite State Channel  │                    │
      │  │                   │  Proof                │                    │
      │  │  200 OK           │                       │                    │
      │  │◀──────────────────│                       │                    │
      │  │                   │                       │                    │
      │  └── over budget ────┤  KILL-SWITCH          │                    │
      │                      │  Desconecta nó GPU    │                    │
      │                      │  (ProviderJobCompleted│                    │
      │                      │   with success=false) │                    │
      │                      │──────────────────────▶│                    │
```

### Resource Consumption Flow (Legacy V1)

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
