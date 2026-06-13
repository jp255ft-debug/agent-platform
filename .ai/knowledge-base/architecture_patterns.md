# Architecture Patterns — Knowledge Base

## Event Sourcing

### Conceito
Event Sourcing persiste o estado de um sistema como uma sequência imutável de eventos. Em vez de armazenar o estado atual de um aggregate, armazenamos cada mudança como um evento.

### Implementação no Projeto

#### Estrutura do Event Store (PostgreSQL)
```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    stream_id VARCHAR(255) NOT NULL,      -- aggregate_id
    version INTEGER NOT NULL,              -- versão sequencial
    event_type VARCHAR(100) NOT NULL,      -- "AgentRegistered", "ResourceConsumed"
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',      -- payload do evento
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(stream_id, version)             -- controle de concorrência
);
```

#### Ciclo de Vida de um Aggregate
```
1. Carregar eventos do stream (event_store.load_stream)
2. Reconstruir aggregate aplicando eventos (aggregate._apply)
3. Executar comando de negócio (aggregate.metodo())
4. Coletar novos eventos (aggregate.get_changes())
5. Persistir eventos com versionamento otimista (event_store.append_events)
```

#### Versionamento Otimista
```python
# No CommandHandler
expected_version = aggregate.version - len(aggregate.get_changes())
await self._event_store.append_events(
    stream_id, aggregate.get_changes(),
    expected_version=expected_version,
)
```
Se outro processo tiver alterado o aggregate entre a leitura e a escrita, o `UNIQUE(stream_id, version)` no banco rejeitará a transação.

### Snapshots
Para evitar reconstruir aggregates longos desde o início:
```python
# Salvar snapshot a cada N eventos
if aggregate.version % SNAPSHOT_INTERVAL == 0:
    await snapshot_repo.save_snapshot(
        aggregate_id=aggregate.aggregate_id,
        aggregate_type=type(aggregate).__name__,
        data=aggregate.to_dict(),
        version=aggregate.version,
    )
```

---

## CQRS (Command Query Responsibility Segregation)

### Conceito
Separar operações de escrita (Commands) de operações de leitura (Queries).

### Implementação

#### Commands (Escrita)
```python
@dataclass
class RegisterAgentCommand:
    agent_id: str
    owner_address: str
    delegation_address: str | None = None

# Handler processa o comando
class CommandHandlers:
    async def handle_register_agent(self, command: RegisterAgentCommand) -> None:
        # 1. Validar regras de negócio
        # 2. Criar aggregate
        # 3. Persistir eventos
```

#### Queries (Leitura)
```python
# Endpoint GET lê do event store (ou de projeções)
@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession):
    events = await event_store.load_stream(agent_id)
    agent = AgentAggregate(agent_id)
    for event in events:
        agent._apply(event)
    return AgentResponse(...)
```

---

## Outbox Pattern

### Conceito
Garantir que eventos sejam publicados no Kafka de forma confiável, sem perder eventos mesmo se o Kafka estiver indisponível.

### Implementação
```sql
CREATE TABLE outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Fluxo
```
1. Transação: INSERT evento no event_store + INSERT na outbox
2. Worker: SELECT * FROM outbox WHERE published = FALSE
3. Worker: Publica no Kafka
4. Worker: UPDATE outbox SET published = TRUE
```

---

## Idempotência

### Conceito
Garantir que uma operação possa ser executada múltiplas vezes sem efeitos colaterais.

### Implementação (Redis)
```python
class IdempotencyService:
    async def is_processed(self, key: str) -> bool:
        return await self._redis.exists(f"idempotency:{key}")

    async def mark_processed(self, key: str) -> None:
        await self._redis.setex(f"idempotency:{key}", 3600, "1")
```

---

## Rate Limiting (Token Bucket)

### Conceito
Algoritmo Token Bucket: um bucket com N tokens que se regenera a uma taxa R tokens/segundo.

### Implementação (Redis Lua)
```lua
-- KEYS[1]: rate_limit:{agent_id}:{resource_type}
-- ARGV[1]: max_tokens
-- ARGV[2]: refill_rate (tokens/second)
-- ARGV[3]: current_time

local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or tonumber(ARGV[1])
local last_refill = tonumber(bucket[2]) or 0
local now = tonumber(ARGV[3])

-- Refill tokens
local elapsed = now - last_refill
tokens = math.min(tokens + (elapsed * tonumber(ARGV[2])), tonumber(ARGV[1]))

if tokens >= 1 then
    redis.call('HMSET', KEYS[1], 'tokens', tokens - 1, 'last_refill', now)
    redis.call('EXPIRE', KEYS[1], 10)
    return {1, tokens - 1}
else
    return {0, tokens}
end
```

---

## x402 Micropayments

### Conceito
Protocolo HTTP 402 (Payment Required) para micropagamentos on-chain.

### Fluxo
```
1. Agent envia requisição com proof de pagamento (tx_hash + assinatura)
2. Backend verifica a transação on-chain (Web3)
3. Se válido, processa o recurso
4. Se inválido, retorna 402 Payment Required
```

### State Channels (para alta frequência)
```
1. Agent e Platform assinam um estado inicial (off-chain)
2. Múltiplas atualizações de estado (off-chain)
3. Settlement final on-chain
4. Período de disputa (challenge period)
```
