# CLAUDE.md — Regras de Planejamento e Arquitetura

## 🎯 Propósito
Este arquivo é carregado automaticamente no início de cada sessão de planejamento (PLAN MODE). Ele contém as decisões arquiteturais, padrões de design e contexto essencial para que o planejamento seja consistente entre sessões.

---

## 🏗️ Arquitetura do Sistema

### Stack Principal
- **Backend**: Python 3.11+ / FastAPI (async)
- **Banco**: PostgreSQL 15 (event store) + TimescaleDB (analytics)
- **Cache**: Redis 7 (rate limiting, idempotência, sessões)
- **Mensageria**: Kafka (event streaming)
- **Blockchain**: Base (Ethereum L2) via Web3.py
- **Contratos**: Solidity 0.8+ com Foundry

### Padrões Arquiteturais (Obrigatórios)

#### 1. Event Sourcing
- Todo estado é derivado de eventos armazenados no PostgreSQL (JSONB)
- Eventos são **append-only** — nunca alterar ou deletar
- Stream ID = aggregate_id (ex: `agent:0x1234`, `session:0xabcd`)
- Versionamento otimista para concorrência
- Snapshots periódicos para performance

#### 2. CQRS (Command Query Responsibility Segregation)
- **Commands**: Mutam estado → produzem eventos → armazenados no event store
- **Queries**: Leem de projeções/materialized views (não do event store)
- Handlers de comando retornam apenas confirmação + ID do aggregate

#### 3. Outbox Pattern
- Eventos são primeiro persistidos no banco (tabela `outbox`)
- Um worker assíncrono publica no Kafka
- Garante entrega **at-least-once** sem perder eventos

#### 4. x402 Micropayments
- Pagamento é verificado on-chain antes do consumo
- State channels para micropagamentos frequentes
- EIP-712 para assinaturas off-chain

---

## 📐 Decisões Arquiteturais (ADRs)

### ADR-001: Mecanismo de Pagamento (x402 + State Channels)
- **Decisão**: Usar x402 para pagamentos avulsos, state channels para alta frequência
- **Motivo**: x402 é simples mas caro em gas; state channels são mais baratos para múltiplas transações
- **Trade-off**: State channels exigem lógica de disputa on-chain

### ADR-002: Delegação EIP-7702
- **Decisão**: Usar EIP-7702 para permitir que EOAs deleguem capacidade computacional
- **Motivo**: EIP-7702 permite que contas EOAs executem código de contrato sem deploy
- **Implementação**: Contrato `AgentDelegation.sol` com funções `setDelegation`/`revokeDelegation`

### ADR-003: Event Sourcing com PostgreSQL
- **Decisão**: PostgreSQL com JSONB como event store (não EventStoreDB ou DynamoDB)
- **Motivo**: Menos dependências externas, transações ACID, familiaridade da equipe
- **Trade-off**: Performance inferior a soluções especializadas para altíssimo throughput

### ADR-004: Rate Limiting com Redis
- **Decisão**: Token Bucket algorithm em Lua (executado no Redis)
- **Motivo**: Atomicidade, performance, sem race conditions
- **Implementação**: Scripts Lua em `backend/app/scripts/redis/`

---

## 🔄 Fluxos Críticos

### Fluxo de Consumo de Recurso
```
Agent → POST /api/v1/consume (com x402 proof)
  → Verificar idempotência (Redis)
  → Verificar rate limit (Redis Token Bucket)
  → Verificar pagamento x402 (on-chain via Web3)
  → Criar/atualizar billing session (Event Store)
  → Publicar evento ResourceConsumed (Kafka)
  → Retornar session_id + tokens restantes
```

### Fluxo de Delegação (EIP-7702)
```
Agent → POST /api/v1/agents/{id}/delegate
  → Verificar se agente existe (Event Store)
  → Verificar assinatura EIP-712 (off-chain)
  → Chamar AgentDelegation.setDelegation (on-chain)
  → Publicar evento AgentDelegated (Event Store)
  → Retornar detalhes atualizados
```

### Fluxo de Settlement
```
Sistema → POST /api/v1/invoices/{id}/settle
  → Carregar invoice aggregate (Event Store)
  → Verificar se está pendente
  → Verificar pagamento on-chain
  → Atualizar status para "paid"
  → Publicar evento InvoicePaid (Kafka)
  → Fechar billing session
```

---

## 🧠 Regras de Planejamento

1. **Sempre começar pelos ADRs**: Antes de implementar qualquer feature, documentar a decisão arquitetural
2. **Priorizar simplicidade**: Se uma solução complexa não é estritamente necessária, optar pela mais simples
3. **Testes primeiro**: Planejar testes antes da implementação (TDD mindset)
4. **Documentação como código**: ADRs, diagramas e modelos de domínio são tão importantes quanto o código
5. **Grounding factual**: Sempre citar fontes (arquivos, funções, ADRs) ao fazer afirmações
6. **Chain of Thought**: Explicar o raciocínio passo a passo antes de concluir

---

## 📁 Estrutura do Projeto (Resumo)

```
agent-platform/
├── .ai/                    # Engenharia de contexto
├── backend/                # FastAPI + Event Sourcing
├── contracts/              # Solidity (Foundry)
├── node-service/           # Node.js (middleware x402)
├── agents/                 # Simuladores
├── timescaledb/            # Analytics
├── monitoring/             # Prometheus + Grafana
├── docs/                   # ADRs, diagramas, modelos
└── scripts/                # Deploy, ops, reconciliação
```
