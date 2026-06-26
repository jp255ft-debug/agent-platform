# Agent Platform — Technical White Paper

## Autonomous DePIN Resource Allocation with Zero-Risk Settlement

**Version**: 0.2.0  
**Date**: June 2026  
**Status**: Draft — Pre-Mainnet

---

## Abstract

The Agent Platform is a **production-grade infrastructure for Autonomous DePIN Resource Allocation**. It enables AI agents to procure GPU compute from decentralized physical infrastructure networks (DePIN) with **zero-risk settlement** — combining x402 micropayments, EIP-7702 delegation, real-time GPU telemetry, and a cryptographic kill-switch that prevents bad debt before it accrues.

The platform solves three fundamental problems for the emerging **Machine-to-Machine (M2M) economy**:

1. **Procurement**: How do autonomous agents discover, lease, and pay for GPU compute from DePIN providers (io.net, Render, Akash) without human intervention?
2. **Risk**: How do we prevent agents from exceeding delegated budgets, creating bad debt for providers?
3. **Verification**: How do we prove computational work was performed and settle payments with cryptographic finality?

Our solution combines **real-time GPU telemetry** (gRPC streaming from provider nodes), **state channel proofs** (off-chain payment verification with on-chain settlement), and a **zero-risk kill-switch** (automatic provider disconnect when budget is exceeded) to create a trust-minimized marketplace for autonomous compute procurement.

---

## 1. Introduction

### 1.1 The Problem

The convergence of AI agents and decentralized compute has created a new economic paradigm: **autonomous agents that need to buy GPU time from decentralized providers**. This market is projected to exceed $50B by 2030, yet the infrastructure for M2M settlement is fundamentally broken:

| Problem | Impact | Current Solutions |
|---------|--------|-------------------|
| **Credit Risk** | Agents can overspend delegated budgets, leaving providers unpaid | Manual caps, no real-time enforcement |
| **Verification** | No proof that GPU work was actually performed | Trust-based, no cryptographic receipts |
| **Latency** | On-chain settlement per compute tick is economically infeasible | $0.50 gas per $0.001 transaction |
| **Discovery** | No standardized way for agents to find and negotiate with providers | Fragmented APIs, no unified marketplace |

### 1.2 The Solution

The Agent Platform provides:

| Capability | Technology | Standard |
|------------|------------|----------|
| GPU compute procurement | gRPC telemetry + Kafka event streaming | Custom protobuf |
| Agent-to-provider payments | x402 micropayments with state channels | EIP-712 |
| Agent-to-agent delegation | EIP-7702 delegation | EIP-7702 |
| Zero-risk budget enforcement | Cryptographic kill-switch | Custom |
| Compute verification | GPU telemetry + TFLOPS attestation | Custom |
| Financial consistency | Triple reconciliation (payments, delegations, state channels) | Custom |

### 1.3 Market Context

- **DePIN Market**: $32B total market cap (June 2026). io.net, Render Network, and Akash Network processing 500K+ GPU hours/month.
- **AI Agent Economy**: AI agents now generate 28.4% of DEX volume. Projected to exceed 80% by 2030.
- **x402 Protocol**: Processed 100M+ payments between APIs and AI agents by late 2025.
- **EIP-7702**: Entered production May 7, 2025. Enables EOAs to delegate execution to smart contracts temporarily.
- **Brazilian Banking**: Institutions like Liqi, BTG, and Itaú are actively exploring tokenization with AI agents. Drex (CBDC) integration is the next frontier.

---

## 2. Architecture

