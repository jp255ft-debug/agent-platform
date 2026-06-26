# Guia de Teste End-to-End (E2E) — Agent Platform

> **Versão:** 1.0 — Corrigido e alinhado com o código real
> **Data:** 22/06/2026
> **Rede:** Base Sepolia (Chain ID: 84532)

---

## 📋 Pré-requisitos

| Item | Versão Mínima | Como Obter |
|------|--------------|------------|
| Node.js | 18.x | `nvm install 18` |
| Docker | 24.x | `docker --version` |
| MetaMask | Extensão Chrome | [metamask.io](https://metamask.io) |
| ETH Base Sepolia | Testnet | [faucet.quicknode.com/base/sepolia](https://faucet.quicknode.com/base/sepolia) |
| Foundry | nightly | `foundryup` |

---

## 🧩 PASSO 1: Configurar MetaMask para Base Sepolia

Na MetaMask, adicione a rede manualmente:

| Campo | Valor |
|-------|-------|
| **Network Name** | Base Sepolia |
| **New RPC URL** | `https://sepolia.base.org` |
| **Chain ID** | `84532` |
| **Currency Symbol** | `ETH` |
| **Block Explorer URL** | `https://sepolia.basescan.org` |

Obtenha ETH de teste:
- [faucet.quicknode.com/base/sepolia](https://faucet.quicknode.com/base/sepolia)
- [coinbase.com/faucets/base-sepolia-faucet](https://coinbase.com/faucets/base-sepolia-faucet)

---

## 🛠️ PASSO 2: Deploy dos Contratos na Base Sepolia

### 2.1. Configurar variáveis de ambiente

```bash
# contracts/.env
PRIVATE_KEY=0x<sua_chave_privada_metamask>
BASESCAN_API_KEY=<api_key_do_basescan>
```

### 2.2. Deploy do PaymentVerifier

```bash
cd contracts

forge script script/DeployPaymentVerifier.s.sol \
  --rpc-url https://sepolia.base.org \
  --private-key $PRIVATE_KEY \
  --broadcast \
  --verify \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY
```

Anote o endereço do contrato deployado.

### 2.3. Deploy do AgentDelegation (opcional)

```bash
forge script script/DeployAgentDelegation.s.sol \
  --rpc-url https://sepolia.base.org \
  --private-key $PRIVATE_KEY \
  --broadcast \
  --verify \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY
```

---

## 🔧 PASSO 3: Configurar o Backend

### 3.1. Atualizar `.env`

```env
# Blockchain
WEB3_PROVIDER_URL=https://sepolia.base.org
PAYMENT_VERIFIER_ADDRESS=0x<endereço_do_payment_verifier>
AGENT_DELEGATION_ADDRESS=0x<endereço_do_agent_delegation>

# Database
DATABASE_URL=postgresql+asyncpg://agent:agent@localhost:5432/agent_platform

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# io.net (DePIN)
IONET_API_KEY=<sua_chave_io_net>
IONET_API_URL=https://api.io.net/v1
```

### 3.2. Iniciar o Backend

```bash
# Com Docker
docker compose up -d

# Ou manualmente
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verifique se está rodando:

```bash
curl http://localhost:8000/health
# → {"status":"healthy","database":"connected","redis":"connected","kafka":"connected"}
```

---

## 🔑 PASSO 4: Fluxo de Autenticação (API Key)

O projeto **não** usa Sign-In with Ethereum. O fluxo correto é via **API Keys**:

### 4.1. Criar um Agente

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_abc123",
    "owner_address": "0x<seu_endereco_metamask>"
  }'
```

**Resposta esperada:**
```json
{
  "agent_id": "agent_abc123",
  "owner_address": "0x...",
  "delegation_address": null,
  "delegation_active": false,
  "reputation_score": 100,
  "version": 0
}
```

### 4.2. Criar uma API Key

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/agent_abc123/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_abc123",
    "expires_in_days": 90
  }'
```

**Resposta esperada:**
```json
{
  "key_id": "550e8400-e29b-41d4-a716-446655440000",
  "plain_key": "550e8400-e29b-41d4-a716-446655440000.abc123...xyz",
  "expires_at": "2026-09-20T00:00:00Z",
  "agent_id": "agent_abc123"
}
```

> ⚠️ **A `plain_key` é mostrada apenas uma vez!** Salve-a imediatamente.

### 4.3. Usar a API Key

Todas as requisições autenticadas usam o header:

```
X-API-Key: key_id.plain_key
```

---

## 🖥️ PASSO 5: Testar os Endpoints

### 5.1. Listar GPUs Disponíveis

```bash
curl -s http://localhost:8000/api/v1/gpu/hardware \
  -H "X-API-Key: <sua_api_key>"
```

**Resposta esperada:** Array de GPUs disponíveis na io.net.

### 5.2. Solicitar Lease de GPU

```bash
curl -s -X POST http://localhost:8000/api/v1/gpu/lease \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <sua_api_key>" \
  -d '{
    "hardware_id": "gpu_001",
    "duration_hours": 1,
    "gpu_count": 1,
    "max_budget_usdc": 2.0
  }'
```

### 5.3. Consultar Status da Lease

```bash
curl -s http://localhost:8000/api/v1/gpu/leases/<lease_id> \
  -H "X-API-Key: <sua_api_key>"
```

---

## 🌐 PASSO 6: Usar o Frontend de Teste

Abra o arquivo `frontend-test.html` na raiz do projeto no navegador:

```bash
start frontend-test.html
```

O frontend guiará você pelos 7 passos:

| Passo | Ação | Descrição |
|-------|------|-----------|
| 1 | 🔗 Conectar MetaMask | Conecta à Base Sepolia |
| 2 | 👤 Criar Agente | Cria agente associado ao seu endereço |
| 3 | 🔑 Criar API Key | Gera chave de API (mostrada uma vez) |
| 4 | 🔒 Usar API Key | Configura a chave (automático ou manual) |
| 5 | 🖥️ Listar GPUs | Consulta hardware disponível na io.net |
| 6 | 💻 Solicitar Lease | Cria uma lease de GPU |
| 7 | 📊 Ver Status | Consulta o status da lease |

---

## ✅ Checklist Final

- [ ] MetaMask configurada para **Base Sepolia** (Chain ID: 84532)
- [ ] ETH de teste obtido no faucet
- [ ] `PaymentVerifier.sol` deployado na Base Sepolia
- [ ] `.env` atualizado com `PAYMENT_VERIFIER_ADDRESS` e `WEB3_PROVIDER_URL`
- [ ] Backend rodando (`docker compose up -d`)
- [ ] `frontend-test.html` aberto no navegador
- [ ] Agente criado via API
- [ ] API Key criada e salva
- [ ] GPUs listadas com sucesso
- [ ] Lease solicitada e status consultado

---

## 🐛 Troubleshooting

| Problema | Causa Provável | Solução |
|----------|---------------|---------|
| `409 Conflict` ao criar agente | Agente já existe | Use outro `agent_id` ou prossiga |
| `401 Unauthorized` | API Key inválida | Re-crie a API Key |
| `X-API-Key` não reconhecido | Formato incorreto | Use `key_id.plain_key` |
| MetaMask "Wrong Network" | Rede não é Base Sepolia | Mude para Chain ID 84532 |
| `No GPUs available` | io.net sem hardware | Tente novamente mais tarde |
| `Lease failed` | Saldo insuficiente | Verifique budget e saldo |

---

## 📚 Referências

- [Arquitetura do Projeto](../ARCHITECTURE.md)
- [API Conventions](../.ai/knowledge-base/api_conventions.md)
- [Production Readiness Audit](PRODUCTION_READINESS_AUDIT.md)
- [Mainnet Checklist](MAINNET_CHECKLIST.md)
