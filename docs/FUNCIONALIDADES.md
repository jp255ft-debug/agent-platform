# 🚀 Agent Platform — Mapa de Funcionalidades

> **Documento de referência** com todas as funcionalidades do sistema, organizadas por camada e domínio.
>
> Versão: 0.1.0 | Atualizado em: Junho/2026

---

## Sumário

1. [🎯 Visão Geral](#-visão-geral)
2. [🧱 Backend (FastAPI)](#-backend-fastapi)
   - [Endpoints REST](#endpoints-rest)
   - [WebSocket](#websocket)
   - [Middleware](#middleware)
   - [Agregados de Domínio](#agregados-de-domínio)
   - [Eventos de Domínio](#eventos-de-domínio)
   - [Serviços de Infraestrutura](#serviços-de-infraestrutura)
   - [Tópicos Kafka](#tópicos-kafka)
3. [🖥️ Node Service (gRPC / GPU)](#️-node-service-grpc--gpu)
4. [⛓️ Smart Contracts (Solidity)](#️-smart-contracts-solidity)
5. [🔗 Integração Financeira (Pix / Stark Bank)](#-integração-financeira-pix--stark-bank)
6. [📊 Observabilidade & Analytics](#-observabilidade--analytics)
7. [🔄 Reconciliação & Consistência](#-reconciliação--consistência)
8. [🧪 Simuladores & Testes](#-simuladores--testes)
9. [🔐 Segurança & Autenticação](#-segurança--autenticação)

---

## 🎯 Visão Geral

O **Agent Platform** é um chassi de **Governança de Custo e Liquidação** para provedores **DePIN** (Decentralized Physical Infrastructure Networks) e Agentes Autônomos. Ele permite:

- **Alocar recursos DePIN** (GPU TFLOPS/hora, VRAM) com pagamento por uso via **x402**
- **Delegar autoridade gasless** usando **EIP-7702** (account delegation)
- **Executar Kill-Switch de Risco Zero** quando o orçamento delegado é excedido
- **Construir reputação on-chain** através de **Soulbound Tokens (SBT)**
- **Operar em Base L2** com **State Channels** para liquidação off-chain
- **Processar pagamentos via Pix** integrado ao Stark Bank

### Stack Tecnológica

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| API REST/WS | FastAPI (Python) | Interface principal |
| Node Service | Node.js + gRPC | Telemetria GPU |
| Event Store | PostgreSQL 15 + JSONB | Log imutável de eventos |
| Cache | Redis 7 | Rate limiting, idempotência |
| Stream | Apache Kafka | Distribuição de eventos |
| Analytics | TimescaleDB | Métricas temporais |
| Smart Contracts | Solidity 0.8+ | Verificação on-chain |
| Blockchain | Base L2 (Sepolia) | Camada de liquidação |
| Pagamentos | Stark Bank (Pix) | Sistema financeiro BR |

---

## 🧱 Backend (FastAPI)

### Endpoints REST

#### 1. Health Check

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Verifica conectividade com banco e Redis |

**Arquivo:** `backend/app/api/v1/endpoints/health.py`

Retorna status `healthy` ou `degraded` com verificação individual de PostgreSQL e Redis.

---

#### 2. Agentes (Agent Management)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/agents` | Registra novo agente |
| `GET` | `/api/v1/agents/{agent_id}` | Obtém detalhes do agente |
| `POST` | `/api/v1/agents/{agent_id}/delegate` | Delega capacidades (EIP-7702) |
| `POST` | `/api/v1/agents/{agent_id}/revoke-delegation` | Revoga delegação |
| `POST` | `/api/v1/agents/{agent_id}/reputation` | Atualiza reputação |

**Arquivo:** `backend/app/api/v1/endpoints/agents.py`

**Comandos:**
- `RegisterAgentCommand` — Registra novo agente com owner_address e delegation_address
- `DelegateAgentCommand` — Delega autoridade para outro endereço com expiração
- `RevokeDelegationCommand` — Revoga delegação ativa
- `UpdateReputationCommand` — Atualiza score de reputação (0-100)

**Eventos emitidos:**
- `AgentRegistered` → Kafka: `agent.registered`
- `AgentDelegated` → Kafka: `agent.delegated`
- `AgentReputationUpdated` → Kafka: `agent.reputation`

---

#### 3. Consumo de Recursos (x402)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/consume` | Consome recurso com pagamento x402 |
| `GET` | `/api/v1/consume/sessions/{session_id}` | Obtém detalhes da sessão de billing |

**Arquivo:** `backend/app/api/v1/endpoints/consume.py`

**Fluxo:**
1. Verifica idempotência (Redis)
2. Verifica rate limit (Redis Token Bucket)
3. Verifica pagamento x402 on-chain
4. Cria `BillingSessionAggregate`
5. Emite `ResourceConsumedV2` → Kafka: `billing.resource.consumed.v2`

**Proteções:**
- Idempotência via `idempotency_key`
- Rate limiting por `agent_id` + `resource_type`
- Retorna `429 Too Many Requests` se excedido

---

#### 4. Faturas (Invoices)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/invoices/{invoice_id}` | Obtém fatura por ID |
| `GET` | `/api/v1/invoices` | Lista faturas com filtros |
| `POST` | `/api/v1/invoices/{invoice_id}/settle` | Liquida fatura |

**Arquivo:** `backend/app/api/v1/endpoints/invoices.py`

**Filtros de listagem:**
- `agent_id` — Filtra por agente
- `status_filter` — Filtra por status (pending, paid, settled)

---

#### 5. Pagamentos Pix

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/pix/qrcode` | Gera QR Code Pix dinâmico |
| `POST` | `/api/v1/pix/webhook` | Recebe confirmação de pagamento Pix |
| `GET` | `/api/v1/pix/{qr_code_id}/status` | Consulta status do pagamento |

**Arquivo:** `backend/app/api/v1/endpoints/pix.py`

**Integração:** Stark Bank (sandbox/produção)
- Geração de QR Code dinâmico com valor, descrição e expiração
- Webhook com validação HMAC (produção)
- Evento `PixPaymentReceived` no Event Store

---

#### 6. API Keys (CRUD + Rotação)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/agents/{agent_id}/api-keys` | Cria nova API key |
| `GET` | `/api/v1/agents/{agent_id}/api-keys` | Lista API keys do agente |
| `POST` | `/api/v1/agents/{agent_id}/api-keys/{key_id}/revoke` | Revoga API key |
| `POST` | `/api/v1/agents/{agent_id}/api-keys/{key_id}/rotate` | Rotaciona API key |

**Arquivo:** `backend/app/api/v1/endpoints/api_keys.py`

**Características:**
- Geração de chaves com hash seguro
- Expiração configurável (default 90 dias)
- Rotação atômica (revoga antiga + cria nova)
- Auditoria de uso (IP, timestamp)
- Autenticação obrigatória via API key existente

---

### WebSocket

| Rota | Descrição |
|------|-----------|
| `GET /ws` | Streaming de eventos em tempo real |

**Arquivo:** `backend/app/api/websocket/event_handler.py`

Conexão persistente para receber eventos de domínio em tempo real (billing, delegations, payments).

---

### Middleware

| Middleware | Descrição | Arquivo |
|-----------|-----------|---------|
| `CORS` | Permite origens configuradas | `app/main.py` |
| `CorrelationIdMiddleware` | Adiciona ID de correlação para tracing | `security.py` |
| `SecurityHeadersMiddleware` | Headers de segurança HTTP | `security.py` |
| `RequestLoggingMiddleware` | Logging estruturado de requisições | `security.py` |
| `RateLimitMiddleware` | Rate limiting (100 req/min) | `rate_limit_middleware.py` |
| `ErrorHandler` | Tratamento global de exceções | `error_handler.py` |

---

### Agregados de Domínio

#### AgentAggregate

Gerencia o ciclo de vida de agentes autônomos:

| Comando | Evento | Descrição |
|---------|--------|-----------|
| `register()` | `AgentRegistered` | Registra novo agente |
| `delegate()` | `AgentDelegated` | Delega autoridade (EIP-7702) |
| `revoke_delegation()` | `DelegationRevoked` | Revoga delegação |
| `update_reputation()` | `AgentReputationUpdated` | Atualiza reputação |

**Arquivo:** `backend/app/domain/aggregates/agent.py`

---

#### ProviderAggregate

Gerencia provedores DePIN (GPU):

| Comando | Evento | Descrição |
|---------|--------|-----------|
| `register()` | `ProviderRegistered` | Registra novo provedor |
| `activate()` | `ProviderStatusChanged` | Ativa provedor (requer stake ≥ 10 USDC) |
| `suspend()` | `ProviderStatusChanged` | Suspende provedor |
| `mark_inactive()` | `ProviderStatusChanged` | Marca como inativo |
| `report_health()` | `HealthReported` | Relatório de telemetria |
| `apply_slashing()` | `SlashingApplied` | Penaliza provedor |
| `stake()` | `ProviderStaked` | Adiciona stake |
| `unstake()` | `ProviderUnstaked` | Remove stake |
| `update_gpu_specs()` | `GPUSpecsUpdated` | Atualiza specs da GPU |
| `record_job_completion()` | `ProviderJobCompleted` | Registra job concluído |

**Arquivo:** `backend/app/domain/aggregates/provider.py`

**Máquina de Estados:**
```
PENDING ──(stake ≥ 10 USDC)──▶ ACTIVE
  │                              │
  │                              ├──▶ SUSPENDED (health)
  │                              ├──▶ SLASHED (penalidade)
  │                              └──▶ INACTIVE (inatividade)
```

**GPUSpecs (Value Object):**
- `model` — Modelo da GPU (ex: "NVIDIA H100")
- `vram_gb` — VRAM em GB
- `tflops_fp16` / `tflops_fp32` — Desempenho
- `cuda_cores` — Número de CUDA cores
- `memory_bandwidth_gbps` — Largura de banda
- `price_per_tflops_hour` — Preço em USDC

---

#### BillingSessionAggregate

Gerencia sessões de faturamento:

| Comando | Evento | Descrição |
|---------|--------|-----------|
| `start()` | `BillingSessionStarted` | Inicia sessão |
| `record_consumption()` | `ResourceConsumedV2` | Registra consumo (DePIN) |
| `close()` | `BillingSessionClosed` | Fecha sessão |
| `settle()` | `BillingSessionSettled` | Liquida sessão |

**Arquivo:** `backend/app/domain/aggregates/billing_session.py`

**Suporte a V2 (DePIN):**
- `ResourceConsumedV2` inclui `cost_micro_usdc` e `provider_id`
- `ResourceConsumed` (V1 legado) aceito para reconstrução histórica via EventUpcaster

---

#### InvoiceAggregate

Gerencia faturas:

| Comando | Evento | Descrição |
|---------|--------|-----------|
| `generate()` | `InvoiceGenerated` | Gera fatura |
| `pay()` | `InvoicePaid` | Marca como paga |

**Arquivo:** `backend/app/domain/aggregates/invoice.py`

---

#### APIKeyAggregate

Gerencia chaves de API:

| Comando | Evento | Descrição |
|---------|--------|-----------|
| `create()` | `APIKeyCreated` | Cria nova chave |
| `revoke_key()` | `APIKeyRevoked` | Revoga chave |
| `rotate_key()` | `APIKeyCreated` + `APIKeyRevoked` | Rotação atômica |
| `expire_keys()` | `APIKeyExpired` | Expira chaves vencidas |
| `record_usage()` | `APIKeyUsed` | Registra uso |

**Arquivo:** `backend/app/domain/aggregates/api_key.py`

---

### Eventos de Domínio

#### Eventos de Agente

| Evento | Kafka Topic | Descrição |
|--------|-------------|-----------|
| `AgentRegistered` | `agent.registered` | Novo agente registrado |
| `AgentDelegated` | `agent.delegated` | Delegação EIP-7702 |
| `AgentReputationUpdated` | `agent.reputation` | Score de reputação alterado |

#### Eventos de Billing

| Evento | Kafka Topic | Descrição |
|--------|-------------|-----------|
| `ResourceConsumed` (V1) | `billing.resource.consumed` | Consumo legado |
| `ResourceConsumedV2` | `billing.resource.consumed.v2` | Consumo DePIN com custo |
| `BillingSessionSettled` | `billing.session.settled` | Sessão liquidada |
| `InvoiceGenerated` | `billing.invoice.generated` | Fatura gerada |
| `InvoicePaid` | `billing.invoice.paid` | Fatura paga |

#### Eventos de Provedor (DePIN)

| Evento | Kafka Topic | Descrição |
|--------|-------------|-----------|
| `ProviderRegistered` | `depin.provider.registered` | Provedor registrado |
| `ProviderStatusChanged` | `depin.provider.status` | Status alterado |
| `HealthReported` | `depin.provider.health` | Telemetria recebida |
| `SlashingApplied` | `depin.provider.slashed` | Penalidade aplicada |
| `ProviderStaked` | `depin.provider.staked` | Stake adicionado |
| `ProviderUnstaked` | `depin.provider.unstaked` | Stake removido |
| `GPUSpecsUpdated` | `depin.provider.gpu_specs` | Specs da GPU atualizadas |
| `ProviderJobCompleted` | `depin.provider.job` | Job concluído |

#### Eventos de Pagamento

| Evento | Kafka Topic | Descrição |
|--------|-------------|-----------|
| `PaymentVerified` | `payment.verified` | Pagamento verificado on-chain |
| `PixPaymentReceived` | — | Pagamento Pix recebido (TODO) |

---

### Serviços de Infraestrutura

#### Event Store (PostgreSQL)

**Arquivo:** `backend/app/infrastructure/db/repositories/event_store.py`

- Armazenamento imutável de eventos em tabela `events` (JSONB)
- Carregamento de stream por `aggregate_id`
- Append com controle de concorrência otimista (`expected_version`)
- Suporte a snapshots para performance

#### Redis Cache

**Arquivos:**
- `backend/app/infrastructure/cache/redis_cache.py` — Cliente Redis
- `backend/app/infrastructure/cache/redis_lua_client.py` — Scripts Lua atômicos

**Scripts Lua:**
| Script | Descrição |
|--------|-----------|
| `rate_limit_check.lua` | Token Bucket para rate limiting |
| `idempotency_check.lua` | Verificação de idempotência |
| `reserve_quota.lua` | Reserva de cota de recursos |

#### Kafka Producer / Consumer

**Arquivos:**
- `backend/app/infrastructure/messaging/kafka_producer.py` — Publica eventos
- `backend/app/infrastructure/messaging/kafka_consumer.py` — Consome eventos

**Características:**
- Producer com `aggregate_id` como partition key (ordering garantido)
- Consumer com `group_id` configurável
- Suporte a múltiplos handlers por tipo de evento

#### Blockchain Clients

| Cliente | Descrição | Arquivo |
|---------|-----------|---------|
| `Web3Client` | Conexão com Base L2 (Sepolia) | `web3_client.py` |
| `PaymentVerifier` | Verificação de pagamentos x402 | `payment_verifier.py` |
| `DelegationContract` | Interação com AgentDelegation.sol | `delegation_contract.py` |

---

### Tópicos Kafka

| Tópico | Partições | Descrição |
|--------|-----------|-----------|
| `agent.registered` | 3 | Novo agente registrado |
| `agent.delegated` | 3 | Delegação de agente |
| `agent.reputation` | 3 | Atualização de reputação |
| `billing.resource.consumed` | 3 | Consumo de recurso (V1) |
| `billing.resource.consumed.v2` | 3 | Consumo DePIN (V2) |
| `billing.session.settled` | 3 | Sessão liquidada |
| `billing.invoice.generated` | 3 | Fatura gerada |
| `billing.invoice.paid` | 3 | Fatura paga |
| `payment.verified` | 3 | Pagamento verificado |
| `depin.provider.registered` | 3 | Provedor registrado |
| `depin.provider.status` | 3 | Status do provedor |
| `depin.provider.health` | 3 | Telemetria do provedor |
| `depin.provider.slashed` | 3 | Penalidade aplicada |
| `depin.provider.staked` | 3 | Stake adicionado |
| `depin.provider.unstaked` | 3 | Stake removido |
| `depin.provider.gpu_specs` | 3 | Specs da GPU |
| `depin.provider.job` | 3 | Job concluído |

---

## 🖥️ Node Service (gRPC / GPU)

### GPU Collector

**Arquivo:** `node-service/src/gpu_collector.ts`

Coleta telemetria da GPU usando `systeminformation` (NVML backend):

| Métrica | Descrição |
|---------|-----------|
| `gpuModel` | Modelo da GPU |
| `gpuUtilization` | Utilização (%) |
| `temperatureCelsius` | Temperatura |
| `memoryUsedGb` / `memoryTotalGb` | Memória |
| `powerWatts` | Consumo |
| `uptimeSeconds` | Uptime do sistema |
| `tflopsFp16` | TFLOPS FP16 estimado |
| `activeJobs` | Jobs ativos (aproximação) |
| `status` | `online` / `degraded` / `offline` |

**Estimativa de TFLOPS:**
- A100: 3x base
- H100: 6x base (Transformer Engine)
- V100: 2x base
- RTX 4090: 2.5x base
- RTX 4080: 2x base
- RTX 3090: 1.5x base

### gRPC Server

**Arquivo:** `node-service/src/server.ts`

| Serviço | RPC | Descrição |
|---------|-----|-----------|
| `GPUTelemetry` | `reportGPUHealth` | Streaming de health reports |
| `GPUTelemetry` | `getGPUStatus` | Consulta de status |

**Proto:** `node-service/src/proto/telemetry.proto`

### Kafka Publisher

**Arquivo:** `node-service/src/kafka_publisher.ts`

| Tópico | Descrição |
|--------|-----------|
| `depin.provider.health` | Health reports da GPU |
| `depin.provider.status` | Mudanças de status (online/degraded/offline) |

**Características:**
- Detecta mudanças de status e publica eventos separados
- Headers com `provider-id` e `event-type`
- Retry com backoff exponencial (10 tentativas)

---

## ⛓️ Smart Contracts (Solidity)

### AgentDelegation.sol

**EIP-7702** — Delegação de autoridade gasless.

| Função | Descrição |
|--------|-----------|
| `setDelegation(address delegate, uint256 expiresAt)` | Define delegação |
| `revokeDelegation()` | Revoga delegação |
| `getDelegation(address agent)` | Consulta delegação ativa |
| `execute(address target, bytes calldata data)` | Executa como delegado |

**Arquivo:** `contracts/src/AgentDelegation.sol`

### PaymentVerifier.sol

**x402** — Verificação de micropagamentos.

| Função | Descrição |
|--------|-----------|
| `verifyPayment(bytes calldata proof)` | Verifica prova de pagamento |
| `processPayment(address from, uint256 amount)` | Processa pagamento |
| `getBalance(address account)` | Consulta saldo |

**Arquivo:** `contracts/src/PaymentVerifier.sol`

### ReputationSBT.sol

**ERC-721 (Soulbound)** — Sistema de reputação não-transferível.

| Função | Descrição |
|--------|-----------|
| `mint(address to, uint256 initialScore)` | Emite SBT de reputação |
| `updateScore(uint256 newScore)` | Atualiza score |
| `getScore(address account)` | Consulta score |
| `getLevel(address account)` | Nível baseado no score |

**Arquivo:** `contracts/src/AgentReputationSBT.sol`

### StateChannelLib.sol

**State Channels** — Liquidação off-chain.

| Função | Descrição |
|--------|-----------|
| `openChannel(address partyA, address partyB, uint256 deposit)` | Abre canal |
| `updateState(bytes32 channelId, bytes calldata newState, bytes calldata signature)` | Atualiza estado |
| `closeChannel(bytes32 channelId, bytes calldata finalState)` | Fecha canal |
| `verifyProof(bytes32 channelId, bytes calldata proof)` | Verifica prova |

**Arquivo:** `contracts/src/libraries/StateChannelLib.sol`

### EIP712Helper.sol

**EIP-712** — Assinaturas tipadas para mensagens off-chain.

| Função | Descrição |
|--------|-----------|
| `hashDelegation(address delegate, uint256 expiresAt)` | Hash de delegação |
| `verify(bytes calldata signature, address signer, bytes32 digest)` | Verifica assinatura |

**Arquivo:** `contracts/src/libraries/EIP712Helper.sol`

---

## 🔗 Integração Financeira (Pix / Stark Bank)

### PixClient

**Arquivo:** `backend/app/infrastructure/payments/pix_client.py`

| Método | Descrição |
|--------|-----------|
| `create_qr_code(amount, description, ...)` | Gera QR Code Pix dinâmico |
| `check_payment(qr_code_id)` | Consulta status do pagamento |

### PixWebhook

**Arquivo:** `backend/app/infrastructure/payments/pix_webhook.py`

- Recebe notificações de pagamento do Stark Bank
- Valida HMAC signature (produção)
- Cria evento `PixPaymentReceived`

### Fluxo Pix

```
1. Agent solicita QR Code → POST /api/v1/pix/qrcode
2. Sistema gera QR Code via Stark Bank
3. Cliente paga via app bancário
4. Stark Bank envia webhook → POST /api/v1/pix/webhook
5. Sistema processa pagamento e emite evento
```

---

## 📊 Observabilidade & Analytics

### Prometheus

- Métricas exportadas pelo backend FastAPI
- Coleta de métricas do sistema (CPU, memória, requests)

### Grafana Dashboards

**Arquivos:** `monitoring/grafana/dashboards/`

| Dashboard | Descrição |
|-----------|-----------|
| `agent-platform-overview.json` | **Métricas de Negócio DePIN**: TVS, Active GPU Leases, Bad Debt Prevented, Kill-Switch Events, Provider Distribution |
| `agent-platform-reconciliation.json` | Monitoramento de discrepâncias e alertas |
| `agent-platform-performance.json` | Performance do sistema (Redis, PostgreSQL, Kafka) |

### TimescaleDB

**Arquivo:** `backend/app/analytics/timescale_queries.py`

- Consultas analíticas otimizadas para séries temporais
- Views materializadas para métricas de negócio
- Migrações em `backend/migrations/versions/002_analytics_views.py`

---

## 🔄 Reconciliação & Consistência

Três scripts garantem consistência entre off-chain (PostgreSQL) e on-chain (Blockchain):

### 1. reconcile_payments.py

**Descrição:** Compara faturas do Event Store com transações x402 on-chain.

**Verificações:**
- Faturas pendentes sem transação correspondente
- Transações sem fatura correspondente
- Discrepâncias de valor

### 2. reconcile_delegations.py

**Descrição:** Verifica consistência das delegações EIP-7702.

**Verificações:**
- Delegações ativas no banco vs on-chain
- Delegações expiradas que precisam ser revogadas
- Delegações órfãs

### 3. reconcile_state_channels.py

**Descrição:** Checa aberturas, atualizações e fechamentos de canais.

**Verificações:**
- Canais abertos no banco vs on-chain
- Atualizações de estado pendentes
- Canais que precisam ser fechados

**Relatórios:** Gerados em `reconciliation_reports/` (JSON e CSV).

---

## 🧪 Simuladores & Testes

### Simuladores de Carga

| Simulador | Comando Make | Descrição |
|-----------|-------------|-----------|
| **Billing** | `make simulate-billing` | Simula agentes consumindo recursos |
| **Delegation** | `make simulate-delegations` | Simula delegações EIP-7702 |
| **Payments** | `make simulate-payments` | Simula pagamentos on-chain (x402) |
| **Pix** | — | Simula pagamentos Pix |

**Arquivos:** `agents/simulator/`

### Testes

| Tipo | Framework | Comando |
|------|-----------|---------|
| Backend (Python) | pytest | `make test-backend` |
| Smart Contracts | Foundry | `make test-contracts` |
| Node Service | Jest | `cd node-service && npm test` |
| Reconciliação | pytest | `scripts/tests/test_reconciliation.py` |

---

## 🔐 Segurança & Autenticação

### API Key Authentication

- Geração de chaves com hash seguro (SHA-256)
- Validação via `validate_api_key` dependency
- Rotação atômica com revogação da chave antiga
- Expiração automática (job schedulado)

### Rate Limiting

- Token Bucket algorithm via Redis Lua scripts
- 100 requisições/minuto por agente (configurável)
- Rate limiting por `agent_id` + `resource_type`

### Idempotência

- Garantia de processamento único via `idempotency_key`
- Armazenamento em Redis com TTL
- Prevenção de duplicatas em pagamentos

### Headers de Segurança

- Correlation ID para tracing distribuído
- Security headers (CSP, X-Frame-Options, etc.)
- Logging estruturado de todas as requisições

### Blockchain Security

- EIP-712 typed signatures para mensagens off-chain
- Verificação on-chain de pagamentos x402
- Slashing automático por violação de SLA
- Stake mínimo de 10 USDC para ativação de provedores

---

## 📋 Resumo por Camada

| Camada | Tecnologias | Funcionalidades |
|--------|-------------|-----------------|
| **API** | FastAPI | 15 endpoints REST, WebSocket, 6 middlewares |
| **Domínio** | Python DDD | 5 agregados, 20+ eventos, Event Sourcing |
| **Infraestrutura** | PostgreSQL, Redis, Kafka | Event Store, Cache, Stream, Blockchain |
| **Node Service** | Node.js, gRPC | Coleta GPU, Health Reports, Kafka Publisher |
| **Smart Contracts** | Solidity | Delegação, Pagamento, Reputação, State Channels |
| **Financeiro** | Stark Bank | Pix QR Code, Webhooks, Pagamentos |
| **Observabilidade** | Prometheus, Grafana, TimescaleDB | 3 dashboards, métricas de negócio |
| **Reconciliação** | Python | 3 scripts, relatórios JSON/CSV |
| **Simuladores** | Python | 4 simuladores de carga |
| **Testes** | pytest, Foundry, Jest | Testes unitários, integração, contratos |

---

> **Documento gerado automaticamente** com base na análise do código-fonte do Agent Platform.
>
> Para contribuir ou reportar inconsistências, consulte o repositório em `https://github.com/jp255ft-debug/agent-platform`.