### 2.1 System Overview (C4 Level 1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent Platform — DePIN Procurement System                │
│                                                                              │
│  ┌──────────────────┐    ┌──────────────┐    ┌──────────────────────┐       │
│  │  DePIN Providers  │───▶│  Node Service │───▶│     Kafka            │       │
│  │  (io.net, Render, │    │  (gRPC)      │    │  depin.provider.health│       │
│  │   Akash, Custom)  │    │  GPU Telemetry│    │  depin.provider.status│       │
│  └──────────────────┘    └──────────────┘    └──────────┬───────────┘       │
│                                                          │                    │
│  ┌──────────────────┐    ┌──────────────┐               │                    │
│  │  Autonomous Agents│───▶│   Backend    │◄──────────────┘                    │
│  │  (EIP-7702)      │    │  (FastAPI)   │───▶  Event Store (PostgreSQL)     │
│  └──────────────────┘    └──────┬───────┘    └──────────────────────┘       │
│                                 │                                            │
│                          ┌──────▼───────┐    ┌──────────────────────┐       │
│                          │    Redis     │    │   TimescaleDB         │       │
│                          │ (Cache/RL)   │    │ (Analytics/Telemetry) │       │
│                          └──────────────┘    └──────────────────────┘       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              Blockchain (Base L2)                                     │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │AgentDelegation   │  │PaymentVerifier   │  │ReputationSBT     │   │   │
│  │  │ (EIP-7702)       │  │ (x402 + State    │  │ (ERC-721)        │   │   │
│  │  │                  │  │  Channels)       │  │                  │   │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 DePIN Procurement Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Agent    │     │   Backend    │     │  DePIN Node   │     │  Blockchain  │
│  (EIP-7702)│     │  (FastAPI)   │     │  (GPU Provider)│     │  (Base L2)   │
└─────┬────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
      │                  │                    │                    │
      │  1. Register     │                    │                    │
      │─────────────────▶│                    │                    │
      │                  │                    │                    │
      │  2. Delegate     │                    │                    │
      │  (EIP-7702)      │─────────────────────────────────────────▶
      │◀─────────────────│                    │                    │
      │                  │                    │                    │
      │  3. Request GPU  │                    │                    │
      │─────────────────▶│                    │                    │
      │                  │  4. Allocate Node  │                    │
      │                  │───────────────────▶│                    │
      │                  │                    │                    │
      │                  │  5. GPU Lease Start│                    │
      │                  │◀───────────────────│                    │
      │◀─────────────────│                    │                    │
      │                  │                    │                    │
      │  ════════════════════════════════════════════════════════════  │
      │  ║              GPU Compute Session (State Channel)      ║  │
      │  ║                                                        ║  │
      │                  │  6. GPU Telemetry Stream                │
      │                  │◀────────────────────────────────────────│
      │                  │  (gRPC: utilization, temp, power,       │
      │                  │   TFLOPS, memory, jobs)                 │
      │                  │                    │                    │
      │                  │  7. Billing Tick   │                    │
      │                  │  (cost = p_gpu *   │                    │
      │                  │   tflops * delta_t │                    │
      │                  │   + p_token * n)   │                    │
      │                  │                    │                    │
      │                  │  8. Credit Risk Check                   │
      │                  │  (accumulated vs delegated budget)      │
      │                  │                    │                    │
      │                  │  ┌─ Within Budget ──────────────────┐   │
      │                  │  │ 9a. State Channel Proof          │   │
      │                  │  │─────────────────────────────────────▶│
      │                  │  └──────────────────────────────────┘   │
      │                  │                    │                    │
      │                  │  ┌─ Budget Exceeded ────────────────┐   │
      │                  │  │ 9b. KILL-SWITCH TRIGGERED        │   │
      │                  │  │───────────────────▶              │   │
      │                  │  │ (Provider disconnects GPU node)  │   │
      │                  │  └──────────────────────────────────┘   │
      │  ║                                                        ║  │
      │  ════════════════════════════════════════════════════════════  │
      │                  │                    │                    │
      │  10. Session End │                    │                    │
      │◀─────────────────│                    │                    │
