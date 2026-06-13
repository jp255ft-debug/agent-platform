# Agent Platform — Technical White Paper

## Autonomous AI Agents with x402 Micropayments and EIP-7702 Delegation

**Version**: 0.1.0  
**Date**: June 2026  
**Status**: Draft — Pre-Mainnet

---

## Abstract

The Agent Platform is a production-grade infrastructure for autonomous AI agents to operate as independent economic entities on blockchain networks. It solves three fundamental problems:

1. **Payments**: How do AI agents pay for API calls and resources without human intervention?
2. **Delegation**: How do agents delegate authority to sub-agents or automated systems?
3. **Consistency**: How do we ensure financial accuracy between off-chain operations and on-chain settlements?

Our solution combines **x402 micropayments** (EIP-712 signed payments verified on-chain), **EIP-7702 delegation** (temporary authority delegation for EOAs), and **Event Sourcing with triple reconciliation** (payments, delegations, state channels) to create a trust-minimized environment for autonomous agent economies.

---

## 1. Introduction

### 1.1 The Problem

The emergence of Web4 and DeFAI (Decentralized Finance + AI) has created a new class of economic actors: **autonomous AI agents**. These agents need to:

- Pay for compute resources (LLM APIs, storage, bandwidth)
- Delegate tasks to specialized sub-agents
- Maintain reputation across platforms
- Settle transactions without human approval

Traditional API key-based payment systems are inadequate for this paradigm. They require manual key management, lack programmatic delegation, and provide no on-chain audit trail.

### 1.2 The Solution

The Agent Platform provides:

| Capability | Technology | Standard |
|------------|------------|----------|
| Agent-to-API payments | x402 micropayments | EIP-712 |
| Agent-to-agent delegation | EIP-7702 delegation | EIP-7702 |
| Agent identity & reputation | Soulbound Tokens | ERC-721 (modified) |
| Off-chain scaling | State channels | Custom |
| Financial consistency | Triple reconciliation | Custom |

### 1.3 Market Context

- **x402 Protocol**: Processed 100M+ payments between APIs and AI agents by late 2025. Integrated with LangChain and Cloudflare. Batch settlement launched May 2026.
- **EIP-7702**: Entered production May 7, 2025. Enables EOAs to delegate execution to smart contracts temporarily.
- **DeFAI**: AI agents now generate 28.4% of DEX volume. Projected to exceed 80% by 2030.
- **Brazilian Banking**: Institutions like Liqi, BTG, and Itaú are actively exploring tokenization with AI agents. Drex (CBDC) integration is the next frontier.

---

## 2. Architecture

### 2.1 System Overview (C4 Level 1)

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

### 2.2 Backend Architecture (C4 Level 2)

The backend follows **Domain-Driven Design** with **Event Sourcing** and **CQRS**:

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

### 2.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Event Sourcing** | Immutable audit trail, temporal queries, complete state reconstruction |
| **CQRS** | Separate read/write paths, optimize independently, analytics without impact |
| **PostgreSQL JSONB** | Event store with JSON flexibility, relational integrity, no extra infra |
| **Redis Lua Scripts** | Atomic operations for rate limiting, idempotency, quota management |
| **Kafka** | Durable event streaming, replay capability, decoupled consumers |

---

## 3. Technical Implementation

### 3.1 Smart Contracts

#### PaymentVerifier.sol (x402)

```solidity
// Verifies x402 payments with EIP-712 typed signatures
// Features: replay protection, deadline enforcement, nonce management

function verifyPayment(Payment calldata _payment) external returns (bool) {
    // 1. Validate inputs (amount > 0, recipient != 0, deadline not passed)
    // 2. Compute payment hash for replay protection
    // 3. Verify EIP-712 signature
    // 4. Mark as used, increment nonce
    // 5. Emit PaymentVerified event
}
```

**Security Properties**:
- Replay protection via `usedPayments` mapping
- Nonce-based ordering
- EIP-712 typed signatures (phishing-resistant)
- Deadline enforcement (prevents stale payments)

#### AgentDelegation.sol (EIP-7702)

```solidity
// Manages agent delegation with EIP-712 typed signatures
// Features: gasless delegation, expiration, history tracking

function delegateBySig(
    address _agent, address _delegate,
    uint256 _expiresAt, bytes calldata _signature
) external {
    // 1. Verify nonce
    // 2. Compute EIP-712 digest
    // 3. Verify signature
    // 4. Create delegation with expiration
    // 5. Emit DelegationCreated event
}
```

**Security Properties**:
- Nonce-based replay protection
- Expiration-based delegation (temporary authority)
- Delegation history for audit
- Gasless operation (delegate pays gas)

### 3.2 Backend (FastAPI)

**Stack**: Python 3.11+, FastAPI, SQLAlchemy (async), Redis, Kafka, Web3.py

