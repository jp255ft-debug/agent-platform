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

### Testes
- **pytest** com fixtures assíncronas
- **Testcontainers** para PostgreSQL/Redis em CI
- **Mock** para blockchain (Web3) e Kafka
- Cobertura mínima: 80%

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

---

## 🌐 TypeScript (Node.js Service)

### Convenções
- **TypeScript 5+** com strict mode
- **ES2020** target
- **Async/await** para todas operações
- **ESLint** + Prettier
- Interfaces sobre types para objetos complexos

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
