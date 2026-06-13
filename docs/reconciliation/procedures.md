# Reconciliation Procedures

## Overview

Reconciliation ensures consistency between on-chain blockchain state and off-chain event store data. This document describes the procedures, schedules, and runbooks for each reconciliation process.

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Blockchain (Base) │         │   PostgreSQL (Event   │
│                     │         │       Store)          │
│  ┌───────────────┐  │         │                      │
│  │PaymentVerifier│  │         │  ┌────────────────┐  │
│  │  (Events)     │──┼─────────┼─▶│ billing_sessions│  │
│  └───────────────┘  │         │  └────────────────┘  │
│  ┌───────────────┐  │         │  ┌────────────────┐  │
│  │AgentDelegation│  │         │  │  delegations   │  │
│  │  (Events)     │──┼─────────┼─▶│  (events)      │  │
│  └───────────────┘  │         │  └────────────────┘  │
│  ┌───────────────┐  │         │  ┌────────────────┐  │
│  │State Channels │  │         │  │state_channels  │  │
│  │  (Events)     │──┼─────────┼─▶│  (events)      │  │
│  └───────────────┘  │         │  └────────────────┘  │
└─────────────────────┘         └──────────────────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
            ┌───────▼────────┐
            │  Reconciliation │
            │    Engine       │
            │                 │
            │  ┌───────────┐  │
            │  │  Matcher  │  │
            │  └───────────┘  │
            │  ┌───────────┐  │
            │  │  Reporter │  │
            │  └───────────┘  │
            │  ┌───────────┐  │
            │  │  Alerter  │  │
            │  └───────────┘  │
            └─────────────────┘
```

## Reconciliation Types

### 1. Payment Reconciliation

**Purpose:** Verify that all on-chain `PaymentVerified` events have corresponding off-chain billing sessions, and vice versa.

**Frequency:** Every 1 hour

**Script:** `scripts/reconciliation/reconcile_payments.py`

**Matching Criteria:**
- Primary key: `tx_hash` (transaction hash)
- Secondary check: `amount` (must match exactly)
- Time window: Last 24 hours (configurable via `--hours`)

**Expected Metrics:**
| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Discrepancy rate | < 0.1% | 0.1-0.5% | > 0.5% |
| On-chain only | 0 | 1-5 | > 5 |
| Off-chain only | 0 | 1-5 | > 5 |
| Amount mismatches | 0 | 1-3 | > 3 |

**Runbook:**

```bash
# Manual execution
python -m scripts.reconciliation.reconcile_payments --hours 24 --alert

# With custom output directory
python -m scripts.reconciliation.reconcile_payments --hours 48 --output-dir /var/log/reconciliation

# Verbose mode for debugging
python -m scripts.reconciliation.reconcile_payments --hours 6 --verbose
```

**Alert Conditions:**
- Discrepancy rate > 0.1%
- Any on-chain-only or off-chain-only records
- Any amount mismatches

### 2. Delegation Reconciliation

**Purpose:** Verify that on-chain delegation state matches off-chain delegation events.

**Frequency:** Every 6 hours

**Script:** `scripts/reconciliation/reconcile_delegations.py`

**Matching Criteria:**
- Primary key: `agent` address
- State comparison: `active` flag on-chain vs. last event type off-chain
- Expiration check: `expiresAt` timestamp

**Expected Metrics:**
| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Discrepancy rate | < 0.1% | 0.1-0.5% | > 0.5% |
| State mismatches | 0 | 1-3 | > 3 |
| Expired delegations | N/A | Monitor | Monitor |

**Runbook:**

```bash
# Manual execution
python -m scripts.reconciliation.reconcile_delegations --hours 24

# Extended window for audit
python -m scripts.reconciliation.reconcile_delegations --hours 168
```

### 3. State Channel Reconciliation

**Purpose:** Verify that on-chain channel events match off-chain state channel events.

**Frequency:** Every 12 hours

**Script:** `scripts/reconciliation/reconcile_state_channels.py`

**Matching Criteria:**
- Primary key: `channel_id`
- State comparison: open/closed/disputed status

**Expected Metrics:**
| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Discrepancy rate | < 0.1% | 0.1-0.5% | > 0.5% |
| Pending disputes | 0 | 1-2 | > 2 |
| State mismatches | 0 | 1 | > 1 |

**Runbook:**

```bash
# Manual execution
python -m scripts.reconciliation.reconcile_state_channels --hours 24

# Extended window for audit
python -m scripts.reconciliation.reconcile_state_channels --hours 72
```

## Automated Scheduling

### Option 1: Cron (Linux/Mac)

```cron
# Payment reconciliation - every hour
0 * * * * cd /opt/agent-platform && python -m scripts.reconciliation.reconcile_payments --alert >> /var/log/reconciliation/payments.log 2>&1

# Delegation reconciliation - every 6 hours
0 */6 * * * cd /opt/agent-platform && python -m scripts.reconciliation.reconcile_delegations >> /var/log/reconciliation/delegations.log 2>&1

# State channel reconciliation - every 12 hours
0 */12 * * * cd /opt/agent-platform && python -m scripts.reconciliation.reconcile_state_channels >> /var/log/reconciliation/channels.log 2>&1
```

### Option 2: Systemd Timer

```ini
# /etc/systemd/system/reconciliation-payments.service
[Unit]
Description=Agent Platform Payment Reconciliation
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/agent-platform
ExecStart=/usr/bin/python -m scripts.reconciliation.reconcile_payments --alert
User=agent-platform

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/reconciliation-payments.timer
[Unit]
Description=Run payment reconciliation hourly
Requires=reconciliation-payments.service

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