```

### 2.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Event Sourcing** | Immutable audit trail for all compute leases, payments, and kill-switch events |
| **CQRS** | Separate read/write paths — optimize billing queries without impacting event ingestion |
| **gRPC Streaming** | Real-time GPU telemetry from provider nodes with protobuf serialization |
| **Kafka Topics** | `depin.provider.health` for telemetry, `depin.provider.status` for state changes |
| **State Channels** | Off-chain payment aggregation with on-chain settlement — economically viable for micro-transactions |
| **Kill-Switch** | Cryptographic guarantee that agents cannot exceed delegated budgets |

---

## 3. Technical Implementation

### 3.1 Node Service (GPU Telemetry)

The **Node Service** is a TypeScript/gRPC microservice that runs on DePIN provider nodes:

```
node-service/
├── src/
│   ├── proto/telemetry.proto    # gRPC service definition
│   ├── server.ts                # gRPC server (port 50051)
│   ├── gpu_collector.ts         # NVML/systeminformation GPU metrics
│   ├── kafka_publisher.ts       # Kafka producer for telemetry
│   └── logger.ts                # Structured logging (winston)
├── test/
│   └── gpu_collector.test.ts    # Unit tests
├── Dockerfile                   # Multi-stage build
├── package.json
└── tsconfig.json
```

**GPU Telemetry Protobuf**:

```protobuf
service GPUTelemetry {
    rpc ReportGPUHealth(stream GPUHealthReport) returns (HealthAck);
    rpc GetGPUStatus(GPUStatusRequest) returns (GPUStatusResponse);
}

message GPUHealthReport {
    string provider_id = 1;
    string gpu_model = 2;
    double gpu_utilization = 3;
    double temperature_celsius = 4;
    double memory_used_gb = 5;
    double memory_total_gb = 6;
    double power_watts = 7;
    uint64 uptime_seconds = 8;
    uint64 timestamp = 9;
    double tflops_fp16 = 10;
    uint32 active_jobs = 11;
    string status = 12;
    map<string, string> labels = 13;
}
```

**Kafka Topics**:

| Topic | Schema | Description |
|-------|--------|-------------|
| `depin.provider.health` | GPUHealthReport JSON | Real-time GPU telemetry from provider nodes |
| `depin.provider.status` | StatusChange JSON | Provider status transitions (online/degraded/offline) |

### 3.2 Smart Contracts

#### PaymentVerifier.sol (x402 + State Channels)

```solidity
// Verifies x402 payments with EIP-712 typed signatures
// Supports state channel proof aggregation for DePIN billing

function verifyPayment(Payment calldata _payment) external returns (bool) {
    // 1. Validate inputs (amount > 0, recipient != 0, deadline not passed)
    // 2. Compute payment hash for replay protection
    // 3. Verify EIP-712 signature
    // 4. Mark as used, increment nonce
    // 5. Emit PaymentVerified event
}

function verifyStateChannelProof(
    bytes32 _channelId,
    uint256 _accumulatedAmount,
    bytes calldata _signature
) external returns (bool) {
    // 1. Verify channel exists and is open
    // 2. Verify accumulated amount <= delegated budget
    // 3. Verify agent signature on state channel proof
    // 4. Settle accumulated amount to provider
    // 5. Emit StateChannelSettled event
}
```

#### AgentDelegation.sol (EIP-7702)

```solidity
// Manages agent delegation with EIP-712 typed signatures
// Features: gasless delegation, expiration, budget limits

function delegateBySig(
    address _agent, address _delegate,
    uint256 _expiresAt, uint256 _maxBudget,
    bytes calldata _signature
) external {
    // 1. Verify nonce
    // 2. Compute EIP-712 digest
    // 3. Verify signature
    // 4. Create delegation with expiration and budget cap
    // 5. Emit DelegationCreated event
}
```

### 3.3 Zero-Risk Kill-Switch

The kill-switch is the platform's core risk management mechanism:

```python
async def verify_agent_credit_risk(agent_id: str, max_budget: float = 50.0):
    # Load projected spend from CQRS read model
    current_spend = await get_materialized_view_spend(agent_id)

    if current_spend >= max_budget:
        # ZERO-RISK TRIGGER: Delegated budget exceeded
        logger.error(f"🚨 BUDGET EXCEEDED: Agent {agent_id}")
        # Call provider API to disconnect GPU node
        await disconnect_gpu_node(agent_id)
        return False

    # Within budget → emit state channel proof
    await emit_state_channel_proof(agent_id, current_spend)
    return True
