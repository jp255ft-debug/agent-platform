# Agent Platform — Mainnet Deployment Checklist

## Production Readiness for Base L2 Mainnet

**Version**: 0.1.0  
**Date**: June 2026  
**Status**: Pre-Deployment

---

## Phase 0: Pre-Deployment Validation

### Security Audit
- [ ] Smart contract audit by **Certora** or **Trail of Bits**
- [ ] Penetration testing on all API endpoints
- [ ] Dependency vulnerability scan (Snyk / Dependabot)
- [ ] Secrets scanning (no hardcoded keys in codebase)
- [ ] Rate limiting bypass testing
- [ ] Idempotency bypass testing

### Legal & Compliance
- [ ] Legal review of smart contract terms
- [ ] Compliance check with **CVM** (Brazilian SEC) for tokenized assets
- [ ] Compliance check with **BACEN** for Drex integration
- [ ] GDPR / LGPD data privacy review
- [ ] Terms of Service drafted
- [ ] Privacy Policy drafted

### Load Testing
- [ ] 100k x402 transactions (see BENCHMARK_PLAN.md)
- [ ] 10k EIP-7702 delegations
- [ ] 50k Event Store writes
- [ ] Reconciliation under load (100 injected discrepancies)
- [ ] Redis Lua script performance (<5ms P99)

---

## Phase 1: Smart Contract Deployment

### Pre-Deployment Checks
- [ ] Contracts compiled with `forge build --optimize --optimizer-runs 200`
- [ ] Gas estimates documented
- [ ] Constructor arguments prepared
- [ ] Deployer wallet funded (ETH for gas)
- [ ] Deployer wallet secured (hardware wallet / multisig)

### Deployment Order
- [ ] **Step 1**: Deploy `EIP712Helper` library
- [ ] **Step 2**: Deploy `StateChannelLib` library
- [ ] **Step 3**: Deploy `AgentDelegation.sol`
  - [ ] Verify on Basescan
  - [ ] Test `delegate()` and `delegateBySig()`
  - [ ] Test `revoke()` and `revokeBySig()`
  - [ ] Test `isValidDelegation()`
- [ ] **Step 4**: Deploy `PaymentVerifier.sol`
  - [ ] Verify on Basescan
  - [ ] Test `verifyPayment()` with valid signature
  - [ ] Test replay protection
  - [ ] Test deadline enforcement
- [ ] **Step 5**: Deploy `AgentReputationSBT.sol`
  - [ ] Verify on Basescan
  - [ ] Test minting
  - [ ] Test transfer restriction (Soulbound)
  - [ ] Test reputation score updates

### Post-Deployment
- [ ] Transfer ownership to **multisig wallet** (Gnosis Safe)
- [ ] Update `.env` with contract addresses
- [ ] Update `backend/app/core/config.py`
- [ ] Run integration tests against deployed contracts
- [ ] Document ABI files in `contracts/out/`

---

## Phase 2: Backend Infrastructure

### Fly.io Setup
- [ ] Create `fly.toml` for production
- [ ] Provision **4 instances** (primary + 3 replicas)
- [ ] Configure auto-scaling (min: 2, max: 6)
- [ ] Set up health checks (`/health` endpoint)
- [ ] Configure rolling deployments
- [ ] Set up **staging** environment (mirror of production)

### PostgreSQL (Neon)
- [ ] Provision **Neon Pro** tier (4GB RAM, HA)
- [ ] Configure connection pooling (PgBouncer)
- [ ] Set up automated backups (hourly)
- [ ] Configure point-in-time recovery (7 days)
- [ ] Enable SSL/TLS connections
- [ ] Create read replicas for analytics queries
- [ ] Run Alembic migrations
- [ ] Verify indexes (events, streams, aggregates)

### Redis
- [ ] Provision **3-node cluster** (16GB each)
- [ ] Configure persistence (AOF + RDB)
- [ ] Set up replication (1 primary + 2 replicas)
- [ ] Configure eviction policy (`allkeys-lru`)
- [ ] Enable TLS encryption
- [ ] Set up monitoring (memory, hit rate, latency)

### Kafka
- [ ] Provision **3-broker cluster**
- [ ] Configure replication factor: 3
- [ ] Configure min.insync.replicas: 2
- [ ] Set up topic retention (7 days)
- [ ] Create all 8 topics with 3 partitions each
- [ ] Enable TLS encryption
- [ ] Set up monitoring (consumer lag, throughput)

### Backend Configuration
- [ ] Generate new **JWT_SECRET** (64+ chars)
- [ ] Generate new **OPERATOR_PRIVATE_KEY** (for blockchain ops)
- [ ] Configure **CORS** (specific origins, not `*`)
- [ ] Set rate limits:
  - [ ] 1000 req/min per IP
  - [ ] 100 req/min per agent
  - [ ] Burst: 200 req/min
- [ ] Enable Prometheus metrics (`/metrics`)
- [ ] Configure structured logging (JSON format)
- [ ] Set log levels (INFO for production)

---

## Phase 3: Security Hardening

### Network Security
- [ ] Configure **Cloudflare** WAF
- [ ] Enable DDoS protection
- [ ] Set up IP whitelist for admin endpoints
- [ ] Configure firewall rules (allow only necessary ports)
- [ ] Enable rate limiting at CDN level

