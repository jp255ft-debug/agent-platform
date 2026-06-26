# CLAUDE.md — Regras de Planejamento e Arquitetura

## 🎯 Propósito
Carregado automaticamente no início de cada sessão de planejamento (PLAN MODE). Contém decisões arquiteturais (ADRs) e contexto essencial para consistência entre sessões.

---

## 🏗️ Stack Principal
- **Backend**: Python 3.11+ / FastAPI (async)
- **Banco**: PostgreSQL 15 (event store) + TimescaleDB (analytics)
- **Cache**: Redis 7 (rate limiting, idempotência, sessões)
- **Mensageria**: Kafka (event streaming)
- **Blockchain**: Base (Ethereum L2) via Web3.py
- **Contratos**: Solidity 0.8+ com Foundry

## 📐 Decisões Arquiteturais (ADRs)

### ADR-001: Event Sourcing com PostgreSQL
- **Decisão**: PostgreSQL com JSONB como event store
- **Motivo**: Menos dependências, transações ACID, familiaridade da equipe
- **Trade-off**: Performance inferior a soluções especializadas para altíssimo throughput

### ADR-002: CQRS
- **Commands** mutam estado → produzem eventos → armazenados no event store
- **Queries** leem de projeções/materialized views (não do event store)

### ADR-003: Outbox Pattern
- Eventos são persistidos no banco (tabela `outbox`) antes do Kafka
- Worker assíncrono publica no Kafka — garante entrega at-least-once

### ADR-004: x402 Micropayments + State Channels
- x402 para pagamentos avulsos, state channels para alta frequência
- EIP-712 para assinaturas off-chain

### ADR-005: Delegação EIP-7702
- Permite que EOAs deleguem capacidade computacional sem deploy de contrato
- Contrato `AgentDelegation.sol` com `setDelegation`/`revokeDelegation`

### ADR-006: Rate Limiting com Redis (Token Bucket)
- Scripts Lua atômicos em `backend/app/infrastructure/cache/lua_scripts/`

---

## 🔄 Fluxos Críticos

### Consumo de Recurso
```
Agent → POST /api/v1/consume (com x402 proof)
  → Verificar idempotência (Redis)
  → Verificar rate limit (Redis Token Bucket)
  → Verificar pagamento x402 (on-chain via Web3)
  → Criar/atualizar billing session (Event Store)
  → Publicar evento ResourceConsumed (Kafka)
  → Retornar session_id + tokens restantes
```

### Delegação (EIP-7702)
```
Agent → POST /api/v1/agents/{id}/delegate
  → Verificar se agente existe (Event Store)
  → Verificar assinatura EIP-712 (off-chain)
  → Chamar AgentDelegation.setDelegation (on-chain)
  → Publicar evento AgentDelegated (Event Store)
```

### Settlement
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

1. **Sempre começar pelos ADRs** — documentar antes de implementar
2. **Priorizar simplicidade** — solução mais simples que funciona
3. **Testes primeiro** — planejar testes antes da implementação (TDD mindset)
4. **Documentação como código** — ADRs, diagramas e modelos de domínio
5. **Grounding factual** — citar fontes (arquivos, funções, ADRs)
6. **Chain of Thought** — explicar raciocínio passo a passo
7. **Verificação** — sempre incluir etapa de validação no plano

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