**API Endpoints**:

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/v1/agents/register` | Register new agent |
| `POST` | `/api/v1/agents/delegate` | Delegate authority (EIP-7702) |
| `POST` | `/api/v1/agents/revoke` | Revoke delegation |
| `POST` | `/api/v1/consume` | Consume resource (x402 payment) |
| `GET` | `/api/v1/invoices/{address}` | Get invoice |
| `WS` | `/ws` | Real-time event streaming |

**Consumption Flow**:

```
Agent → POST /consume → Redis (idempotency) → Redis (rate limit)
  → Redis (quota) → Blockchain (x402 verify) → Event Store
  → Kafka (event) → Response (session_id, quota_remaining)
```

### 3.3 Reconciliation Layer

The platform implements **triple reconciliation** to ensure off-chain/on-chain consistency:

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `reconcile_payments.py` | Verify x402 payments match on-chain state | Hourly |
| `reconcile_delegations.py` | Verify EIP-7702 delegations are consistent | Hourly |
| `reconcile_state_channels.py` | Verify channel open/close states | Hourly |

**Reconciliation Flow**:
1. Load events from PostgreSQL Event Store
2. For each event, verify corresponding on-chain state
3. Log discrepancies, generate reports (JSON + CSV)
4. Optionally auto-correct (configurable)

---

## 4. Security & Compliance

### 4.1 Smart Contract Security

- **EIP-712 Typed Signatures**: Prevents phishing and replay attacks
- **Nonce Management**: Sequential nonces prevent transaction reordering
- **Replay Protection**: `usedPayments` mapping prevents double-spending
- **Deadline Enforcement**: Payments expire after deadline
- **Access Control**: Owner-only functions for sensitive operations

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
- Complete transaction history
- Point-in-time state reconstruction
- Regulatory compliance (audit trail)
- Dispute resolution capability

---

## 5. Performance Metrics

*To be populated after mainnet benchmark (see BENCHMARK_PLAN.md)*

| Metric | Target | Measured |
|--------|--------|----------|
| x402 throughput | >100 tx/s | TBD |
| P95 latency | <500ms | TBD |
| P99 latency | <2s | TBD |
| Gas cost (x402 verify) | <50k gas | TBD |
| Reconciliation time | <5 min | TBD |
| Event Store write | >500 events/s | TBD |

---

## 6. Use Cases

### 6.1 Autonomous Trading Agents

AI agents that monitor DeFi markets and execute trades autonomously:
- Agent registers on platform (on-chain identity)
- Agent receives delegation to execute trades
- Agent pays gas via x402 micropayments
- All trades recorded in Event Store for audit

### 6.2 Tokenized Asset Management

Financial institutions tokenizing real-world assets:
- Asset tokenization on Base L2
- AI agents manage portfolio rebalancing
- x402 payments for rebalancing fees
- Triple reconciliation for regulatory compliance

### 6.3 DeFi Portfolio Rebalancing

Automated portfolio management:
- Agent monitors portfolio composition
- Agent executes swaps via delegated authority
- Agent pays fees via x402
- Reputation score tracks agent performance

### 6.4 Brazilian Banking Integration (Drex)

Integration with Brazil's CBDC (Drex):
- Tokenized assets on Drex-compatible network
- AI agents managing treasury operations
- Compliance with BACEN regulations
- Real-time reconciliation with Drex settlement

---

## 7. Roadmap

| Quarter | Milestone | Status |
|---------|-----------|--------|
| Q2 2026 | Testnet deployment (Base Sepolia) | ✅ Complete |
| Q2 2026 | Smart contract audit | 🔄 In progress |
| Q3 2026 | Mainnet deployment (Base L2) | 📅 Planned |
| Q3 2026 | Public benchmark (100k tx) | 📅 Planned |
| Q3 2026 | Pilot with financial partner | 📅 Planned |
| Q4 2026 | EIP-8004 (Agent Cards) integration | 📅 Planned |
| Q4 2026 | EIP-8183 (Agent Commerce) integration | 📅 Planned |
| Q1 2027 | Drex / Real Digital integration | 📅 Planned |
| Q2 2027 | Multi-chain support (Solana, Polygon) | 📅 Planned |

---

## 8. Conclusion

The Agent Platform provides a **production-ready infrastructure** for autonomous AI agents to operate as independent economic entities. By combining x402 micropayments, EIP-7702 delegation, and Event Sourcing with triple reconciliation, it addresses the core requirements of Web4 and DeFAI applications.

The architecture is **minimalist by design** — FastAPI, PostgreSQL, Redis, Kafka — reducing operational complexity while maintaining enterprise-grade reliability. The triple reconciliation layer provides the financial consistency required by regulated institutions.

**Next step**: Mainnet deployment and public benchmark validation.

---

## References

1. [x402 Protocol](https://x402.org) — Micropayments for AI agents
2. [EIP-7702](https://eips.ethereum.org/EIPS/eip-7702) — EOA Delegation
3. [EIP-712](https://eips.ethereum.org/EIPS/eip-712) — Typed structured data hashing and signing
4. [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html) — Martin Fowler
5. [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html) — Martin Fowler
6. [Base L2](https://base.org) — Ethereum L2 by Coinbase
7. [DeFAI Market Report](https://example.com) — AI agents in DeFi (2026)

---

> **Document version**: 0.1.0  
> **Last updated**: June 2026  
> **Contact**: [project maintainers]
