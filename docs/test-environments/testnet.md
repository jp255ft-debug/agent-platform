# Ambiente de Testnet Pública — Base Sepolia

> **Chain ID:** 84532 · **RPC:** https://sepolia.base.org · **ETH:** 💧 Faucet

> ⚠️ **Nota:** Este ambiente usa ETH real de testnet (faucet). Prefira Hardhat Fork ou Tenderly para desenvolvimento.

## Configurar MetaMask

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

## Deploy dos Contratos

```bash
# contracts/.env
PRIVATE_KEY=0x<sua_chave_privada_metamask>
BASESCAN_API_KEY=<api_key_do_basescan>

# Deploy PaymentVerifier
forge script script/DeployPaymentVerifier.s.sol \
  --rpc-url https://sepolia.base.org \
  --private-key $PRIVATE_KEY \
  --broadcast --verify \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY

# Deploy AgentDelegation (opcional)
forge script script/DeployAgentDelegation.s.sol \
  --rpc-url https://sepolia.base.org \
  --private-key $PRIVATE_KEY \
  --broadcast --verify \
  --verifier-url https://api-sepolia.basescan.org/api \
  --etherscan-api-key $BASESCAN_API_KEY
```

Anote os endereços dos contratos deployados.

## Configurar o Backend

Atualize `.env`:

```env
WEB3_PROVIDER_URL=https://sepolia.base.org
PAYMENT_VERIFIER_ADDRESS=0x<endereço_do_payment_verifier>
AGENT_DELEGATION_ADDRESS=0x<endereço_do_agent_delegation>
DATABASE_URL=postgresql+asyncpg://agent:agent@localhost:5432/agent_platform
REDIS_URL=redis://localhost:6379/0
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
IONET_API_KEY=<sua_chave_io_net>
IONET_API_URL=https://api.io.net/v1
```

Inicie:

```bash
docker compose up -d
# Ou manualmente:
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verifique:

```bash
curl http://localhost:8000/health
# → {"status":"healthy","database":"connected","redis":"connected","kafka":"connected"}
```

## Fluxo de Autenticação

### Criar Agente

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent_abc123", "owner_address": "0x<seu_endereco_metamask>"}'
```

### Criar API Key

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/agent_abc123/api-keys \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent_abc123", "expires_in_days": 90}'
```

> ⚠️ **A `plain_key` é mostrada apenas uma vez!** Salve-a imediatamente.

### Usar a API Key

```
X-API-Key: key_id.plain_key
```

## Testar Endpoints

```bash
# Listar GPUs
curl -s http://localhost:8000/api/v1/gpu/hardware -H "X-API-Key: <sua_api_key>"

# Solicitar Lease
curl -s -X POST http://localhost:8000/api/v1/gpu/lease \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <sua_api_key>" \
  -d '{"hardware_id": "gpu_001", "duration_hours": 1, "gpu_count": 1, "max_budget_usdc": 2.0}'

# Consultar Status
curl -s http://localhost:8000/api/v1/gpu/leases/<lease_id> -H "X-API-Key: <sua_api_key>"
```

## Frontend de Teste

```bash
start frontend-test.html
```

O frontend guiará você pelos 7 passos: Conectar → Criar Agente → API Key → Listar GPUs → Leasear → Ver Status.