```

**Properties**:
- **Real-time**: Checked on every billing tick (configurable interval)
- **Cryptographic**: Kill-switch events are recorded on-chain
- **Provider-agnostic**: Works with any DePIN provider via standardized API
- **Auditable**: Every kill-switch event is stored in the Event Store

### 3.4 Backend (FastAPI)

**Stack**: Python 3.11+, FastAPI, SQLAlchemy (async), Redis, Kafka, Web3.py

**DePIN-specific API Endpoints**:

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/v1/agents/register` | Register new autonomous agent |
| `POST` | `/api/v1/agents/delegate` | Delegate authority with budget cap (EIP-7702) |
| `POST` | `/api/v1/agents/revoke` | Revoke delegation |
| `POST` | `/api/v1/consume` | Consume GPU compute (billing tick) |
| `GET` | `/api/v1/consume/sessions/{id}` | Get GPU lease session details |
| `GET` | `/api/v1/invoices/{address}` | Get invoice |
| `GET` | `/api/v1/providers` | List DePIN providers |
| `GET` | `/api/v1/providers/{id}/telemetry` | Get provider GPU telemetry |
| `WS` | `/ws` | Real-time event streaming |

**Consumption Flow (DePIN)**:

```
Agent → POST /consume → Redis (idempotency) → Redis (rate limit)
  → Redis (quota) → Credit Risk Check (kill-switch)
  → Blockchain (state channel proof) → Event Store
  → Kafka (billing.resource.consumed.v2) → Response
```

### 3.5 Reconciliation Layer

The platform implements **triple reconciliation** for DePIN procurement:

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `reconcile_payments.py` | Verify x402 payments match on-chain state | Hourly |
| `reconcile_delegations.py` | Verify EIP-7702 delegations are consistent | Hourly |
| `reconcile_state_channels.py` | Verify channel open/close states and accumulated spend | Hourly |

**DePIN-specific reconciliation checks**:
- GPU hours billed vs. telemetry-reported uptime
- Kill-switch events vs. provider disconnect logs
- State channel proofs vs. on-chain settlement

---

## 4. Security & Compliance

### 4.1 Smart Contract Security

- **EIP-712 Typed Signatures**: Prevents phishing and replay attacks
- **Nonce Management**: Sequential nonces prevent transaction reordering
- **Replay Protection**: `usedPayments` mapping prevents double-spending
- **Deadline Enforcement**: Payments expire after deadline
- **Budget Caps**: Delegated budgets prevent runaway spending
- **Kill-Switch**: Cryptographic guarantee of spend limits

### 4.2 Backend Security

- **Rate Limiting**: Token bucket algorithm via Redis Lua scripts
- **Idempotency**: Atomic check-and-set for duplicate request prevention
- **Input Validation**: Pydantic schemas with strict field validation
- **CORS**: Configurable allowed origins
- **WebSocket Authentication**: Connection validation

### 4.3 Audit Trail

Every state change is recorded as an immutable event in PostgreSQL:

```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    stream_id VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(stream_id, version)  -- Optimistic concurrency
);
```

This provides:
- Complete transaction history for every GPU lease
- Point-in-time state reconstruction for dispute resolution
- Regulatory compliance (audit trail for financial institutions)
- Kill-switch event forensics

---

## 5. Performance Metrics

*To be populated after mainnet benchmark (see BENCHMARK_PLAN.md)*

| Metric | Target | Measured |
|--------|--------|----------|
| GPU telemetry throughput | >1000 reports/s | TBD |
| Billing tick latency (P95) | <100ms | TBD |
| Kill-switch response time | <500ms | TBD |
| State channel settlement | <50k gas | TBD |
| Reconciliation time | <5 min | TBD |
| Event Store write | >500 events/s | TBD |

