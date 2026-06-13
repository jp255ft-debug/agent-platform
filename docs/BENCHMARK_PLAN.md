# Agent Platform — Benchmark Plan

## Public Performance Validation for Production Readiness

**Version**: 0.1.0  
**Date**: June 2026  
**Status**: Draft

---

## 1. Objective

Validate the Agent Platform's ability to handle **production-scale workloads** for x402 micropayments, EIP-7702 delegations, and triple reconciliation. Results will be published as a public benchmark report.

### Success Criteria

| Metric | Target | Critical? |
|--------|--------|-----------|
| x402 throughput | >100 tx/s sustained | ✅ Yes |
| P95 latency (end-to-end) | <500ms | ✅ Yes |
| P99 latency (end-to-end) | <2s | ✅ Yes |
| Reconciliation accuracy | 100% (zero false positives) | ✅ Yes |
| Zero lost transactions | 0 discrepancies | ✅ Yes |
| Event Store write throughput | >500 events/s | ✅ Yes |
| Kafka event propagation | <100ms P99 | ✅ Yes |
| Redis Lua script latency | <5ms P99 | ✅ Yes |

---

## 2. Benchmark Scenarios

### Scenario 1: x402 Payment Throughput

**Goal**: Measure sustained x402 payment processing capacity.

**Parameters**:
- Total payments: 100,000
- Duration: 1 hour (target: ~28 tx/s sustained)
- Concurrency: 50 parallel agents
- Resource types: LLM, STT, TTS (evenly distributed)
- Payment amounts: random (1-100 wei)

**Metrics**:
- Transactions per second (moving average)
- Success rate (%)
- Gas cost per transaction
- Event Store write latency
- Redis Lua script latency (idempotency + rate limit + quota)

**Expected Outcome**: System maintains >100 tx/s with <0.1% error rate.

### Scenario 2: EIP-7702 Delegation

**Goal**: Measure delegation creation, verification, and revocation performance.

**Parameters**:
- Total delegations: 10,000
- Total revocations: 10,000
- Duration: 30 minutes
- Concurrency: 25 parallel agents
- Delegation duration: random (1-24 hours)

**Metrics**:
- Delegation creation throughput
- Signature verification time (EIP-712)
- Nonce consistency (zero conflicts)
- Event Store append latency
- Reconciliation detection time

**Expected Outcome**: 100% nonce consistency, <100ms signature verification.

### Scenario 3: Reconciliation Under Load

**Goal**: Validate triple reconciliation accuracy under high transaction volume.

**Parameters**:
- Total events in Event Store: 50,000
- Forced discrepancies: 100 (randomly injected)
- Reconciliation frequency: every 5 minutes
- Duration: 2 hours

**Metrics**:
- Discrepancy detection rate (target: 100%)
- False positive rate (target: 0%)
- Reconciliation execution time
- Report generation time

**Expected Outcome**: 100% of injected discrepancies detected, zero false positives.

### Scenario 4: Concurrent Mixed Workload

**Goal**: Measure system behavior under realistic mixed workload.

**Parameters**:
- 50 agents performing mixed operations
- 70% x402 payments
- 20% delegation operations
- 10% invoice queries
- Duration: 2 hours

**Metrics**:
- All metrics from Scenarios 1-3
- Resource contention (CPU, memory, connections)
- Database connection pool utilization
- Kafka consumer lag

**Expected Outcome**: No degradation in any individual metric compared to isolated scenarios.

---

## 3. Infrastructure Setup

### 3.1 Production-like Environment

| Component | Specification | Provider |
|-----------|--------------|----------|
| Backend (FastAPI) | 4 instances, 2 vCPU / 4GB RAM each | Fly.io |
| PostgreSQL (Event Store) | Neon Pro (4GB RAM, HA) | Neon |
| Redis | 16GB, 3 nodes cluster | Fly.io |
| Kafka | 3 brokers, 3 partitions per topic | Fly.io |
| Blockchain | Base L2 Sepolia (testnet) | Base |
| Monitoring | Prometheus + Grafana | Fly.io |

### 3.2 Simulator Agents

