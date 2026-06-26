# AGENTS.md — Regras de Codificação para Agentes IA

## 🎯 Propósito
Este arquivo é carregado automaticamente no início de cada sessão de codificação (ACT MODE). Ele contém convenções de código, padrões de nomenclatura e regras de implementação.

---

## 🐍 Python (Backend FastAPI)

### Convenções Gerais
- **Python 3.11+** com type hints obrigatórios
- **Async/await** para todas as operações I/O (DB, Redis, Kafka, Web3)
- **PEP 8** (via Ruff) — linha máxima 100 caracteres
- **Docstrings** no formato Google Style
- **Dataclasses** para commands e DTOs
- **Protocols** (ABC) para interfaces de repositório

### Estrutura de Arquivos
```
app/
├── domain/          # Lógica de negócio pura (sem dependências externas)
│   ├── events/      # Eventos de domínio (dataclasses imutáveis)
│   ├── aggregates/  # Aggregate roots com métodos de negócio
│   └── repositories/ # Protocolos/interfaces
├── application/     # Casos de uso (orquestração)
│   ├── commands/    # Command objects (dataclasses)
│   ├── handlers/    # Command/Event handlers
│   └── services/    # Serviços de aplicação (rate limiter, idempotência)
├── infrastructure/  # Implementações concretas (DB, Redis, Kafka, Web3)
│   ├── db/          # PostgreSQL (event store, snapshots)
│   ├── cache/       # Redis
│   ├── messaging/   # Kafka
│   └── blockchain/  # Web3, contratos
└── api/             # Interface HTTP/WebSocket
    ├── v1/
    │   ├── endpoints/  # FastAPI routers
    │   ├── schemas/    # Pydantic models (request/response)
    │   └── middleware/ # Rate limiting, auth
    └── websocket/      # Event streaming
```

### Nomenclatura
- **Commands**: `{Acao}Command` (ex: `RegisterAgentCommand`)
- **Events**: `{Entidade}{Acao}` (ex: `AgentRegistered`)
- **Handlers**: `handle_{acao}` (ex: `handle_register_agent`)
- **Aggregates**: `{Entidade}Aggregate` (ex: `AgentAggregate`)
- **Schemas**: `{Entidade}{Tipo}` (ex: `AgentCreate`, `AgentResponse`)
- **Repositories**: `{Tecnologia}{Entidade}` (ex: `PostgresEventStore`)

### Error Handling
- **Domain errors**: Exceções customizadas em `app/core/exceptions.py`
- **HTTP errors**: FastAPI `HTTPException` com status code apropriado
- **Sempre tratar erros conhecidos**: Nunca deixar `except Exception` sem log
- **Idempotência**: Garantir que operações possam ser repetidas com segurança
- **Hierarquia de exceções**: Usar a árvore em `app/core/exceptions.py`:
  - `AgentPlatformError` → base
  - `DomainError` → erros de negócio (404, 409)
  - `ValidationError` → dados inválidos (422)
  - `AuthenticationError` → falha de autenticação (401)
  - `AuthorizationError` → sem permissão (403)
  - `PaymentError` → falha de pagamento (402)
  - `RateLimitError` → rate limit excedido (429)
  - `IdempotencyError` → conflito de idempotência (409)
  - `BlockchainError` → falha em contrato/Web3 (502)
  - `InfrastructureError` → falha em DB/Redis/Kafka (503)

### Logging
- Usar `structlog` (não `logging` padrão) — configurado em `app/core/logging.py`
- **Níveis**:
  - `DEBUG`: Dados de requisição/resposta (nunca em produção)
  - `INFO`: Eventos de negócio (agente criado, chave gerada, recurso consumido)
  - `WARNING`: Comportamento suspeito (rate limit próximo, tentativa de acesso negado)
  - `ERROR`: Falha operacional (DB offline, Kafka indisponível)
  - `CRITICAL`: Falha catastrófica (perda de dados, breach de segurança)
- **Campos obrigatórios**: `correlation_id`, `agent_id` (quando disponível), `event_type`
- **Nunca logar**: senhas, chaves privadas, tokens de acesso completos (apenas hash/prefixo)

### Testes
- **Framework**: pytest com fixtures assíncronas (`pytest-asyncio`)
- **Cobertura mínima**: 80% (verificada via `pytest-cov`)
- **Estrutura de diretórios**:
  ```
  tests/
  ├── unit/           # Testes de unidade (agregados, handlers, serviços)
  │   ├── test_{entidade}_aggregate.py
  │   ├── test_{entidade}_endpoint.py
  │   └── test_{servico}.py
  ├── integration/    # Testes de integração (endpoints com DB real)
  │   ├── conftest.py  # Fixtures compartilhadas (DB, Redis, Kafka mock)
  │   ├── test_{entidade}.py
  │   └── test_{fluxo}.py
  └── conftest.py     # Fixtures globais
  ```
