# API Conventions — Knowledge Base

## OpenAPI 3.0 Standards

### Endpoints REST

#### Base URL
```
/api/v1/{resource}
```

#### Padrão de Nomenclatura
| Método | Path | Descrição |
|--------|------|-----------|
| GET | /api/v1/agents | Listar agentes |
| POST | /api/v1/agents | Criar agente |
| GET | /api/v1/agents/{id} | Obter agente |
| POST | /api/v1/agents/{id}/delegate | Delegar agente |
| POST | /api/v1/agents/{id}/revoke-delegation | Revogar delegação |
| POST | /api/v1/agents/{id}/reputation | Atualizar reputação |
| POST | /api/v1/consume | Consumir recurso |
| GET | /api/v1/consume/sessions/{id} | Obter sessão de billing |
| GET | /api/v1/invoices | Listar faturas |
| GET | /api/v1/invoices/{id} | Obter fatura |
| POST | /api/v1/invoices/{id}/settle | Liquidar fatura |
| GET | /health | Health check |

### Padrão de Respostas

#### Sucesso (200/201)
```json
{
    "agent_id": "0x1234...",
    "owner_address": "0xabcd...",
    "status": "active",
    "version": 5
}
```

#### Erro (400/404/409/429)
```json
{
    "detail": "Agent not found"
}
```

#### Erro de Validação (422)
```json
{
    "detail": [
        {
            "loc": ["body", "agent_id"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

### Códigos de Status
| Código | Significado | Uso |
|--------|-------------|-----|
| 200 | OK | GET, POST (sucesso) |
| 201 | Created | POST (recurso criado) |
| 400 | Bad Request | Dados inválidos |
| 402 | Payment Required | x402 payment needed |
| 404 | Not Found | Recurso não existe |
| 409 | Conflict | Concorrência (versão) |
| 422 | Unprocessable Entity | Validação de schema |
| 429 | Too Many Requests | Rate limit excedido |

---

## AsyncAPI 2.0 (Event Streaming)

### Tópicos Kafka
| Tópico | Eventos | Descrição |
|--------|---------|-----------|
| agent.registered | AgentRegistered | Novo agente registrado |
| agent.delegated | AgentDelegated | Delegação de agente |
| agent.reputation | AgentReputationUpdated | Reputação atualizada |
| billing.resource.consumed | ResourceConsumed | Recurso consumido |
| billing.session.settled | BillingSessionSettled | Sessão liquidada |
| billing.invoice.generated | InvoiceGenerated | Fatura gerada |
| billing.invoice.paid | InvoicePaid | Fatura paga |
| payment.verified | PaymentVerified | Pagamento verificado |

### Formato do Evento
```json
{
    "event_id": "uuid",
    "event_type": "AgentRegistered",
    "aggregate_id": "agent:0x1234",
    "occurred_at": "2026-06-10T12:00:00Z",
    "data": {
        "agent_id": "0x1234",
        "owner_address": "0xabcd"
    }
}
```

---

## WebSocket

### Endpoint
```
ws://host/ws
```

### Mensagens

#### Cliente → Servidor
```json
{"type": "ping"}
{"type": "subscribe", "channels": ["agent.*", "billing.*"]}
```

#### Servidor → Cliente
```json
{"type": "pong"}
{"type": "subscribed", "channels": ["agent.*", "billing.*"]}
{"type": "event", "event_type": "AgentRegistered", "data": {...}}
