# Agent Platform — Build Guide

## Manual de Construção e Arquitetura Detalhada

> **Propósito**: Este documento descreve como o Agent Platform foi construído, a função de cada diretório e arquivo, as decisões arquiteturais tomadas, e como estender o sistema seguindo os padrões existentes.

---

## 📑 Índice

1. [Visão Geral da Estrutura](#1-visão-geral-da-estrutura)
2. [Ordem de Construção (Fases)](#2-ordem-de-construção)
3. [Camada 1: Smart Contracts (Solidity)](#3-camada-1-smart-contracts)
4. [Camada 2: Backend Core (FastAPI + DDD)](#4-camada-2-backend-core)
5. [Camada 3: Infraestrutura](#5-camada-3-infraestrutura)
6. [Camada 4: Aplicação (Commands & Handlers)](#6-camada-4-aplicação)
7. [Camada 5: API & WebSocket](#7-camada-5-api--websocket)
8. [Camada 6: Analytics & Monitoramento](#8-camada-6-analytics--monitoramento)
9. [Camada 7: Reconciliação](#9-camada-7-reconciliação)
10. [Camada 8: Simuladores & Testes](#10-camada-8-simuladores--testes)
11. [Camada 9: DevOps & CI/CD](#11-camada-9-devops--cicd)
12. [Decisões Arquiteturais (ADRs)](#12-decisões-arquiteturais)
13. [Guia de Extensão](#13-guia-de-extensão)
14. [Fluxos Completos](#14-fluxos-completos)
15. [Camada 10: Conformidade e Regulatório (KYC/AML)](#15-camada-10-conformidade-e-regulatório)
16. [Camada 11: Integração com Sistema Financeiro Brasileiro](#16-camada-11-integração-com-sistema-financeiro-brasileiro)
17. [Camada 12: Governança Institucional e LGPD](#17-camada-12-governança-institucional-e-lgpd)
18. [Roadmap de Adaptação ao Mercado Brasileiro (90 Dias)](#18-roadmap-de-adaptação-ao-mercado-brasileiro)
19. [Fluxos Estendidos para Mercado Financeiro](#19-fluxos-estendidos-para-mercado-financeiro)

---

## 1. Visão Geral da Estrutura

```
agent-platform/
│
├── .ai/                          # Contexto para assistentes de IA (Cline/Claude)
├── .github/workflows/            # CI/CD (GitHub Actions)
├── agents/                       # Simuladores de carga e replay
├── backend/                      # Backend principal (FastAPI + Python)
├── contracts/                    # Smart Contracts (Solidity + Foundry)
├── docs/                         # Documentação completa
├── lib/                          # Dependências Git (submodules)
├── monitoring/                   # Prometheus + Grafana
├── scripts/                      # Scripts de automação
├── timescaledb/                  # Migrations do TimescaleDB
│
├── docker-compose.yml            # Orquestração de serviços
├── Makefile                      # Comandos rápidos
├── ARCHITECTURE.md               # Arquitetura C4
├── BUILD_GUIDE.md                # ← Este documento
└── README.md                     # Documentação principal (inglês)
```

### Princípios Arquiteturais

| Princípio | Descrição |
|-----------|-----------|
| **Event Sourcing** | Todo estado é derivado de eventos imutáveis armazenados no PostgreSQL |
| **CQRS** | Separação entre comandos (escrita) e queries (leitura) |
| **DDD** | Domain-Driven Design com agregados, eventos e repositórios |
| **On-Chain Verification** | Pagamentos e delegações verificados na blockchain |
| **Reconciliation** | Consistência entre off-chain e on-chain via scripts periódicos |

---

## 2. Ordem de Construção

O sistema foi construído nesta ordem, cada fase dependendo da anterior:

```
FASE 1: Smart Contracts ──────────▶ Contratos Solidity + testes Foundry
       │
       ▼
FASE 2: Domain Layer ─────────────▶ Agregados, Eventos, Repositórios (DDD)
       │
       ▼
FASE 3: Infrastructure ──────────▶ PostgreSQL, Redis, Kafka, Web3
       │
       ▼
FASE 4: Application Layer ───────▶ Commands, Handlers, Services
       │
       ▼
FASE 5: API Layer ───────────────▶ Endpoints REST, Schemas, Middleware
       │
       ▼
FASE 6: Analytics ───────────────▶ TimescaleDB, Queries, Dashboards
       │
       ▼
FASE 7: Reconciliation ──────────▶ Scripts de consistência off-chain/on-chain
       │
       ▼
FASE 8: Simulators & Tests ──────▶ Simuladores de carga, CI/CD
```

---

## 3. Camada 1: Smart Contracts

### Estrutura

```
contracts/
├── foundry.toml              # Configuração do Foundry (compilador Solidity)
├── remappings.txt            # Mapeamento de imports (forge-std, openzeppelin)
│
├── src/                      # Contratos principais
│   ├── AgentDelegation.sol   # Delegação EIP-7702
│   ├── AgentReputationSBT.sol# Sistema de reputação (Soulbound Token)
│   ├── PaymentVerifier.sol   # Verificação de pagamentos x402
│   │
│   └── libraries/            # Bibliotecas auxiliares
│       ├── EIP712Helper.sol  # Utilitários EIP-712 (typed signatures)
│       └── StateChannelLib.sol # Lógica de state channels off-chain
│
├── script/                   # Scripts de deploy
│   ├── DeployAgentDelegation.s.sol
│   ├── DeployPaymentVerifier.s.sol
│   └── DeployReputationSBT.s.sol
│
└── test/                     # Testes Foundry (Forge)
    ├── AgentDelegation.t.sol
    ├── EIP712Helper.t.sol
    ├── PaymentVerifier.t.sol
    ├── ReputationSBT.t.sol
    └── StateChannelLib.t.sol
```

### Detalhamento dos Contratos

#### `AgentDelegation.sol` — EIP-7702

**Propósito**: Permite que agentes deleguem autoridade para outras contas, com suporte a expiração e assinaturas EIP-712 (gasless).

**Padrões**:
- EIP-712 typed signatures para delegação sem gas
- Nonces para proteção contra replay
- Histórico de delegações por agente

**Funções principais**:
```solidity
function delegate(address _delegate, uint256 _expiresAt) external;
function delegateBySig(address _agent, address _delegate, uint256 _expiresAt, bytes calldata _signature) external;
function revoke() external;
function revokeBySig(address _agent, bytes calldata _signature) external;
function isValidDelegation(address _agent, address _delegate) external view returns (bool);
```

#### `PaymentVerifier.sol` — x402

**Propósito**: Verifica pagamentos x402 (micropagamentos on-chain) usando EIP-712.

**Padrões**:
- Replay protection via `usedPayments` mapping
- Deadline para expiração de pagamentos
- Nonces incrementais

**Funções principais**:
```solidity
function verifyPayment(Payment calldata _payment) external returns (bool);
function getNonce(address _sender) external view returns (uint256);
function isPaymentUsed(bytes32 _paymentHash) external view returns (bool);
```

#### `AgentReputationSBT.sol` — ERC-721 (Soulbound)

**Propósito**: Sistema de reputação não-transferível (Soulbound Token).

**Características**:
- ERC-721 com transferências bloqueadas
- Apenas o contrato pode mintar/burnar
- Score de reputação armazenado on-chain

#### `StateChannelLib.sol` — Off-Chain Scaling

**Propósito**: Biblioteca para gerenciamento de state channels, permitindo múltiplas transações off-chain com settlement on-chain.

### Como Adicionar um Novo Contrato

1. Criar o contrato em `contracts/src/`
2. Usar `forge-std` e `openzeppelin-contracts` como dependências
3. Criar script de deploy em `contracts/script/`
4. Criar testes em `contracts/test/` (nomenclatura: `*.t.sol`)
5. Rodar `forge build` e `forge test`

---

## 4. Camada 2: Backend Core

### Estrutura

```
backend/
├── Dockerfile                 # Imagem Docker do backend
├── pyproject.toml             # Configuração Python (dependências, ferramentas)
├── requirements.txt           # Dependências Python (pip freeze)
├── alembic.ini                # Configuração do Alembic (migrations)
│
└── app/
    ├── main.py                # Entrypoint FastAPI (lifespan, routers, middleware)
    ├── __init__.py
    │
    ├── core/                  # Configurações centrais
    │   ├── config.py          # Settings via pydantic-settings (variáveis de ambiente)
    │   ├── dependencies.py    # Dependências FastAPI (DB session, etc.)
    │   ├── exceptions.py      # Exceções customizadas
    │   └── logging.py         # Configuração de logging estruturado
    │
    ├── domain/                # 🎯 DOMAIN LAYER (DDD)
    │   ├── aggregates/        # Agregados (unidades de consistência)
    │   │   ├── agent.py           # AgentAggregate
    │   │   ├── billing_session.py # BillingSessionAggregate
    │   │   ├── invoice.py         # InvoiceAggregate
    │   │   └── api_key.py         # 🆕 APIKeyAggregate (event sourcing)
    │   │
    │   ├── events/            # Eventos de domínio
    │   │   ├── base.py            # DomainEvent (classe base)
    │   │   ├── agent_events.py    # Eventos de agente
    │   │   ├── billing_events.py  # Eventos de billing
    │   │   ├── payment_events.py  # Eventos de pagamento
    │   │   └── api_key_events.py  # 🆕 Eventos de API Key
    │   │
    │   └── repositories/      # Interfaces de repositório (protocolos)
    │       ├── event_store.py     # EventStore (interface)
    │       └── snapshot_repo.py   # SnapshotRepository (interface)
    │
    ├── application/           # 🎯 APPLICATION LAYER
    │   ├── commands/          # Command objects
    │   │   ├── register_agent.py
    │   │   ├── consume_resource.py
    │   │   └── settle_invoice.py
    │   │
    │   ├── handlers/          # Command & Event handlers
    │   │   ├── command_handlers.py  # Processa comandos → produz eventos
    │   │   └── event_handlers.py    # Reage a eventos (side effects)
    │   │
    │   └── services/          # Serviços de aplicação
    │       ├── idempotency.py      # Garantia de idempotência
    │       └── rate_limiter.py     # Rate limiting
    │
    ├── infrastructure/        # 🎯 INFRASTRUCTURE LAYER
    │   ├── blockchain/        # Integração com blockchain
    │   │   ├── web3_client.py         # Cliente Web3 genérico
    │   │   ├── payment_verifier.py    # Verificador de pagamentos x402
    │   │   └── delegation_contract.py # Interação com AgentDelegation
    │   │
    │   ├── cache/             # Redis
    │   │   ├── redis_cache.py        # Cliente Redis genérico
    │   │   ├── redis_lua_client.py   # Executor de scripts Lua atômicos
    │   │   └── lua_scripts/          # Scripts Lua para Redis
    │   │       ├── reserve_quota.lua
    │   │       ├── rate_limit_check.lua
    │   │       └── idempotency_check.lua
    │   │
    │   ├── db/                # Banco de dados
    │   │   └── repositories/  # Implementações concretas dos repositórios
    │   │       ├── event_store.py        # PostgresEventStore (implementação)
    │   │       ├── snapshot_repo.py      # SnapshotRepository (implementação)
    │   │       └── api_key_repository.py # 🆕 APIKeyRepository (PostgreSQL + Redis cache)
    │   │
    │   └── messaging/         # Kafka
    │       ├── kafka_producer.py     # Produtor de eventos Kafka
    │       └── kafka_consumer.py     # Consumidor de eventos Kafka
    │
    ├── api/                   # 🎯 API LAYER (Interface com o mundo externo)
    │   ├── v1/
    │   │   ├── endpoints/     # Handlers HTTP
    │   │   │   ├── health.py      # GET /health
    │   │   │   ├── agents.py      # POST /agents/register, /delegate, etc.
    │   │   │   ├── consume.py     # POST /consume (x402)
    │   │   │   └── invoices.py    # GET /invoices
    │   │   │
    │   │   ├── middleware/    # Middleware HTTP
    │   │   │   └── rate_limit_middleware.py  # Rate limiting por IP/agente
    │   │   │
    │   │   └── schemas/       # Pydantic models (validação request/response)
    │   │       ├── agents.py
    │   │       ├── consume.py
    │   │       ├── health.py
    │   │       └── invoices.py
    │   │
    │   └── websocket/         # WebSocket para eventos em tempo real
    │       └── event_handler.py
    │
    ├── analytics/             # Queries analíticas
    │   ├── queries.py             # SQL queries para métricas de negócio
    │   └── timescale_queries.py   # Queries específicas TimescaleDB
    │
    └── scripts/               # Scripts de inicialização
        ├── db/init_db.py          # Inicialização do banco
        └── redis/init_redis.py    # Inicialização do Redis
```

### Domain Layer (DDD)

#### Agregados

Os agregados são a unidade de consistência transacional. Cada agregado:

1. **Produz eventos** quando seu estado muda
2. **Aplica eventos** para reconstruir seu estado (`_apply`)
3. **Mantém uma lista de mudanças** não persistidas (`_changes`)

**Exemplo: AgentAggregate**

```python
# backend/app/domain/aggregates/agent.py

class AgentAggregate:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.owner_address = None
        self.delegation_address = None
        self.delegation_active = False
        self.reputation_score = 100
        self.version = 0
        self._changes = []

    @staticmethod
    def register(agent_id, owner_address, delegation_address=None):
        """Factory method: cria um novo agente e produz AgentRegistered event."""
        agent = AgentAggregate(agent_id)
        event = AgentRegistered(agent_id, owner_address, delegation_address)
        agent._apply(event)
        agent._changes.append(event)
        return agent

    def delegate(self, delegate_address, expires_at):
        """Produz AgentDelegated event."""
        event = AgentDelegated(self.agent_id, delegate_address, expires_at)
        self._apply(event)
        self._changes.append(event)

    def _apply(self, event):
        """Reconstrói estado a partir de um evento."""
        if isinstance(event, AgentRegistered):
            self.owner_address = event.data["owner_address"]
        elif isinstance(event, AgentDelegated):
            self.delegation_address = event.data["delegate_address"]
            self.delegation_active = True
        self.version += 1
```

#### Eventos de Domínio

```python
# backend/app/domain/events/base.py

class DomainEvent:
    def __init__(self, aggregate_id: str, data: dict = None):
        self.event_id = str(uuid4())       # ID único
        self.aggregate_id = aggregate_id    # ID do agregado
        self.occurred_at = datetime.utcnow() # Timestamp
        self.data = data or {}              # Payload do evento

    def event_type(self) -> str:
        return self.__class__.__name__      # Ex: "AgentRegistered"
```

**Eventos existentes**:

| Evento | Agregado | Disparado por |
|--------|----------|---------------|
| `AgentRegistered` | Agent | `register_agent` |
| `AgentDelegated` | Agent | `delegate_agent` |
| `AgentDelegationRevoked` | Agent | `revoke_delegation` |
| `AgentReputationUpdated` | Agent | `update_reputation` |
| `BillingSessionStarted` | BillingSession | `consume_resource` |
| `ResourceConsumed` | BillingSession | `consume_resource` |
| `BillingSessionClosed` | BillingSession | `settle_invoice` |
| `BillingSessionSettled` | BillingSession | `settle_invoice` |
| `PaymentReceived` | Invoice | `settle_invoice` |
| `PaymentVerified` | Invoice | `settle_invoice` |
| `PaymentFailed` | Invoice | `settle_invoice` |
| `InvoiceGenerated` | Invoice | `settle_invoice` |
| `InvoicePaid` | Invoice | `settle_invoice` |
| `APIKeyCreated` | APIKey | `create_api_key` |
| `APIKeyRevoked` | APIKey | `revoke_api_key` |
| `APIKeyExpired` | APIKey | `expire_keys` (automático) |
| `APIKeyRotated` | APIKey | `rotate_api_key` |
| `APIKeyUsed` | APIKey | `validate_api_key` (auditoria) |

### APIKeyAggregate

**Arquivo**: `backend/app/domain/aggregates/api_key.py`

**Propósito**: Gerenciar chaves de API de agentes com event sourcing completo para auditoria.

**Eventos**:
| Evento | Disparado por | Payload |
|--------|---------------|---------|
| `APIKeyCreated` | `create()` | `{key_id, key_hash, expires_at, label}` |
| `APIKeyRevoked` | `revoke_key()` | `{key_id, reason}` |
| `APIKeyExpired` | `expire_keys()` | `{key_id}` |
| `APIKeyRotated` | `rotate_key()` | `{old_key_id, new_key_id, new_key_hash}` |
| `APIKeyUsed` | `record_usage()` | `{key_id, ip_address}` |

**Métodos principais**:
```python
class APIKeyAggregate:
    @staticmethod
    def create(agent_id, key_id, key_hash, expires_in_days=90, label="default")
    def revoke_key(key_id, reason="manual")
    def rotate_key(old_key_id, new_key_id, new_key_hash)
    def expire_keys()
    def is_valid(key_hash) -> bool
    def record_usage(key_id, ip_address=None)
    def active_keys() -> List[str]
```

**Exemplo de uso**:
```python
# Criar uma nova chave
aggregate = APIKeyAggregate.create("agent-123", "key_abc", "$2b$12$hash...")
await event_store.append_events("agent-123", aggregate.get_changes(), expected_version=0)

# Verificar se uma chave é válida
aggregate = APIKeyAggregate.rebuild("agent-123", events)
if aggregate.is_valid("$2b$12$hash..."):
    # Chave válida - prosseguir
    pass
```

### Como Adicionar um Novo Agregado

1. Criar o agregado em `backend/app/domain/aggregates/`
2. Criar os eventos em `backend/app/domain/events/`
3. Adicionar o event_type no mapper em `PostgresEventStore._row_to_event()`
4. Criar o command em `backend/app/application/commands/`
5. Criar o handler em `backend/app/application/handlers/command_handlers.py`
6. Criar o endpoint em `backend/app/api/v1/endpoints/`
7. Criar o schema em `backend/app/api/v1/schemas/`

---

## 5. Camada 3: Infraestrutura

### PostgreSQL (Event Store + API Keys)

**Arquivo**: `backend/app/infrastructure/db/repositories/event_store.py`

O `PostgresEventStore` implementa a interface `EventStore` usando PostgreSQL com coluna JSONB para os dados do evento.

**Schema** (Migration `001_initial_schema.py`):
```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    stream_id VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(stream_id, version)  -- Controle de concorrência otimista
);

CREATE INDEX idx_events_stream ON events(stream_id, version);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_aggregate ON events(aggregate_id);
CREATE INDEX idx_events_occurred ON events(occurred_at);
```

**Operações**:
- `append_events(stream_id, events, expected_version)` — Concorrência otimista via `expected_version`
- `load_stream(stream_id)` — Carrega todos os eventos de um stream
- `load_stream_from_version(stream_id, from_version)` — Carrega a partir de uma versão

### Redis (Cache + Rate Limiting + Idempotência)

**Arquivo**: `backend/app/infrastructure/cache/redis_lua_client.py`

Usa scripts Lua para operações atômicas no Redis:

| Script | Propósito | Chave |
|--------|-----------|-------|
| `reserve_quota.lua` | Reservar cota de recurso atomicamente | `quota:{agent_id}:{resource_type}` |
| `rate_limit_check.lua` | Token bucket para rate limiting | `rate_limit:{agent_id}:{resource_type}` |
| `idempotency_check.lua` | Check-and-set para idempotência | `idempotency:{key}` |

**Exemplo de script Lua** (`rate_limit_check.lua`):
```lua
-- Token Bucket Algorithm
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1] or max_tokens)
local last_refill = tonumber(bucket[2] or now)

local elapsed = math.max(0, now - last_refill)
tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

if tokens >= cost then
    redis.call('HMSET', key, 'tokens', tokens - cost, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) * 2)
    return 1  -- Allowed
else
    return 0  -- Rate limited
end
```

### Kafka (Event Streaming)

**Arquivos**:
- `kafka_producer.py` — Publica eventos no Kafka
- `kafka_consumer.py` — Consome eventos e executa side effects

**Tópicos** (8 tópicos, 3 partições cada):
```
agent.registered              → Novo agente registrado
agent.delegated               → Delegação criada
agent.reputation              → Reputação atualizada
billing.resource.consumed     → Recurso consumido
billing.session.settled       → Sessão finalizada
billing.invoice.generated     → Fatura gerada
billing.invoice.paid          → Fatura paga
payment.verified              → Pagamento verificado
```

### Blockchain (Web3)

**Arquivos**:
- `web3_client.py` — Cliente genérico (conexão, verificação de assinatura)
- `payment_verifier.py` — Interação com `PaymentVerifier.sol`
- `delegation_contract.py` — Interação com `AgentDelegation.sol`

**Configuração** (via `core/config.py`):
```python
RPC_URL_BASE = "https://sepolia.base.org"
AGENT_DELEGATION_ADDRESS = "0x..."  # Endereço do contrato AgentDelegation
PAYMENT_VERIFIER_ADDRESS = "0x..."  # Endereço do contrato PaymentVerifier
REPUTATION_SBT_ADDRESS = "0x..."    # Endereço do contrato ReputationSBT
```

---

## 6. Camada 4: Aplicação

### Commands

Commands são objetos imutáveis que representam uma intenção do usuário:

```python
# backend/app/application/commands/register_agent.py
@dataclass
class RegisterAgentCommand:
    agent_id: str
    owner_address: str
    delegation_address: Optional[str] = None

@dataclass
class DelegateAgentCommand:
    agent_id: str
    delegate_address: str
    expires_at: str
```

### Command Handlers

Handlers processam commands, carregam agregados do Event Store, executam a lógica de negócio, e persistem novos eventos:

```python
# backend/app/application/handlers/command_handlers.py

class CommandHandlers:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store

    async def handle_register_agent(self, command: RegisterAgentCommand):
        # 1. Verificar se agente já existe
        existing = await self._event_store.load_stream(command.agent_id)
        if existing:
            raise ValueError(f"Agent {command.agent_id} already exists")

        # 2. Criar agregado (produz eventos)
        aggregate = AgentAggregate.register(
            command.agent_id, command.owner_address, command.delegation_address,
        )

        # 3. Persistir eventos (concorrência otimista)
        await self._event_store.append_events(
            command.agent_id, aggregate.get_changes(), expected_version=0,
        )
```

### Event Handlers

Event handlers reagem a eventos para executar side effects (publicar no Kafka, enviar WebSocket, etc.):

```python
# backend/app/application/handlers/event_handlers.py

class EventHandlers:
    def __init__(self, kafka_producer, ws_handler):
        self._kafka = kafka_producer
        self._ws = ws_handler

    async def handle_agent_registered(self, event: AgentRegistered):
        await self._kafka.publish("agent.registered", event.to_dict())
        await self._ws.broadcast(event.to_dict())
```

---

## 7. Camada 5: API & WebSocket

### Endpoints REST

| Método | Rota | Handler | Descrição |
|--------|------|---------|-----------|
| `GET` | `/health` | `health_check` | Status dos serviços |
| `GET` | `/` | `root` | Informações da API |
| `POST` | `/api/v1/agents/register` | `register_agent` | Registrar novo agente |
| `POST` | `/api/v1/agents/delegate` | `delegate_agent` | Delegar autoridade |
| `POST` | `/api/v1/agents/revoke` | `revoke_delegation` | Revogar delegação |
| `POST` | `/api/v1/agents/reputation` | `update_reputation` | Atualizar reputação |
| `POST` | `/api/v1/consume` | `consume_resource` | Consumir recurso (x402) |
| `GET` | `/api/v1/invoices/{address}` | `get_invoice` | Obter fatura |
| `GET` | `/api/v1/invoices/{address}/pending` | `list_invoices` | Listar faturas pendentes |
| `POST` | `/api/v1/agents/{agent_id}/api-keys` | `create_api_key` | 🆕 Criar chave de API |
| `GET` | `/api/v1/agents/{agent_id}/api-keys` | `list_api_keys` | 🆕 Listar chaves de API |
| `POST` | `/api/v1/agents/{agent_id}/api-keys/{key_id}/revoke` | `revoke_api_key` | 🆕 Revogar chave |
| `POST` | `/api/v1/agents/{agent_id}/api-keys/{key_id}/rotate` | `rotate_api_key` | 🆕 Rotacionar chave |
| `WS` | `/ws` | `websocket_endpoint` | Eventos em tempo real |

### Schemas (Pydantic)

Schemas validam requests e responses:

```python
# backend/app/api/v1/schemas/consume.py
class ConsumeRequest(BaseModel):
    agent_address: str
    resource_type: str
    units: int = Field(gt=0, le=1000)
    tx_hash: str
    amount: str  # Wei como string

class ConsumeResponse(BaseModel):
    session_id: str
    status: str
    quota_remaining: int
```

**Schemas de API Keys** (`backend/app/api/v1/schemas/api_keys.py`):
```python
class CreateAPIKeyRequest(BaseModel):
    label: str = Field(default="default", max_length=100)
    expires_in_days: int = Field(default=90, ge=1, le=365)

class CreateAPIKeyResponse(BaseModel):
    key_id: str
    plain_key: str  # Mostrado apenas uma vez!
    expires_at: datetime
    label: str

class APIKeyResponse(BaseModel):
    key_id: str
    label: str
    is_active: bool
    is_revoked: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime

class RevokeAPIKeyRequest(BaseModel):
    reason: str = Field(default="manual", max_length=500)
```

### Middleware

**Rate Limit Middleware** (`rate_limit_middleware.py`):
- Limita requisições por IP/agente
- Usa Redis + Token Bucket
- Configurável via `max_requests` e `window`

**Security Middleware** (`security.py`) — 🆕:
- **OWASP Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- **Correlation ID**: Header `X-Correlation-ID` para rastreamento distribuído
- **Request Logging**: Log estruturado de todas as requisições (método, path, status, duração)

```python
# backend/app/api/v1/middleware/security.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response
```

### Autenticação com API Key

**Arquivo**: `backend/app/core/auth.py`

**Formato**: `X-API-Key: <key_id>.<plain_key>`

**Fluxo de validação**:
```
1. Extrair header X-API-Key
2. Parsear key_id.plain_key
3. Buscar hash no Redis (cache, TTL 5min) ou PostgreSQL
4. Verificar bcrypt (salt rounds: 12)
5. Carregar APIKeyAggregate do Event Store
6. Validar se chave não está revogada/expirada
7. Registrar uso (evento APIKeyUsed para auditoria)
8. Retornar agent_id
```

**Exemplo de uso em endpoints**:
```python
from app.core.auth import validate_api_key

@router.get("/api/v1/protected-resource")
async def get_protected_resource(
    agent_id: str = Depends(validate_api_key)
):
    return {"agent_id": agent_id, "data": "sensitive"}
```

### WebSocket

**Event Handler** (`event_handler.py`):
- Conexões WebSocket para streaming de eventos em tempo real
- Broadcast de eventos de domínio para todos os clientes conectados

---

## 8. Camada 6: Analytics & Monitoramento

### TimescaleDB

**Migration** (`002_analytics_views.py`):
- Cria hypertables para dados time-series
- Views materializadas para métricas agregadas

### Queries Analíticas

**Arquivo**: `backend/app/analytics/queries.py`

Queries SQL pré-definidas para métricas de negócio:

| Query | Descrição |
|-------|-----------|
| `revenue_by_agent(days)` | Receita total por agente |
| `resource_consumption_trends(interval, days)` | Tendências de consumo |
| `agent_activity_summary(days)` | Resumo de atividade dos agentes |
| `delegation_analytics(days)` | Métricas de delegação |
| `payment_success_rate(days)` | Taxa de sucesso de pagamentos |
| `top_agents_by_consumption(resource_type, days, limit)` | Top agentes por consumo |
| `daily_active_agents(days)` | Agentes ativos por dia |
| `billing_session_duration(days)` | Duração média das sessões |
| `invoice_summary(days)` | Resumo de faturas |

### Grafana Dashboards

**Arquivos** em `monitoring/grafana/dashboards/`:

| Dashboard | Métricas |
|-----------|----------|
| `agent-platform-overview.json` | Requisições/min, receita, agentes ativos, taxa de erro |
| `agent-platform-reconciliation.json` | Discrepâncias encontradas, alertas, histórico |
| `agent-platform-performance.json` | Latência Redis/PostgreSQL/Kafka, uso de memória |

---

## 9. Camada 7: Reconciliação

### Propósito

Garantir que o estado off-chain (PostgreSQL Event Store) esteja consistente com o estado on-chain (Blockchain).

### Scripts

```
scripts/reconciliation/
├── config.py                    # Configuração compartilhada
├── reconcile_payments.py        # Reconciliação de pagamentos x402
├── reconcile_delegations.py     # Reconciliação de delegações EIP-7702
├── reconcile_state_channels.py  # Reconciliação de state channels
└── refresh_views.py             # Atualização de views materializadas
```

### Fluxo de Reconciliação

```
1. Carregar eventos do PostgreSQL (Event Store)
2. Para cada evento, verificar estado correspondente na blockchain
3. Se discrepância encontrada:
   a. Registrar em reconciliation_reports/
   b. Disparar alerta (se configurado)
   c. Opcionalmente, corrigir automaticamente
4. Gerar relatório JSON + CSV
```

### Execução

```bash
# Manual
make reconcile

# Agendado (cron)
0 2 * * * cd /path/to/agent-platform && make reconcile >> /var/log/reconcile.log 2>&1
```

---

## 10. Camada 8: Simuladores & Testes

### Simuladores

```
agents/simulator/
├── agent_simulator.py        # Simula agentes consumindo recursos
├── delegation_simulator.py   # Simula delegações EIP-7702
└── payment_simulator.py      # Simula pagamentos x402
```

**Uso**:
```bash
make simulate-billing      # 10 agentes, 5 req/s, 60s
make simulate-delegations  # 5 agentes, 2 req/s, 60s
make simulate-payments     # 3 req/s, 10% falha, 60s
make simulate-all          # Todos em paralelo
```

### Testes

```bash
make test              # Todos os testes (94+ Python + 91+ Solidity)
make test-backend      # pytest + coverage (94 testes)
make test-contracts    # forge test (91+ testes)
make test-lua          # Testes de scripts Lua Redis
```

**Testes de API Key** (33 novos testes):

| Arquivo | Tipo | Quantidade | O que testa |
|---------|------|------------|-------------|
| `tests/unit/test_api_key_aggregate.py` | Unitário | 23 | Create, revoke, rotate, expire, validation, active_keys, record_usage, event sourcing |
| `tests/integration/test_auth.py` | Integração | 10 | Crypto (bcrypt), validação de header, key revogada/expirada, fluxo completo |

**Testes de Pix** (13 testes):

| Arquivo | Tipo | Quantidade | O que testa |
|---------|------|------------|-------------|
| `tests/integration/test_pix_client.py` | Integração | 13 | Inicialização, QR Code, check payment, list transactions, context manager |

---

## 11. Camada 9: DevOps & CI/CD

### Docker Compose

**Arquivo**: `docker-compose.yml`

**Serviços Core** (sempre ativos):
| Serviço | Imagem | Depende de |
|---------|--------|------------|
| `postgres` | postgres:15-alpine | — |
| `redis` | redis:7-alpine | — |
| `zookeeper` | cp-zookeeper:7.5.0 | — |
| `kafka` | cp-kafka:7.5.0 | zookeeper |
| `backend` | Dockerfile (./backend) | postgres, redis, kafka |
| `kafka-init` | cp-kafka:7.5.0 | kafka |

**Serviços Opcionais** (`--profile full`):
| Serviço | Imagem | Porta |
|---------|--------|-------|
| `timescaledb` | timescale/timescaledb:2.13-pg15 | 5433 |
| `prometheus` | prom/prometheus:v2.48.0 | 9090 |
| `grafana` | grafana/grafana:10.2.2 | 3000 |
| `kafka-ui` | provectuslabs/kafka-ui:v0.7.1 | 8080 |

### CI/CD (GitHub Actions)

**Arquivo**: `.github/workflows/ci.yml`

**Jobs**:
1. `validate-python` — Ruff linter + mypy + validador customizado
2. `validate-solidity` — Forge build + Forge test + validador customizado
3. `validate-docker` — Validação do docker-compose.yml

### Makefile

Comandos principais:
```bash
make up           # Iniciar serviços
make down         # Parar serviços
make test         # Rodar todos os testes
make reconcile    # Rodar reconciliação
make simulate-all # Rodar simuladores
make logs         # Ver logs
make clean        # Limpar tudo
```

---

## 12. Decisões Arquiteturais

Cada decisão arquitetural está documentada como um ADR (Architecture Decision Record) em `docs/adr/`:

| ADR | Decisão | Motivação |
|-----|---------|-----------|
| [ADR-001](docs/adr/ADR-001-payment-mechanism.md) | x402 Micropayments | Pagamentos on-chain por consumo, padrão Coinbase/Linux Foundation |
| [ADR-002](docs/adr/ADR-002-delegation-eip7702.md) | EIP-7702 Delegation | Delegação de autoridade com assinaturas EIP-712 |
| [ADR-003](docs/adr/ADR-003-event-sourcing-postgres.md) | Event Sourcing + PostgreSQL | Imutabilidade, audit trail, reconstrução de estado |
| [ADR-004](docs/adr/ADR-004-rate-limiting-redis.md) | Redis Lua Scripts | Operações atômicas para rate limiting e idempotência |

### Por que Event Sourcing?

1. **Audit Trail Completo**: Todo evento é imutável e registrado
2. **Reconstrução de Estado**: Qualquer estado pode ser reconstruído a qualquer momento
3. **Temporal Queries**: É possível saber o estado do sistema em qualquer ponto no tempo
4. **Integração com Kafka**: Eventos de domínio são naturalmente publicáveis no Kafka

### Por que CQRS?

1. **Separação de Responsabilidades**: Commands (escrita) vs Queries (leitura)
2. **Otimização Independente**: Cada lado pode ser otimizado separadamente
3. **Analytics sem Impacto**: Queries analíticas não afetam a escrita

### Por que Redis Lua Scripts?

1. **Atomicidade**: Operações complexas executadas atomicamente no Redis
2. **Performance**: Evita round-trips múltiplos cliente-servidor
3. **Consistência**: Token bucket, idempotência e reserva de cota em uma única operação

### Por que 3 Reconciliações?

1. **Pagamentos**: Garantir que faturas no Event Store correspondem a transações on-chain
2. **Delegações**: Verificar que delegações EIP-7702 estão consistentes
3. **State Channels**: Assegurar que aberturas/fechamentos de canais

---

## 13. Guia de Extensão

### Como Adicionar um Novo Endpoint

Siga este checklist para adicionar um novo endpoint seguindo os padrões existentes:

**Passo 1: Schema** (`backend/app/api/v1/schemas/`)
```python
# schemas/meu_recurso.py
from pydantic import BaseModel, Field

class MeuRecursoRequest(BaseModel):
    agent_id: str
    param1: str = Field(..., min_length=1, max_length=100)
    param2: int = Field(gt=0, le=1000)

class MeuRecursoResponse(BaseModel):
    id: str
    status: str
    result: dict
```

**Passo 2: Command** (`backend/app/application/commands/`)
```python
# commands/meu_recurso.py
from dataclasses import dataclass

@dataclass
class MeuRecursoCommand:
    agent_id: str
    param1: str
    param2: int
```

**Passo 3: Event** (`backend/app/domain/events/`)
```python
# events/meus_eventos.py
from app.domain.events.base import DomainEvent

class MeuRecursoExecutado(DomainEvent):
    def __init__(self, aggregate_id: str, resultado: str):
        super().__init__(aggregate_id, {"resultado": resultado})
```

**Passo 4: Agregado** (`backend/app/domain/aggregates/`)
```python
# aggregates/meu_recurso.py
from app.domain.events.meus_eventos import MeuRecursoExecutado

class MeuRecursoAggregate:
    def __init__(self, id: str):
        self.id = id
        self.resultado = None
        self.version = 0
        self._changes = []

    @staticmethod
    def executar(id: str, param1: str):
        aggregate = MeuRecursoAggregate(id)
        event = MeuRecursoExecutado(id, f"resultado_{param1}")
        aggregate._apply(event)
        aggregate._changes.append(event)
        return aggregate

    def _apply(self, event):
        if isinstance(event, MeuRecursoExecutado):
            self.resultado = event.data["resultado"]
        self.version += 1
```

**Passo 5: Handler** (`backend/app/application/handlers/command_handlers.py`)
```python
async def handle_meu_recurso(self, command: MeuRecursoCommand) -> str:
    aggregate = MeuRecursoAggregate.executar(command.agent_id, command.param1)
    await self._event_store.append_events(
        command.agent_id, aggregate.get_changes(), expected_version=0,
    )
    return aggregate.id
```

**Passo 6: Endpoint** (`backend/app/api/v1/endpoints/`)
```python
# endpoints/meu_recurso.py
from fastapi import APIRouter, Depends
from app.api.v1.schemas.meu_recurso import MeuRecursoRequest, MeuRecursoResponse
from app.application.commands.meu_recurso import MeuRecursoCommand

router = APIRouter()

@router.post("/meu-recurso", response_model=MeuRecursoResponse)
async def executar_meu_recurso(request: MeuRecursoRequest, handlers=Depends(get_handlers)):
    command = MeuRecursoCommand(agent_id=request.agent_id, param1=request.param1, param2=request.param2)
    result_id = await handlers.handle_meu_recurso(command)
    return MeuRecursoResponse(id=result_id, status="executed", result={})
```

**Passo 7: Registrar no main.py**
```python
# main.py
from app.api.v1.endpoints import meu_recurso
app.include_router(meu_recurso.router, prefix="/api/v1", tags=["meu_recurso"])
```

### Como Adicionar um Novo Contrato Solidity

1. Criar em `contracts/src/NovoContrato.sol`
2. Usar `forge-std` e `openzeppelin-contracts` como dependências
3. Criar script de deploy em `contracts/script/DeployNovoContrato.s.sol`
4. Criar testes em `contracts/test/NovoContrato.t.sol`
5. Adicionar interação no backend em `backend/app/infrastructure/blockchain/`
6. Adicionar endereço do contrato em `backend/app/core/config.py`

### Como Adicionar um Novo Script Lua Redis

1. Criar em `backend/app/infrastructure/cache/lua_scripts/novo_script.lua`
2. Adicionar no `RedisLuaClient.load_scripts()` em `redis_lua_client.py`
3. Criar método Python correspondente no `RedisLuaClient`
4. Usar o método nos handlers ou services

### Como Adicionar um Novo Tópico Kafka

1. Adicionar no `kafka-init` em `docker-compose.yml`
2. Publicar eventos usando `kafka_producer.publish(topic, event)`
3. Consumir eventos usando `kafka_consumer` com callback apropriado

---

## 14. Fluxos Completos

### Fluxo: Registro de Agente + Delegação

```
Agente (EOA)                    Backend                        Blockchain
     │                             │                              │
     │  POST /api/v1/agents/register                              │
     │  {address, signature}       │                              │
     │────────────────────────────▶│                              │
     │                             │  1. Verificar assinatura     │
     │                             │  2. Criar AgentAggregate     │
     │                             │  3. AgentRegistered event    │
     │                             │  4. Persistir no Event Store │
     │                             │  5. Publicar Kafka           │
     │                             │  6. Broadcast WebSocket      │
     │  201 {agent_id, status}     │                              │
     │◀────────────────────────────│                              │
     │                             │                              │
     │  POST /api/v1/agents/delegate                               │
     │  {agent, delegate, sig}     │                              │
     │────────────────────────────▶│                              │
     │                             │  1. Verificar EIP-712 sig    │
     │                             │  2. Carregar AgentAggregate  │
     │                             │  3. AgentDelegated event     │
     │                             │  4. Persistir no Event Store │
     │                             │  5. Chamar AgentDelegation   │
     │                             │     contract (se necessário) │
     │                             │─────────────────────────────▶│
     │                             │                              │
     │  200 {status: "delegated"}  │                              │
     │◀────────────────────────────│                              │
```

### Fluxo: Consumo de Recurso (x402)

```
Agente (EOA)                    Backend                    Redis           Blockchain
     │                             │                       │                  │
     │  POST /api/v1/consume       │                       │                  │
     │  {agent, resource,          │                       │                  │
     │   tx_hash, amount}          │                       │                  │
     │────────────────────────────▶│                       │                  │
     │                             │  1. Check idempotency │                  │
     │                             │──────────────────────▶│                  │
     │                             │  (idempotency:{hash}) │                  │
     │                             │◀──────────────────────│                  │
     │                             │                       │                  │
     │                             │  2. Check rate limit  │                  │
     │                             │──────────────────────▶│                  │
     │                             │  (rate_limit:{agent}) │                  │
     │                             │◀──────────────────────│                  │
     │                             │                       │                  │
     │                             │  3. Reserve quota     │                  │
     │                             │──────────────────────▶│                  │
     │                             │  (quota:{agent}:llm)  │                  │
     │                             │◀──────────────────────│                  │
     │                             │                       │                  │
     │                             │  4. Verify x402       │                  │
     │                             │   payment on-chain    │                  │
     │                             │─────────────────────────────────────────▶│
     │                             │                       │                  │
     │                             │  5. Create billing    │                  │
     │                             │   session (Event Store)│                 │
     │                             │                       │                  │
     │                             │  6. Publish Kafka     │                  │
     │                             │   (billing.resource   │                  │
     │                             │    .consumed)         │                  │
     │                             │                       │                  │
     │  200 {session_id,           │                       │                  │
     │       quota_remaining}      │                       │                  │
     │◀────────────────────────────│                       │                  │
```

### Fluxo: Reconciliação de Pagamentos

```
Schedule (cron)          Reconciliation Script          PostgreSQL          Blockchain
     │                             │                       │                  │
     │  make reconcile             │                       │                  │
     │────────────────────────────▶│                       │                  │
     │                             │  1. Load events       │                  │
     │                             │   (PaymentVerified)   │                  │
     │                             │──────────────────────▶│                  │
     │                             │◀──────────────────────│                  │
     │                             │                       │                  │
     │                             │  2. For each event:   │                  │
     │                             │   Check tx_hash       │                  │
     │                             │   on-chain            │                  │
     │                             │─────────────────────────────────────────▶│
     │                             │◀─────────────────────────────────────────│
     │                             │                       │                  │
     │                             │  3. If discrepancy:   │                  │
     │                             │   a. Log warning      │                  │
     │                             │   b. Generate report  │                  │
     │                             │   c. (Optional) fix   │                  │
     │                             │                       │                  │
     │  Report generated           │                       │                  │
     │◀────────────────────────────│                       │                  │
```

### Fluxo: CI/CD Pipeline

```
Push to main
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions                            │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ validate-python  │  │ validate-solidity│  │validate-docker│
│  │                  │  │                  │  │             │ │
│  │ - Ruff linter    │  │ - forge build   │  │ - docker    │ │
│  │ - mypy types     │  │ - forge test    │  │   compose    │ │
│  │ - pytest         │  │ - validate_sol  │  │   validate  │ │
│  │ - validate_py    │  │                  │  │             │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬──────┘ │
│           │                     │                    │        │
│           └─────────────────────┴────────────────────┘        │
│                                 │                             │
│                          All passed?                          │
│                                 │                             │
│                          [Deploy]                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 15. Camada 10: Conformidade e Regulatório (KYC/AML)

### Propósito

Tornar a plataforma elegível para operar no **sandbox regulatório da CVM** (prorrogado até 2026) e atender requisitos do BACEN (Banco Central) e COAF (Conselho de Controle de Atividades Financeiras), conforme Resolução CVM 88.

### Estrutura

```
backend/app/
├── domain/
│   ├── aggregates/
│   │   ├── kyc_profile.py         # 🆕 Agregado de perfil KYC
│   │   └── compliance_check.py    # 🆕 Agregado de verificações de compliance
│   │
│   └── events/
│       └── compliance_events.py   # 🆕 Eventos de compliance
│
├── infrastructure/
│   ├── compliance/                # 🆕 Integrações de compliance
│   │   ├── serpro_client.py       # Validação CPF/CNPJ (API Serpro)
│   │   ├── unico_client.py        # Biometria facial (Unico ID)
│   │   └── chainalysis_client.py  # AML on-chain (Chainalysis)
│   │
│   └── regulatory/                # 🆕 Relatórios regulatórios
│       ├── cvm_reporter.py        # Relatórios CVM (Resolução 88)
│       └── coaf_reporter.py       # Relatórios COAF (>R$ 10k)
│
├── analytics/
│   └── regulatory_reports.py      # 🆕 Queries para relatórios regulatórios
│
└── api/v1/
    ├── endpoints/
    │   └── compliance.py          # 🆕 Endpoints de KYC/AML
    │
    └── schemas/
        └── compliance.py          # 🆕 Schemas de compliance
```

```
contracts/src/
└── compliance/
    ├── ComplianceVerifier.sol     # 🆕 Verificação de KYC on-chain
    └── RegulatedAssetToken.sol    # 🆕 Token ERC-20 com whitelist KYC
```

### Detalhamento dos Componentes

#### `KYCProfile` Aggregate

**Arquivo**: `backend/app/domain/aggregates/kyc_profile.py`

**Propósito**: Gerenciar o perfil de identidade e conformidade de um agente.

**Campos**:
```python
class KYCProfile:
    profile_id: str               # UUID
    agent_id: str                 # Referência ao agente
    document_type: str            # "CPF" | "CNPJ"
    document_number: str          # Número do documento
    full_name: str                # Nome completo / Razão social
    email: str                    # Email de contato
    phone: str                    # Telefone
    address: dict                 # Endereço completo
    risk_score: str               # "low" | "medium" | "high"
    verification_status: str      # "pending" | "approved" | "rejected" | "suspended"
    verified_at: datetime         # Data de aprovação
    aml_checks: List[dict]        # Lista de verificações AML
    version: int
    _changes: List[DomainEvent]
```

**Eventos**:
```python
KYCProfileCreated         # Perfil KYC iniciado
KYCDocumentSubmitted      # Documento enviado
KYCBiometrySubmitted      # Biometria enviada
KYCApproved               # KYC aprovado
KYCRejected               # KYC rejeitado
KYCSuspended              # KYC suspenso (atividade suspeita)
AMLCheckCompleted         # Verificação AML concluída
AMLAlertTriggered         # Alerta AML disparado (transação suspeita)
```

#### Integrações de Compliance

##### Serpro Client (Validação CPF/CNPJ)

**Arquivo**: `backend/app/infrastructure/compliance/serpro_client.py`

**API**: https://apigateway.serpro.gov.br/

**Funcionalidades**:
- Validação de CPF (existência e regularidade)
- Validação de CNPJ (existência, situação cadastral)
- Consulta de dados básicos (nome, data de nascimento)

**Exemplo de uso**:
```python
class SerproClient:
    async def validate_cpf(self, cpf: str) -> dict:
        # POST /consulta-cpf/v1/cpf/{cpf}
        # Retorna: {"nome": "...", "situacao": "REGULAR", "data_nascimento": "..."}
        pass

    async def validate_cnpj(self, cnpj: str) -> dict:
        # GET /consulta-cnpj/v2/cnpj/{cnpj}
        # Retorna: {"razao_social": "...", "situacao": "ATIVA", ...}
        pass
```

**Custo**: ~R$ 0,10 por consulta

##### Unico Client (Biometria Facial)

**Arquivo**: `backend/app/infrastructure/compliance/unico_client.py`

**Funcionalidades**:
- Verificação de biometria facial (liveness detection)
- Comparação com foto do documento
- Prova de vida

**Exemplo de uso**:
```python
class UnicoClient:
    async def verify_face(self, selfie_base64: str, document_photo_base64: str) -> dict:
        # POST /v1/face-match
        # Retorna: {"match": true, "confidence": 0.98}
        pass
```

**Custo**: ~R$ 0,50 por verificação

##### Chainalysis Client (AML On-Chain)

**Arquivo**: `backend/app/infrastructure/compliance/chainalysis_client.py`

**Funcionalidades**:
- Rastreamento de endereços Ethereum suspeitos
- Identificação de origem de fundos (exchange, mixer, etc.)
- Alertas de risco (sanções, ransomware, etc.)

**Exemplo de uso**:
```python
class ChainalysisClient:
    async def check_address(self, address: str) -> dict:
        # GET /v1/address/{address}
        # Retorna: {"risk": "low", "source": "exchange", "alerts": []}
        pass
```

**Custo**: ~US$ 500/mês (plano básico)

#### Relatórios Regulatórios

##### CVM Reporter (Resolução 88)

**Arquivo**: `backend/app/infrastructure/regulatory/cvm_reporter.py`

**Relatórios Obrigatórios**:

1. **Posição Consolidada de Ativos Tokenizados** (mensal)
   - Formato: CSV
   - Campos: CNPJ emissor, tipo ativo, quantidade, valor, custódia

2. **Transações Suspeitas (COAF)** (tempo real se > R$ 10k)
   - Formato: XML (padrão COAF)
   - Envio: API COAF

3. **Relatório de Custódia** (diário)
   - Formato: JSON
   - Conteúdo: Saldos de ativos por investidor

4. **Relatório de Operações** (trimestral)
   - Formato: PDF
   - Conteúdo: Volume transacionado, fees, etc.

**Exemplo**:
```python
class CVMReporter:
    async def generate_consolidated_position(self, month: int, year: int) -> str:
        """Gera relatório mensal de posição consolidada."""
        # Query TimescaleDB/PostgreSQL
        # Exporta CSV conforme formato CVM
        return "path/to/report.csv"
```

#### ComplianceVerifier Smart Contract

**Arquivo**: `contracts/src/compliance/ComplianceVerifier.sol`

**Propósito**: Verificação on-chain se um agente está aprovado para operar.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ComplianceVerifier {
    struct KYCRecord {
        bool approved;
        bool suspended;
        uint256 approvedAt;
        uint256 expiresAt;
        string tier; // "basic" | "advanced" | "institutional"
    }

    mapping(address => KYCRecord) public kycRegistry;
    address public admin;

    event KYCApproved(address indexed agent, uint256 expiresAt, string tier);
    event KYCSuspended(address indexed agent, string reason);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin");
        _;
    }

    function approveKYC(address _agent, uint256 _expiresAt, string memory _tier) 
        external onlyAdmin {
        kycRegistry[_agent] = KYCRecord({
            approved: true,
            suspended: false,
            approvedAt: block.timestamp,
            expiresAt: _expiresAt,
            tier: _tier
        });
        emit KYCApproved(_agent, _expiresAt, _tier);
    }

    function suspendKYC(address _agent, string memory _reason) 
        external onlyAdmin {
        kycRegistry[_agent].suspended = true;
        emit KYCSuspended(_agent, _reason);
    }

    function canOperate(address _agent) public view returns (bool) {
        KYCRecord memory record = kycRegistry[_agent];
        return record.approved && 
               !record.suspended && 
               record.expiresAt > block.timestamp;
    }
}
```

**Integração**: O `PaymentVerifier.sol` será modificado para chamar `ComplianceVerifier.canOperate()` antes de aceitar pagamentos.

### Como Adicionar um Novo Check de Compliance

1. Criar evento em `compliance_events.py`
2. Adicionar método no agregado `KYCProfile`
3. Criar integração em `infrastructure/compliance/`
4. Adicionar handler em `command_handlers.py`
5. Criar endpoint em `api/v1/endpoints/compliance.py`
6. Atualizar `ComplianceVerifier.sol` se necessário

### Fluxo: Onboarding com KYC

```
Usuário          Backend                Serpro/Unico         ComplianceVerifier
   │                │                        │                       │
   │  POST /kyc/start                        │                       │
   │  {cpf, name}   │                        │                       │
   │───────────────▶│                        │                       │
   │                │  Validate CPF          │                       │
   │                │───────────────────────▶│                       │
   │                │◀───────────────────────│                       │
   │                │  (nome, situação)      │                       │
   │                │                        │                       │
   │  200 {token}   │                        │                       │
   │◀───────────────│                        │                       │
   │                │                        │                       │
   │  POST /kyc/biometry                     │                       │
   │  {selfie}      │                        │                       │
   │───────────────▶│                        │                       │
   │                │  Verify face           │                       │
   │                │───────────────────────▶│                       │
   │                │◀───────────────────────│                       │
   │                │  (match: true, 98%)    │                       │
   │                │                        │                       │
   │                │  KYCApproved event     │                       │
   │                │                        │                       │
   │                │  approveKYC(address)   │                       │
   │                │───────────────────────────────────────────────▶│
   │                │                        │                       │
   │  200 {approved}│                        │                       │
   │◀───────────────│                        │                       │
```

---

## 16. Camada 11: Integração com Sistema Financeiro Brasileiro

### Propósito

Viabilizar liquidação financeira em **BRL fiduciário** (Pix) e **BRL digital** (stablecoins privadas futuras), integrando a plataforma ao sistema financeiro nacional via Open Finance.

### Estrutura

```
backend/app/
├── infrastructure/
│   ├── payments/                  # 🆕 Integrações de pagamento
│   │   ├── pix_client.py          # Cliente Pix (Stark Bank / Celcoin)
│   │   ├── pix_webhook.py         # Webhook de confirmação Pix
│   │   └── pix_reconciliation.py  # Reconciliação Pix ↔ Event Store
│   │
│   └── openfinance/               # 🆕 Open Finance (Resolução BCB)
│       ├── consent_manager.py     # Gerenciamento de consentimentos
│       └── account_client.py      # Consulta de dados bancários
│
└── api/v1/
    └── endpoints/
        ├── pix.py                 # 🆕 Endpoints de pagamento Pix
        └── openfinance.py         # 🆕 Endpoints Open Finance
```

```
contracts/src/
└── settlements/
    ├── StablecoinBridge.sol       # 🆕 Interface para stablecoins
    └── PixSettlement.sol          # 🆕 Liquidação híbrida Pix + blockchain
```

### Detalhamento dos Componentes

#### Pix Client (Stark Bank)

**Arquivo**: `backend/app/infrastructure/payments/pix_client.py`

**Funcionalidades**:
- Gerar QR Code Pix dinâmico
- Consultar status de pagamento
- Receber webhook de confirmação
- Listar transações

**Exemplo de uso**:
```python
class PixClient:
    def __init__(self, api_key: str, environment: str = "sandbox"):
        self.api_key = api_key
        self.base_url = "https://sandbox.api.starkbank.com/v2" if environment == "sandbox" else "https://api.starkbank.com/v2"

    async def create_qr_code(self, amount: Decimal, description: str, payer_name: str) -> dict:
        """Gera QR Code Pix dinâmico."""
        # POST /dynamic-brcode
        # Retorna: {"id": "...", "qr_code": "00020126...", "url": "https://..."}
        pass

    async def check_payment(self, qr_code_id: str) -> dict:
        """Verifica se pagamento foi recebido."""
        # GET /dynamic-brcode/{id}
        # Retorna: {"status": "paid", "amount": 1000, "payer": {...}}
        pass
```

**Webhook**:
```python
# backend/app/api/v1/endpoints/pix.py

@router.post("/webhooks/pix")
async def pix_webhook(event: dict, signature: str = Header(...)):
    # 1. Validar assinatura HMAC
    # 2. Processar evento (payment.created, payment.paid)
    # 3. Atualizar Event Store (PixPaymentReceived event)
    # 4. Liberar recurso para o agente
    pass
```

**Custo**: ~1% por transação Pix

#### Open Finance Client

**Arquivo**: `backend/app/infrastructure/openfinance/consent_manager.py`

**Conformidade**: Resolução Conjunta nº 1 (BCB + CMN)

**Funcionalidades**:
- Solicitar consentimento do usuário (OAuth2)
- Buscar dados de contas bancárias
- Validar capacidade de pagamento

**Fluxo OAuth2**:
```
1. Backend redireciona usuário para banco
2. Usuário autoriza compartilhamento de dados
3. Backend recebe authorization_code
4. Backend troca por access_token
5. Backend consulta dados bancários
```

**Exemplo**:
```python
class OpenFinanceClient:
    async def request_consent(self, user_id: str, scopes: List[str]) -> str:
        """Inicia fluxo de consentimento."""
        # Redireciona para: https://banco.com/oauth/authorize?scope=accounts,transactions
        pass

    async def get_accounts(self, access_token: str) -> List[dict]:
        """Lista contas bancárias do usuário."""
        # GET /open-banking/accounts/v1/accounts
        # Retorna: [{"accountId": "...", "balance": {...}}]
        pass
```

#### StablecoinBridge Smart Contract

**Arquivo**: `contracts/src/settlements/StablecoinBridge.sol`

**Propósito**: Interface genérica para múltiplos emissores de stablecoins (USDC, BRZ, Drex futuro).

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IStablecoinProvider {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract StablecoinBridge {
    mapping(string => address) public providers; // "USDC" => 0x..., "BRZ" => 0x...
    address public admin;

    event ProviderRegistered(string indexed symbol, address provider);
    event SettlementExecuted(address indexed agent, string symbol, uint256 amount);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin");
        _;
    }

    constructor() {
        admin = msg.sender;
    }

    function registerProvider(string memory _symbol, address _provider) 
        external onlyAdmin {
        providers[_symbol] = _provider;
        emit ProviderRegistered(_symbol, _provider);
    }

    function settle(string memory _symbol, address _agent, uint256 _amount) 
        external {
        address provider = providers[_symbol];
        require(provider != address(0), "Provider not registered");

        IStablecoinProvider(provider).transfer(_agent, _amount);
        emit SettlementExecuted(_agent, _symbol, _amount);
    }
}
```

### Fluxo: Pagamento Híbrido (Pix + x402)

```
Agente          Backend           Stark Bank         Blockchain
   │               │                   │                  │
   │  POST /consume                    │                  │
   │  (sem tx_hash) │                  │                  │
   │───────────────▶│                  │                  │
   │                │  Gera QR Code Pix│                  │
   │                │─────────────────▶│                  │
   │                │◀─────────────────│                  │
   │  200 {qr_code} │                  │                  │
   │◀───────────────│                  │                  │
   │                │                  │                  │
   │  [Paga Pix]    │                  │                  │
   │───────────────────────────────────▶│                  │
   │                │                  │                  │
   │                │  Webhook (paid)  │                  │
   │                │◀─────────────────│                  │
   │                │                  │                  │
   │                │  PixPaymentReceived event           │
   │                │  (Event Store)   │                  │
   │                │                  │                  │
   │                │  Libera recurso  │                  │
   │                │  para agente     │                  │
   │                │                  │                  │
   │                │  [Opcional] Batch settlement        │
   │                │  on-chain (fim do dia)              │
   │                │─────────────────────────────────────▶│
```

---

## 17. Camada 12: Governança Institucional e LGPD

### Propósito

Implementar controles de governança empresarial (multi-sig, auditoria) e conformidade com LGPD (Lei Geral de Proteção de Dados - Lei 13.709/2018).

### Estrutura

```
backend/app/
├── infrastructure/
│   ├── gdpr/                      # 🆕 Conformidade LGPD
│   │   ├── gdpr_manager.py        # Anonimização e data retention
│   │   └── data_export.py         # Portabilidade de dados
│   │
│   └── governance/                # 🆕 Governança
│       ├── audit_logger.py        # Log de auditoria
│       └── access_control.py      # Controle de acesso (RBAC)
│
└── analytics/
    └── audit_queries.py           # 🆕 Queries de auditoria
```

```
contracts/src/
└── governance/
    ├── MultiSigController.sol     # 🆕 Multi-sig para operações críticas
    └── TimelockController.sol     # 🆕 Timelock para upgrades
```

```
docs/business/
├── TCO_CALCULATOR.md              # 🆕 Calculadora de ROI
└── COMPLIANCE_MATRIX.md           # 🆕 Matriz de conformidade
```

### Multi-Sig Controller

**Arquivo**: `contracts/src/governance/MultiSigController.sol`

**Propósito**: Requer múltiplas assinaturas (3/5) para operações críticas.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MultiSigController {
    address[] public signers;
    uint256 public requiredSignatures = 3;
    
    struct Transaction {
        address target;
        uint256 value;
        bytes data;
        uint256 confirmations;
        bool executed;
        mapping(address => bool) confirmed;
    }

    mapping(uint256 => Transaction) public transactions;
    uint256 public transactionCount;

    event TransactionSubmitted(uint256 indexed txId, address indexed target);
    event TransactionConfirmed(uint256 indexed txId, address indexed signer);
    event TransactionExecuted(uint256 indexed txId);

    modifier onlySigner() {
        bool isSigner = false;
        for (uint i = 0; i < signers.length; i++) {
            if (signers[i] == msg.sender) isSigner = true;
        }
        require(isSigner, "Not a signer");
        _;
    }

    function submitTransaction(address _target, uint256 _value, bytes memory _data) 
        external onlySigner returns (uint256) {
        uint256 txId = transactionCount++;
        Transaction storage txn = transactions[txId];
        txn.target = _target;
        txn.value = _value;
        txn.data = _data;
        
        emit TransactionSubmitted(txId, _target);
        confirmTransaction(txId);
        return txId;
    }

    function confirmTransaction(uint256 _txId) public onlySigner {
        Transaction storage txn = transactions[_txId];
        require(!txn.executed, "Already executed");
        require(!txn.confirmed[msg.sender], "Already confirmed");

        txn.confirmed[msg.sender] = true;
        txn.confirmations++;

        emit TransactionConfirmed(_txId, msg.sender);

        if (txn.confirmations >= requiredSignatures) {
            executeTransaction(_txId);
        }
    }

    function executeTransaction(uint256 _txId) internal {
        Transaction storage txn = transactions[_txId];
        require(!txn.executed, "Already executed");
        require(txn.confirmations >= requiredSignatures, "Not enough confirmations");

        txn.executed = true;
        (bool success,) = txn.target.call{value: txn.value}(txn.data);
        require(success, "Transaction failed");

        emit TransactionExecuted(_txId);
    }
}
```

### LGPD Manager

**Arquivo**: `backend/app/infrastructure/gdpr/gdpr_manager.py`

**Funcionalidades**:
- **Right to be Forgotten**: Remover/anonimizar dados de um agente
- **Data Portability**: Exportar todos os dados em formato legível (JSON)
- **Data Retention**: Anonimizar eventos com PII após 5 anos (LGPD Art. 16)

```python
class GDPRManager:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store

    async def anonymize_agent(self, agent_id: str) -> None:
        """Anonimiza dados de um agente (direito ao esquecimento)."""
        # 1. Carregar todos os eventos do agente
        events = await self._event_store.load_stream(agent_id)
        
        # 2. Para cada evento com PII, substituir por dados anônimos
        for event in events:
            if self._contains_pii(event):
                event.data = {"anonymized": True, "reason": "GDPR_request"}
                await self._event_store.update_event(event)

    async def export_agent_data(self, agent_id: str) -> dict:
        """Exporta todos os dados de um agente (portabilidade)."""
        events = await self._event_store.load_stream(agent_id)
        return {
            "agent_id": agent_id,
            "events": [e.to_dict() for e in events],
            "exported_at": datetime.utcnow().isoformat()
        }

    async def apply_retention_policy(self) -> int:
        """Aplica política de retenção (anonimiza eventos >5 anos)."""
        cutoff_date = datetime.utcnow() - timedelta(days=5*365)
        expired_events = await self._event_store.get_events_before(cutoff_date)
        
        count = 0
        for event in expired_events:
            if self._contains_pii(event):
                event.data = {"anonymized": True, "reason": "retention_policy"}
                await self._event_store.update_event(event)
                count += 1
        
        return count
```

### TCO Calculator

**Arquivo**: `docs/business/TCO_CALCULATOR.md`

**Conteúdo**: Calculadora de ROI (Return on Investment) para apresentar a CFOs.

```markdown
# TCO Calculator — Agent Platform para Bancos

## Cenário: Banco de Grande Porte

### Custos Atuais (Infraestrutura Legada)

| Item | Custo Anual |
|------|-------------|
| Equipe de Compliance (10 FTEs) | R$ 2.000.000 |
| Infraestrutura de Reconciliação | R$ 800.000 |
| Auditoria Externa | R$ 500.000 |
| Multas por Discrepâncias (~2% ao ano) | R$ 300.000 |
| **TOTAL** | **R$ 3.600.000** |

### Custos Projetados (Agent Platform)

| Item | Custo Anual |
|------|-------------|
| Assinatura Platform (R$ 20k/mês x 12) | R$ 240.000 |
| Taxa sobre Volume (0,5% de R$ 100M) | R$ 500.000 |
| Equipe Reduzida (3 FTEs) | R$ 600.000 |
| Infra Cloud (AWS/Azure) | R$ 200.000 |
| **TOTAL** | **R$ 1.540.000** |

### Economia e ROI

| Métrica | Valor |
|---------|-------|
| **Economia Anual** | **R$ 2.060.000** (57%) |
| **Investimento Inicial** (PoC + integração) | R$ 500.000 |
| **Payback Period** | **3 meses** |
| **ROI em 12 meses** | **312%** |

### Benefícios Intangíveis

- ✅ Zero discrepâncias (vs. 2% com sistema legado)
- ✅ Conformidade CVM/BACEN automática
- ✅ Redução de 80% no tempo de onboarding (KYC)
- ✅ Relatórios regulatórios em tempo real
```

---

## 18. Roadmap de Adaptação ao Mercado Brasileiro (90 Dias)

### Visão Geral

Este roadmap detalha a implementação dos 3 pilares estratégicos para adaptação ao mercado financeiro brasileiro:

| Pilar | ARR Habilitado | Prioridade | Duração |
|-------|----------------|------------|---------|
| **Pilar 1: Facilitador x402** | R$ 20M - R$ 30M | 🔥 Alta | 30 dias |
| **Pilar 2: Tokenização + Compliance** | R$ 2,2M - R$ 15M | 🔥 Alta | 45 dias |
| **Pilar 3: Agentes as a Service** | R$ 1,2M | Média | 60 dias |

### Sprint 1-2: Facilitador x402 (Semanas 1-4)

**Objetivo**: Processar R$ 1M em volume de testes com 100% de reconciliação.

#### Semana 1: Integração Pix

**Entregas**:
- [ ] `backend/app/infrastructure/payments/pix_client.py`
- [ ] Conta Stark Bank Sandbox
- [ ] Testes: Gerar QR Code Pix

**Testes**:
```bash
pytest tests/integration/test_pix_client.py
```

#### Semana 2: Webhook e Reconciliação

**Entregas**:
- [ ] `backend/app/api/v1/endpoints/pix.py` (webhook)
- [ ] `PixPaymentReceived` event
- [ ] Reconciliação Pix ↔ Event Store

**Fluxo de Teste**:
1. Gerar QR Code via API
2. Pagar via Pix (sandbox)
3. Webhook confirma pagamento
4. Event Store atualizado
5. Script de reconciliação valida

#### Semana 3: Dashboard x402

**Entregas**:
- [ ] `monitoring/grafana/dashboards/x402-facilitator.json`
- [ ] Métricas: Volume processado, taxa de sucesso, latência

#### Semana 4: Testes de Carga

**Entregas**:
- [ ] Simulador: 10k transações Pix
- [ ] Validação: 100% de reconciliação

### Sprint 3-4: Tokenização + Compliance (Semanas 5-8)

**Objetivo**: Tokenizar 1 ativo real (R$ 10M) com KYC completo.

#### Semana 5: Módulo KYC

**Entregas**:
- [ ] `backend/app/domain/aggregates/kyc_profile.py`
- [ ] `backend/app/infrastructure/compliance/serpro_client.py`
- [ ] Integração Serpro (validação CPF)

#### Semana 6: Biometria e AML

**Entregas**:
- [ ] `backend/app/infrastructure/compliance/unico_client.py`
- [ ] `backend/app/infrastructure/compliance/chainalysis_client.py`
- [ ] Fluxo completo de KYC (CPF + biometria)

#### Semana 7: Smart Contract Regulado

**Entregas**:
- [ ] `contracts/src/compliance/ComplianceVerifier.sol`
- [ ] `contracts/src/compliance/RegulatedAssetToken.sol`
- [ ] Testes Foundry (forge test)

#### Semana 8: Relatórios CVM

**Entregas**:
- [ ] `backend/app/infrastructure/regulatory/cvm_reporter.py`
- [ ] Relatório de Posição Consolidada (CSV)
- [ ] Relatório COAF (XML)

### Sprint 5-6: Agentes as a Service (Semanas 9-12)

**Objetivo**: 1 cliente piloto pagando R$ 20k/mês por 3 meses.

#### Semana 9: Agent Marketplace

**Entregas**:
- [ ] `backend/app/api/v1/endpoints/agent_marketplace.py`
- [ ] Catálogo: 3 agentes pré-configurados
  - Agente de Rebalanceamento de Portfólio
  - Agente de Monitoramento de Liquidez
  - Agente de Alertas de Compliance

#### Semana 10: Multi-tenancy

**Entregas**:
- [ ] `backend/app/infrastructure/isolation/tenant_manager.py`
- [ ] Namespace isolado por cliente (Redis, Kafka, PostgreSQL)

#### Semana 11: Billing por Tokens

**Entregas**:
- [ ] `backend/app/domain/aggregates/agent_billing.py`
- [ ] Modelo: R$ 20k base + R$ 0,01 por 1k tokens

#### Semana 12: Governança

**Entregas**:
- [ ] `contracts/src/governance/MultiSigController.sol`
- [ ] `backend/app/infrastructure/gdpr/gdpr_manager.py`
- [ ] Política de retenção LGPD (5 anos)

### Demo Day (Semana 13)

**Entregáveis**:
- [ ] Pitch Deck (10 slides)
- [ ] Vídeo Demo (3 minutos)
- [ ] TCO Calculator (Excel)
- [ ] PoC funcionando em produção (sandbox)

**Agenda**:
1. Apresentação para CTO/CFO do Itaú
2. Demo ao vivo: Pix → KYC → Tokenização → Reconciliação
3. Apresentação de métricas reais
4. Discussão de piloto (3 meses)

### Métricas de Sucesso

| Métrica | Meta |
|---------|------|
| Volume Pix Processado | R$ 1M |
| Taxa de Reconciliação | 100% |
| KYCs Aprovados | 50+ |
| Ativos Tokenizados | 1 (R$ 10M) |
| Relatórios CVM Gerados | 3 (mensal, COAF, custódia) |
| Clientes Piloto (Agentes as a Service) | 1 |

---

## 19. Fluxos Estendidos para Mercado Financeiro

### Fluxo: Onboarding Completo com KYC + Pix + Tokenização

```
Cliente          Backend              Serpro/Unico         Stark Bank         Blockchain
   │                │                     │                    │                  │
   │  POST /kyc/start                     │                    │                  │
   │  {cpf, name}   │                     │                    │                  │
   │───────────────▶│                     │                    │                  │
   │                │  Validate CPF       │                    │                  │
   │                │────────────────────▶│                    │                  │
   │                │◀────────────────────│                    │                  │
   │                │  (nome, situação)   │                    │                  │
   │                │                     │                    │                  │
   │  200 {token}   │                     │                    │                  │
   │◀───────────────│                     │                    │                  │
   │                │                     │                    │                  │
   │  POST /kyc/biometry                  │                    │                  │
   │  {selfie}      │                     │                    │                  │
   │───────────────▶│                     │                    │                  │
   │                │  Verify face        │                    │                  │
   │                │────────────────────▶│                    │                  │
   │                │◀────────────────────│                    │                  │
   │                │  (match: 98%)       │                    │                  │
   │                │                     │                    │                  │
   │                │  KYCApproved event  │                    │                  │
   │                │                     │                    │                  │
   │                │  approveKYC()       │                    │                  │
   │                │───────────────────────────────────────────────────────────▶│
   │                │                     │                    │                  │
   │  POST /consume (Pix)                 │                    │                  │
   │  {resource, units}                   │                    │                  │
   │───────────────▶│                     │                    │                  │
│                │  Check KYC (canOperate)                  │                  │
│                │───────────────────────────────────────────────────────────▶│
│                │                     │                    │                  │
│                │  Gera QR Code Pix   │                    │                  │
│                │─────────────────────────────────────────▶│                  │
│                │                     │                    │                  │
│  200 {qr_code} │                     │                    │                  │
│◀───────────────│                     │                    │                  │
│                │                     │                    │                  │
│  [Paga Pix]    │                     │                    │                  │
│──────────────────────────────────────────────────────────▶│                  │
│                │                     │                    │                  │
│                │  Webhook (paid)     │                    │                  │
│                │◀─────────────────────────────────────────│                  │
│                │                     │                    │                  │
│                │  PixPaymentReceived event                │                  │
│                │  (Event Store)      │                    │                  │
│                │                     │                    │                  │
│                │  Libera recurso     │                    │                  │
│                │  para agente        │                    │                  │
│                │                     │                    │                  │
│                │  [Opcional] Tokeniza ativo               │                  │
│                │  (RegulatedAssetToken)                   │                  │
│                │───────────────────────────────────────────────────────────▶│
│                │                     │                    │                  │
│                │  InvoiceGenerated event                  │                  │
│                │  (Event Store)      │                    │                  │
│                │                     │                    │                  │
│                │  Relatório CVM      │                    │                  │
│                │  (Posição Consolidada)                   │                  │
│                │                     │                    │                  │
│  200 {invoice} │                     │                    │                  │
│◀───────────────│                     │                    │                  │
```

### Fluxo: Reconciliação Estendida (Pix + Blockchain + CVM)

```
Schedule (cron)    Reconciliation Script       PostgreSQL        Stark Bank      Blockchain
     │                      │                      │                │               │
     │  make reconcile      │                      │                │               │
     │─────────────────────▶│                      │                │               │
     │                      │  1. Load Pix events  │                │               │
     │                      │─────────────────────▶│                │               │
     │                      │◀─────────────────────│                │               │
     │                      │                      │                │               │
     │                      │  2. For each Pix:    │                │               │
     │                      │   Check Stark Bank   │                │               │
     │                      │──────────────────────────────────────▶│               │
     │                      │◀──────────────────────────────────────│               │
     │                      │                      │                │               │
     │                      │  3. Load on-chain    │                │               │
     │                      │   events             │                │               │
     │                      │─────────────────────▶│                │               │
     │                      │◀─────────────────────│                │               │
     │                      │                      │                │               │
     │                      │  4. Cross-reference  │                │               │
     │                      │   Pix ↔ Blockchain   │                │               │
     │                      │                      │                │               │
     │                      │  5. If discrepancy:  │                │               │
     │                      │   a. Log alert       │                │               │
     │                      │   b. Generate report │                │               │
     │                      │   c. Notify CVM      │                │               │
     │                      │                      │                │               │
     │  Report + CVM file   │                      │                │               │
     │◀─────────────────────│                      │                │               │
```

---

> **Documento gerado em**: 13/06/2026
> **Versão do Projeto**: 0.1.0
> **Adaptação para Mercado Financeiro Brasileiro**: v1.0