- **Padrões de teste**:
  - **Unitários**: Mockar dependências externas (DB, Redis, Kafka, Web3)
  - **Integração**: Usar `testcontainers` para PostgreSQL/Redis em CI
  - **Event Sourcing**: Testar rebuild de aggregate a partir de eventos
  - **Idempotência**: Testar que mesma requisição com mesmo `Idempotency-Key` retorna mesmo resultado
  - **Rate Limiting**: Testar que requisições além do limite são rejeitadas com 429
- **Fixtures obrigatórias** (em `tests/conftest.py`):
  - `event_store` — EventStore mockado
  - `redis_cache` — RedisCache mockado
  - `rate_limiter` — RateLimiter mockado
  - `web3_client` — Web3Client mockado
  - `kafka_producer` — KafkaProducer mockado
- **Comandos úteis**:
  ```bash
  pytest backend/tests/unit/ -v                          # Todos os unitários
  pytest backend/tests/unit/test_auth.py -v              # Arquivo específico
  pytest backend/tests/ -k "test_register_agent" -v      # Teste específico
  pytest --cov=app --cov-report=term-missing             # Com cobertura
  pytest -x --ff                                         # Stop on first failure, run failures first
  ```

---

## ⛓️ Solidity (Contratos)

### Convenções Gerais
- **Solidity 0.8.20+** com `pragma` explícito
- **SPDX-License-Identifier** obrigatório
- **NatSpec** (`@notice`, `@param`, `@return`) em todas as funções públicas
- **OpenZeppelin** para padrões ERC (Ownable, ReentrancyGuard)
- **Foundry** para testes (Forge)

### Padrões de Segurança (Obrigatórios)
1. **Checks-Effects-Interactions**: Sempre validar antes de alterar estado, alterar estado antes de chamar externos
2. **ReentrancyGuard**: Em funções que transferem ETH ou chamam contratos externos
3. **Evitar `tx.origin`**: Usar `msg.sender` para autenticação
4. **Integer Overflow**: Usar SafeMath (Solidity 0.8+ já tem built-in)
5. **Eventos**: Emitir eventos em toda mutação de estado

### Estrutura de Contratos
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract MeuContrato is Ownable, ReentrancyGuard {
    // --- State ---
    // --- Events ---
    // --- Constructor ---
    // --- External/Public Functions ---
    // --- Internal Functions ---
    // --- View/Pure Functions ---
}
```

### Testes (Foundry)
- Usar `vm.assume`, `vm.expectRevert`, `vm.prank`
- Testar todos os modifiers (Ownable, ReentrancyGuard)
- Testar edge cases (zero address, overflow, underflow)
- Fuzz testing para funções críticas
- Comandos:
  ```bash
  forge test --match-path contracts/test/MeuContrato.t.sol -vvv
  forge coverage --report lcov
  ```

---

## 🌐 TypeScript (Node.js Service)

### Convenções
- **TypeScript 5+** com strict mode
- **ES2020** target
- **Async/await** para todas operações
- **ESLint** + Prettier
- Interfaces sobre types para objetos complexos

### Testes
- **Framework**: Jest com `ts-jest`
- **Cobertura mínima**: 80%
- **Comandos**:
  ```bash
  cd node-service && npm test
  cd node-service && npm run lint
  cd node-service && npx tsc --noEmit
  ```

---

## 📜 Lua (Redis Scripts)

### Convenções
- Scripts atômicos (sem `redis.call` dentro de loops)
- Documentar KEYS e ARGV no topo
- Retornar arrays para múltiplos valores
- Testar com `redis-cli --eval`

---

## 🚀 Regras de Implementação

1. **Nunca inventar APIs**: Se uma função/biblioteca não existe no código, não assumir que existe
2. **Citar fontes**: Ao implementar, citar o arquivo/função que está sendo modificada
3. **Dizer "não sei"**: Se não souber como implementar algo, perguntar antes de alucinar
4. **Testar antes de concluir**: Sempre verificar se o código gerado é sintaticamente válido
5. **Manter consistência**: Seguir os padrões existentes no projeto, não criar novos
6. **Documentar decisões**: Se uma escolha de implementação não é óbvia, comentar o motivo
7. **Verificar após alterar**: Executar `validate_python.py` ou `validate_solidity.py` após cada alteração significativa
8. **Nunca deixar código comentado**: Remover código morto, não comentar