---

## 6. Use Cases

### 6.1 Autonomous AI Training on DePIN

AI agents that autonomously procure GPU compute for model training:
- Agent registers on platform with delegated budget (EIP-7702)
- Agent discovers available GPU nodes via provider registry
- Agent leases GPU time, pays per TFLOPS/hour via state channels
- Kill-switch prevents budget overruns
- All training sessions recorded in Event Store for audit

### 6.2 Decentralized Inference Networks

Autonomous agents running inference workloads across distributed GPU nodes:
- Real-time GPU telemetry ensures node reliability
- Dynamic pricing based on GPU utilization and demand
- Automatic failover when nodes go offline
- Zero-risk settlement protects both agents and providers

### 6.3 DePIN Provider Marketplace

A marketplace where DePIN providers compete for agent compute workloads:
- Providers register GPU specs and pricing
- Agents select providers based on price, reputation, and availability
- Automated billing and settlement via state channels
- Reputation system (Soulbound Tokens) tracks provider reliability

### 6.4 Brazilian Banking Integration (Drex)

Integration with Brazil's CBDC (Drex) for institutional DePIN procurement:
- Tokenized GPU compute on Drex-compatible network
- AI agents managing treasury operations for compute procurement
- Compliance with BACEN regulations
- Real-time reconciliation with Drex settlement

---

## 7. Roadmap

| Quarter | Milestone | Status |
|---------|-----------|--------|
| Q2 2026 | Testnet deployment (Base Sepolia) | ✅ Complete |
| Q2 2026 | Smart contract audit | 🔄 In progress |
| Q2 2026 | Node Service (GPU telemetry) MVP | ✅ Complete |
| Q3 2026 | Mainnet deployment (Base L2) | 📅 Planned |
| Q3 2026 | Public benchmark (100k GPU hours) | 📅 Planned |
| Q3 2026 | Pilot with DePIN provider (io.net) | 📅 Planned |
| Q4 2026 | EIP-8004 (Agent Cards) integration | 📅 Planned |
| Q4 2026 | EIP-8183 (Agent Commerce) integration | 📅 Planned |
| Q1 2027 | Drex / Real Digital integration | 📅 Planned |
| Q2 2027 | Multi-chain support (Solana, Polygon) | 📅 Planned |

---

## 8. Conclusion

The Agent Platform provides a **production-grade infrastructure for Autonomous DePIN Resource Allocation**. By combining real-time GPU telemetry, state channel proofs, and a cryptographic kill-switch, it enables AI agents to procure compute from decentralized providers with **zero-risk settlement**.

The architecture is **minimalist by design** — FastAPI, PostgreSQL, Redis, Kafka, gRPC — reducing operational complexity while maintaining enterprise-grade reliability. The triple reconciliation layer provides the financial consistency required by regulated institutions.

**Next step**: Mainnet deployment and public benchmark validation with DePIN providers.

---

## References

1. [x402 Protocol](https://x402.org) — Micropayments for AI agents
2. [EIP-7702](https://eips.ethereum.org/EIPS/eip-7702) — EOA Delegation
3. [EIP-712](https://eips.ethereum.org/EIPS/eip-712) — Typed structured data hashing and signing
4. [io.net](https://io.net) — Decentralized GPU network
5. [Render Network](https://rendertoken.com) — Decentralized GPU rendering
6. [Akash Network](https://akash.network) — Decentralized cloud marketplace
7. [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html) — Martin Fowler
8. [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html) — Martin Fowler
9. [Base L2](https://base.org) — Ethereum L2 by Coinbase
10. [DeFAI Market Report](https://example.com) — AI agents in DeFi (2026)

---

> **Document version**: 0.2.0  
> **Last updated**: June 2026  
> **Contact**: [project maintainers]