| Component | Specification |
|-----------|--------------|
| Agent simulator | 50 concurrent agents |
| Request rate | Configurable (1-100 req/s) |
| Failure injection | Configurable (0-10%) |
| Metrics export | Prometheus push gateway |

### 3.3 Monitoring Stack

- **Prometheus**: Scraping every 15 seconds
- **Grafana**: Real-time dashboards (3 pre-built)
- **Alerting**: PagerDuty integration for anomalies
- **Logging**: Structured JSON logs, 30-day retention

---

## 4. Execution Timeline

```
Week 1: Infrastructure Provisioning
├── Deploy Fly.io instances
├── Configure Neon PostgreSQL
├── Set up Redis cluster
├── Deploy Kafka cluster
├── Configure monitoring stack
└── Smoke tests

Week 2: Simulator Calibration
├── Calibrate agent simulators
├── Validate metrics collection
├── Tune rate limiting parameters
├── Test failure injection
└── Dry run (1,000 transactions)

Week 3: Benchmark Execution
├── Day 1: Scenario 1 (x402 throughput)
├── Day 2: Scenario 2 (EIP-7702 delegation)
├── Day 3: Scenario 3 (Reconciliation)
├── Day 4: Scenario 4 (Mixed workload)
└── Day 5: Data analysis

Week 4: Report Publication
├── Analyze results
├── Write benchmark report
├── Publish on GitHub
├── Share on Twitter / LinkedIn
└── Present to potential partners
```

---

## 5. Data Collection

### 5.1 Metrics to Collect

```yaml
metrics:
  throughput:
    - tx_per_second
    - requests_per_minute
    - events_per_second
  
  latency:
    - p50_end_to_end_ms
    - p95_end_to_end_ms
    - p99_end_to_end_ms
    - p50_event_store_write_ms
    - p95_event_store_write_ms
    - p50_redis_lua_ms
    - p95_redis_lua_ms
  
  errors:
    - error_rate_percent
    - timeout_count
    - rate_limit_hits
    - idempotency_hits
  
  blockchain:
    - gas_cost_per_tx
    - tx_confirmation_time
    - nonce_conflicts
  
  infrastructure:
    - cpu_usage_percent
    - memory_usage_mb
    - db_connection_pool_usage
    - kafka_consumer_lag
```

### 5.2 Export Format

All metrics will be exported as:
- **CSV**: Raw data for analysis
- **JSON**: Structured format for programmatic consumption
- **Grafana snapshots**: Visual dashboards
- **PDF report**: Executive summary

---

## 6. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Testnet RPC rate limits | High | Use multiple RPC endpoints, implement retry logic |
| Infrastructure cost overrun | Medium | Set budget alerts, use spot instances |
| Simulator bugs | High | Dry run before full benchmark |
| Network latency variance | Low | Run multiple iterations, report percentiles |
| Data loss | Critical | Real-time replication, hourly backups |

---

## 7. Success Criteria Summary

```
✅ PASS: All 5 success criteria met
⚠️ PARTIAL: 3-4 criteria met (identify gaps)
❌ FAIL: <3 criteria met (remediation required)
```

### Post-Benchmark Actions

| Result | Action |
|--------|--------|
| ✅ PASS | Proceed to mainnet deployment |
| ⚠️ PARTIAL | Address gaps, re-run affected scenarios |
| ❌ FAIL | Architecture review, fix issues, re-run |

---

## 8. Appendix: Simulator Configuration

### Agent Simulator (`agents/simulator/agent_simulator.py`)

```bash
# Usage
python -m agents.simulator.agent_simulator \
    --agents 50 \
    --rate 30 \
    --duration 3600 \
    --failure-rate 0.01 \
    --metrics-endpoint http://prometheus:9091
```

### Delegation Simulator (`agents/simulator/delegation_simulator.py`)

```bash
python -m agents.simulator.delegation_simulator \
    --agents 25 \
    --rate 10 \
    --duration 1800 \
    --delegation-duration 3600
```

### Payment Simulator (`agents/simulator/payment_simulator.py`)

```bash
python -m agents.simulator.payment_simulator \
    --rate 30 \
    --failure-rate 0.05 \
    --duration 3600 \
    --amount-range 1-100
```

---

> **Document version**: 0.1.0  
> **Last updated**: June 2026