### API Security
- [ ] Implement API key authentication for agent endpoints
- [ ] Add request signing (HMAC) for sensitive operations
- [ ] Enable request validation middleware
- [ ] Set up CORS properly (specific origins)
- [ ] Add security headers (HSTS, CSP, X-Frame-Options)

### Smart Contract Security
- [ ] Deploy with **multisig** (3/5 Gnosis Safe)
- [ ] Set up **timelock** for upgrades (48h delay)
- [ ] Configure **emergency pause** mechanism
- [ ] Monitor for suspicious transactions
- [ ] Set up alerts for large transfers

### Key Management
- [ ] Store private keys in **vault** (HashiCorp Vault / AWS KMS)
- [ ] Rotate API keys quarterly
- [ ] Enable 2FA for all admin accounts
- [ ] Audit key access monthly

---

## Phase 4: Monitoring & Observability

### Grafana Dashboards
- [ ] **Overview Dashboard**: Requests/min, revenue, active agents, error rate
- [ ] **Reconciliation Dashboard**: Discrepancies found, alerts, history
- [ ] **Performance Dashboard**: Latency (Redis, PostgreSQL, Kafka), memory usage
- [ ] **Business Dashboard**: Daily active agents, top agents, revenue trends

### Prometheus Alerts
- [ ] Error rate > 1% (critical)
- [ ] P95 latency > 1s (warning)
- [ ] P95 latency > 2s (critical)
- [ ] Reconciliation discrepancy detected (critical)
- [ ] Redis memory > 80% (warning)
- [ ] PostgreSQL connections > 80% (warning)
- [ ] Kafka consumer lag > 1000 (warning)
- [ ] SSL certificate expiring < 30 days (warning)

### Logging
- [ ] Centralized log aggregation (Datadog / ELK Stack)
- [ ] Structured JSON logging
- [ ] 90-day log retention
- [ ] Log level: INFO (production)
- [ ] Audit log for all admin actions

### APM (Application Performance Monitoring)
- [ ] Set up **Sentry** for error tracking
- [ ] Configure distributed tracing
- [ ] Monitor slow queries (>100ms)
- [ ] Track external API call latency

### Uptime Monitoring
- [ ] Set up **Pingdom** / **Better Uptime**
- [ ] Monitor `/health` endpoint (30s interval)
- [ ] Monitor `/api/v1/consume` (synthetic transaction)
- [ ] Configure status page

---

## Phase 5: Disaster Recovery

### Backup Strategy
- [ ] PostgreSQL: Hourly backups, 7-day retention
- [ ] Redis: AOF + RDB persistence
- [ ] Kafka: Topic retention (7 days)
- [ ] Configuration: Version-controlled (Git)
- [ ] Smart contracts: Immutable (no upgrade needed)

### Recovery Procedures
- [ ] **Database failure**: Restore from backup (RTO: 1h, RPO: 1h)
- [ ] **Redis failure**: Rebuild from Event Store (RTO: 30min)
- [ ] **Kafka failure**: Replay from last committed offset (RTO: 15min)
- [ ] **Blockchain RPC failure**: Failover to secondary RPC (automatic)
- [ ] **Full region failure**: Deploy to secondary region (RTO: 4h)

### Runbook
- [ ] Document incident response procedures
- [ ] Create on-call rotation schedule
- [ ] Set up PagerDuty integration
- [ ] Conduct disaster recovery drill (quarterly)

---

## Phase 6: Go-Live

### Pre-Launch
- [ ] Final security review
- [ ] Final load test
- [ ] Stakeholder sign-off
- [ ] Communication plan drafted
- [ ] Support team trained

### Gradual Rollout
- [ ] **Phase 1** (Day 1): 10% of traffic
  - [ ] Monitor error rates (<0.1%)
  - [ ] Monitor latency (P95 <500ms)
  - [ ] Monitor reconciliation (zero discrepancies)
- [ ] **Phase 2** (Day 3): 50% of traffic
  - [ ] Same checks as Phase 1
  - [ ] Scale infrastructure if needed
- [ ] **Phase 3** (Day 7): 100% of traffic
  - [ ] Full production load
  - [ ] Continuous monitoring

### Post-Launch
- [ ] Announce mainnet launch (Twitter, blog, Discord)
- [ ] Publish benchmark results
- [ ] Monitor for 72 hours (24/7 coverage)
- [ ] Retrospective after 1 week
- [ ] Retrospective after 1 month

---

## Phase 7: Ongoing Operations

### Daily
- [ ] Check reconciliation reports
- [ ] Review error rates
- [ ] Monitor infrastructure costs

### Weekly
- [ ] Review security alerts
- [ ] Analyze performance trends
- [ ] Update dependencies (patch versions)

### Monthly
- [ ] Rotate API keys
- [ ] Review access logs
- [ ] Capacity planning review
- [ ] Disaster recovery drill

### Quarterly
- [ ] Full security audit
- [ ] Penetration testing
- [ ] Dependency upgrade (major versions)
- [ ] Business continuity review

---

## Quick Reference: Commands

```bash
# Deploy contracts
cd contracts && forge script script/DeployAgentDelegation.s.sol --rpc-url base_mainnet --broadcast
cd contracts && forge script script