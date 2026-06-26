# 🚀 Guia de Vendas — Agent Platform

> **Fluxo completo:** Criar Agente → Gerar API Key → Listar GPUs → Alugar GPU → Monitorar

---

## 📌 Passo 1: Criar uma Conta (Agente)

Registre um novo agente na plataforma. Você precisa fornecer um **identificador único** (`agent_id`) e seu **endereço Ethereum** (`owner_address`).

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "meu-agente-1",
    "owner_address": "0xSeuEnderecoAqui"
  }'
```

**Resposta esperada:**
```json
{
  "agent_id": "meu-agente-1",
  "owner_address": "0xSeuEnderecoAqui",
  "delegation_address": null,
  "delegation_active": false,
  "reputation_score": 100,
  "version": 0
}
```

> ⚠️ **Importante:** O campo `agent_id` é **obrigatório**. Escolha um identificador único para seu agente.

---

## 📌 Passo 2: Gerar uma Chave de API

Crie uma chave de API para autenticar as requisições. A chave é mostrada **apenas uma vez** — salve-a imediatamente!

```bash
curl -X POST http://localhost:8000/api/v1/agents/meu-agente-1/api-keys \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Key: true" \
  -d '{"expires_in_days": 90, "label": "minha-chave"}'
```

**Resposta esperada:**
```json
{
  "key_id": "key_abc123",
  "plain_key": "key_abc123.8a7b6c5d4e3f2g1h",
  "expires_at": "2026-09-23T00:00:00Z"
}
```

> ⚠️ **Salve a `plain_key`!** Ela não será mostrada novamente.

---

## 📌 Passo 3: Listar GPUs Disponíveis

Consulte o hardware disponível na rede io.net para leasing. **Requer autenticação** via header `X-API-Key`.

```bash
curl -X GET http://localhost:8000/api/v1/gpu/hardware \
  -H "X-API-Key: key_abc123.8a7b6c5d4e3f2g1h"
```

**Resposta esperada:**
```json
[
  {
    "id": "gpu-1",
    "model": "RTX 4090",
    "gpu_count": 2,
    "vram_gb": 24,
    "total_vram_gb": 48,
    "price_per_hour_usdc": 1.50,
    "location": "US-East",
    "is_available": true,
    "vcpu": 16,
    "memory_gb": 64,
    "storage_gb": 500
  }
]
```

**Filtros opcionais:**
- `?search=RTX` — busca textual
- `?min_vram=16` — VRAM mínima por placa (GB)
- `?max_price=2.0` — preço máximo por hora (USDC)

---

## 📌 Passo 4: Alugar uma GPU (Leasing)

Solicite uma GPU da io.net. O provisionamento é assíncrono.

```bash
curl -X POST http://localhost:8000/api/v1/gpu/lease \
  -H "Content-Type: application/json" \
  -H "X-API-Key: key_abc123.8a7b6c5d4e3f2g1h" \
  -d '{
    "hardware_id": "gpu-1",
    "duration_hours": 4,
    "gpu_count": 2,
    "max_budget_usdc": 100.0
  }'
```

**Resposta esperada:**
```json
{
  "lease_id": "uuid-da-lease",
  "deployment_id": "dep-123",
  "status": "provisioning",
  "total_cost_usdc": 50.0,
  "ionet_fee_usdc": 5.0,
  "expires_at": "2026-06-21T20:00:00+00:00"
}
```

> 💡 O orçamento é verificado localmente contra `max_budget_usdc`. A integração com orçamento delegado on-chain (EIP-7702) está em desenvolvimento.

---

## 📌 Passo 5: Monitorar e Controlar

### Consultar status da lease
```bash
curl -X GET http://localhost:8000/api/v1/gpu/leases/{lease_id} \
  -H "X-API-Key: key_abc123.8a7b6c5d4e3f2g1h"
```

### Estender duração
```bash
curl -X POST http://localhost:8000/api/v1/gpu/leases/{lease_id}/extend \
  -H "Content-Type: application/json" \
  -H "X-API-Key: key_abc123.8a7b6c5d4e3f2g1h" \
  -d '{"additional_hours": 4}'
```

### Encerrar lease (kill-switch)
```bash
curl -X DELETE http://localhost:8000/api/v1/gpu/leases/{lease_id} \
  -H "X-API-Key: key_abc123.8a7b6c5d4e3f2g1h"
```

---

## 📌 Passo 6: Pagamento e Reconciliação

### Consumo de recursos (x402 micropagamentos)
```bash
curl -X POST http://localhost:8000/api/v1/consume \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "meu-agente-1",
    "resource_type": "compute",
    "amount": 100,
    "x402_payment": {"proof": "0x..."}
  }'
```

### Consultar faturas
```bash
curl -X GET http://localhost:8000/api/v1/invoices
```

---

## 📋 O Que o Cliente NÃO Precisa Fazer

| Tarefa | Por que não precisa |
|--------|-------------------|
| Criar conta na io.net | A plataforma gerencia via API key própria |
| KYC/AML | Só precisa de um endereço Ethereum |
| Lidar com gas fees | Transações on-chain são pagas pela plataforma |
| Assinar transações toda hora | EIP-7702 permite delegação com assinatura única |
| Gerenciar reconciliação | Automática via scripts de reconciliação |
| Instalar software de nó | Só consome a API REST |

---

## 🔧 Troubleshooting

### Erro 422 (Unprocessable Entity)
- Verifique se o payload contém **todos os campos obrigatórios**
- No Passo 1, `agent_id` e `owner_address` são obrigatórios
- No Passo 2, `expires_in_days` é obrigatório (mín. 1, máx. 365)

### Erro 401 (Unauthorized)
- Certifique-se de enviar o header `X-API-Key` com a chave correta
- A chave tem formato `key_id.plain_key`

### Erro 404 (Not Found)
- Verifique se o `agent_id` existe
- Verifique se o `lease_id` está correto

---

## 🧪 Ambiente de Desenvolvimento

Em desenvolvimento, use o header `X-Bootstrap-Key: true` para criar chaves sem autenticação prévia:

```bash
curl -X POST http://localhost:8000/api/v1/agents/meu-agente-1/api-keys \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Key: true" \
  -d '{"expires_in_days": 90, "label": "dev-key"}'
```

---

> 📖 **Documentação completa:** http://localhost:8000/docs (Swagger) ou http://localhost:8000/redoc (ReDoc)