### Option 3: Docker Container

```yaml
# docker-compose.yml addition
reconciliation:
  build: .
  command: >
    sh -c "while true; do
      python -m scripts.reconciliation.reconcile_payments --alert;
      sleep 3600;
    done"
  environment:
    - RPC_URL_BASE=${RPC_URL_BASE}
    - PAYMENT_VERIFIER_ADDRESS=${PAYMENT_VERIFIER_ADDRESS}
    - AGENT_DELEGATION_ADDRESS=${AGENT_DELEGATION_ADDRESS}
    - DATABASE_URL=${DATABASE_URL}
    - RECONCILIATION_ALERT_WEBHOOK=${RECONCILIATION_ALERT_WEBHOOK}
```

## Report Format

### JSON Report

Reports are saved as JSON files in the configured output directory:

```json
{
  "run_id": "20260610_143022",
  "timestamp": "2026-06-10T14:30:22.123456+00:00",
  "window_start": "2026-06-09T14:30:22+00:00",
  "window_end": "2026-06-10T14:30:22+00:00",
  "total_on_chain": 150,
  "total_off_chain": 148,
  "matched": 148,
  "on_chain_only": 2,
  "off_chain_only": 0,
  "amount_mismatches": 0,
  "total_on_chain_amount": 500000000000000000,
  "total_off_chain_amount": 500000000000000000,
  "total_discrepancy": 0,
  "matches": [
    {
      "on_chain": {
        "tx_hash": "0xabc...",
        "sender": "0x123...",
        "recipient": "0x456...",
        "amount": 1000000000000000,
        "nonce": 5,
        "block_number": 12345678,
        "block_timestamp": 1718031422,
        "log_index": 42
      },
      "off_chain": {
        "session_id": "session_abc...",
        "agent_id": "agent_123...",
        "tx_hash": "0xabc...",
        "amount": 1000000000000000,
        "status": "completed",
        "created_at": "2026-06-10T14:25:00+00:00"
      },
      "status": "matched",
      "discrepancy": 0
    }
  ],
  "errors": [],
  "discrepancy_rate": 0.0133,
  "is_healthy": false
}
```

### Alert Format

Alerts are sent via webhook (Slack/Discord) when discrepancies exceed thresholds:

```
🚨 *Reconciliation Alert*
Discrepancy rate: 1.33%
Threshold: 0.10%
On-chain only: 2
Off-chain only: 0
Amount mismatches: 0
Total discrepancy: 0 wei
Window: 2026-06-09T14:30:22 to 2026-06-10T14:30:22
```

## Incident Response

### Level 1: Minor Discrepancy (< 0.5%)

**Symptoms:** Small number of unmatched records, no amount mismatches.

**Actions:**
1. Check if the discrepancy is due to timing (events near window boundary)
2. Re-run reconciliation with extended window
3. If resolved, no further action needed
4. Log in reconciliation journal

### Level 2: Moderate Discrepancy (0.5-2%)

**Symptoms:** Multiple unmatched records, some amount mismatches.

**Actions:**
1. Investigate each unmatched record
2. Check blockchain reorg status
3. Verify event store integrity
4. Check for duplicate events
5. Manual correction if needed
6. Create incident report

### Level 3: Critical Discrepancy (> 2%)

**Symptoms:** Large number of unmatched records, significant amount mismatches.

**Actions:**
1. **IMMEDIATE:** Pause automated billing
2. Investigate root cause:
   - Check blockchain RPC connectivity
   - Verify contract addresses
   - Check event store for corruption
   - Review recent deployments
3. Restore from backup if needed
4. Manual reconciliation
5. Post-mortem analysis
6. Update procedures

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RPC_URL_BASE` | Base L2 RPC endpoint | `https://sepolia.base.org` |
| `PAYMENT_VERIFIER_ADDRESS` | PaymentVerifier contract address | (required) |
| `AGENT_DELEGATION_ADDRESS` | AgentDelegation contract address | (required) |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://agent:agent@localhost:5432/agent_platform` |
| `RECONCILIATION_ALERT_WEBHOOK` | Slack/Discord webhook URL | (optional) |

### Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_discrepancy_rate` | 0.001 (0.1%) | Maximum acceptable discrepancy rate |
| `max_block_lag` | 10 | Maximum blocks behind before alert |
| `reconciliation_window_hours` | 24 | Default lookback window |

## Maintenance

### Log Rotation

```bash
# /etc/logrotate.d/reconciliation
/var/log/reconciliation/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 agent-platform agent-platform
}
```

### Report Cleanup

```bash
# Clean reports older than 90 days
find /var/log/reconciliation -name "*.json" -mtime +90 -delete
find /var/log/reconciliation -name "*.txt" -mtime +90 -delete
```

## Testing

### Unit Tests

```bash
# Run reconciliation tests
python -m pytest scripts/tests/test_reconciliation.py -v
```

### Integration Tests

```bash
# Test with local Anvil instance
anvil --fork-url https://sepolia.base.org &
python -m scripts.reconciliation.reconcile_payments --hours 1 --verbose
```

### Dry Run

All reconciliation scripts support dry-run mode by default (no `--alert` flag). This allows testing without sending alerts.

## Related Documents

- [ADR-001: Payment Mechanism](../../docs/adr/ADR-001-payment-mechanism.md)
- [ADR-002: Delegation EIP-7702](../../docs/adr/ADR-002-delegation-eip7702.md)
- [ADR-003: Event Sourcing PostgreSQL](../../docs/adr/ADR-003-event-sourcing-postgres.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Threat Model](../../docs/diagrams/threat-models/stride-matrix.md)
