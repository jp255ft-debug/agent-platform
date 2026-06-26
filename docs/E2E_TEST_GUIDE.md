# Guia de Teste End-to-End (E2E) — Agent Platform

> **Versão:** 2.0 — Ecossistema completo de testes
> **Data:** 26/06/2026
> **Redes Suportadas:** Hardhat Local (31337) · Tenderly Virtual TestNet · Base Sepolia (84532)

---

## 📋 Visão Geral do Ecossistema de Testes

A Agent Platform utiliza **4 camadas de ambiente** para garantir qualidade em todas as etapas:

| Camada | Ambiente | Ferramenta | ETH | Dados Reais | Velocidade |
|--------|----------|------------|-----|-------------|------------|
| **1. Desenvolvimento** | Local | Hardhat Fork | ♾️ Infinito | ✅ Fork da Mainnet | ⚡ Instantâneo |
| **2. Staging** | Nuvem | Tenderly Virtual TestNet | ♾️ Infinito | ✅ Fork da Mainnet | 🚀 Rápido |
| **3. Teste de Carga** | Local/CI | Locust / k6 | ♾️ Simulado | ❌ Mockado | ⚡ Sob demanda |
| **4. Testnet Pública** | Base Sepolia | MetaMask + Foundry | 💧 Faucet | ⚠️ Parcial | 🐢 Lento |

### Matriz de Responsabilidades

| O quê testar | Hardhat | Tenderly | Locust/k6 | Sepolia |
|-------------|---------|----------|-----------|---------|
| Fluxo completo (Auth → Lease → Kill) | ✅ | ✅ | ❌ | ✅ |
| Preços de oráculos on-chain | ❌ | ✅ | ❌ | ✅ |
| Rate limiting sob carga | ❌ | ❌ | ✅ | ❌ |
| Consumer lag do Kafka | ❌ | ❌ | ✅ | ❌ |
| CI/CD (cada PR) | ✅ | ✅ | ✅ | ❌ |
| Demo para clientes | ✅ | ✅ | ❌ | ✅ |

---

## 🧰 Pré-requisitos

| Item | Versão Mínima | Como Obter |
|------|--------------|------------|
| Node.js | 18.x | `nvm install 18` |
| Docker | 24.x | `docker --version` |
| MetaMask | Extensão Chrome | [metamask.io](https://metamask.io) |
| Foundry | nightly | `foundryup` |
| Hardhat | 2.x | `npm install -g hardhat` |
| Python | 3.11+ | `python --version` |
| Locust (opcional) | 2.40+ | `pip install locust` |
| k6 (opcional) | 0.50+ | `npm install -g k6` |

---

## 🏗️ PASSO 1: Ambiente de Desenvolvimento Local (Hardhat Fork)

O Hardhat Fork cria uma blockchain local que copia o estado real da Mainnet/Base Sepolia. Você tem ETH infinito e pode manipular o estado com cheatcodes.

### 1.1. Instalar Hardhat

```bash
cd contracts
npm install --save-dev hardhat @nomiclabs/hardhat-ethers ethers
npm install --save-dev @nomicfoundation/hardhat-network-helpers
```

### 1.2. Configurar `hardhat.config.js`

```javascript
// contracts/hardhat.config.js
module.exports = {
  solidity: "0.8.20",
  networks: {
    hardhat: {
      forking: {
        url: "https://sepolia.base.org",
        blockNumber: 12345678  // Pinar bloco = testes determinísticos
      }
    }
  }
};
```

> **Por que pinar um bloco?** O estado não muda entre execuções, garantindo testes reproduzíveis. O Hardhat cacheia os dados no disco, trazendo **ganhos de velocidade de até 20x**.

### 1.3. Iniciar o nó local

```bash
npx hardhat node --fork https://sepolia.base.org --fork-block-number 12345678
```

Isso criará:
- **20 contas** com 10.000 ETH falsos cada
- RPC em `http://127.0.0.1:8545`
- Chain ID: `31337`

### 1.4. Conectar MetaMask à rede local

| Campo | Valor |
|-------|-------|
| **Network Name** | Hardhat Local |
| **New RPC URL** | `http://127.0.0.1:8545` |
| **Chain ID** | `31337` |
| **Currency Symbol** | `ETH` |

Importe uma conta de teste: pegue a chave privada de uma das contas exibidas no terminal do Hardhat e importe na MetaMask.

### 1.5. Impersonação de contas

Com o Hardhat, você pode **assumir a identidade de qualquer endereço** da rede forkeada:

```javascript
const helpers = require("@nomicfoundation/hardhat-network-helpers");

// Impersonar um endereço específico
await helpers.impersonateAccount("0x...endereço_do_agente...");

// Agora você pode assinar transações como esse endereço
const impersonatedSigner = await ethers.getSigner("0x...endereço_do_agente...");
await impersonatedSigner.sendTransaction({ to: "...", value: ... });
```

Outros cheatcodes úteis:
- `helpers.setBalance(endereco, ethers.parseEther("1000"))` — definir saldo
- `helpers.takeSnapshot()` / `helpers.restoreSnapshot()` — snapshots para resetar estado
- `helpers.mine(10)` — minerar blocos rapidamente

---

## ☁️ PASSO 2: Ambiente de Staging (Tenderly Virtual TestNet)

O Tenderly oferece **Virtual Environments** — ambientes privados que fazem fork de uma rede ao vivo (Mainnet, Base, Sepolia) e se comportam como uma mainnet que você controla.

### 2.1. Criar conta e configurar

1. Crie uma conta gratuita em [Tenderly](https://tenderly.co)
2. Configure as variáveis de ambiente:

```bash
export TENDERLY_ACCOUNT_ID=<seu_usuario>
export TENDERLY_PROJECT=<seu_projeto>
export TENDERLY_ACCESS_KEY=<sua_access_key>

export TENDERLY_TESTNET_NAME=agent-platform-staging
export PURPOSE=development
export ORIGINAL_NETWORK_ID=84532  # Base Sepolia
export BLOCK_NUMBER=latest
export CHAIN_ID=735784532           # Prefixo 7357 + Chain ID original
```

### 2.2. Script de criação e deploy

Crie `scripts/deploy/deploy-to-testnet.sh`:

```bash
#!/bin/bash
cd contracts

# Criar Virtual TestNet (via API Tenderly)
# (consulte a documentação do Tenderly para o endpoint exato)

# Deploy dos contratos
forge script script/DeployPaymentVerifier.s.sol \
  --broadcast \
  --rpc-url $TENDERLY_VIRTUAL_TESTNET_RPC \
  --verify \
  --verifier-url $VERIFICATION_URL \
  --private-key $DEPLOYER_PRIVATE_KEY

echo "Contratos deployados. RPC: $TENDERLY_VIRTUAL_TESTNET_RPC"
```

### 2.3. CI/CD com GitHub Actions

Adicione ao `.github/workflows/ci.yml`:

```yaml
tenderly-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: Tenderly/tenderly-github-actions@v1
      with:
        access_key: ${{ secrets.TENDERLY_ACCESS_KEY }}
        project: ${{ secrets.TENDERLY_PROJECT }}
        action: create-testnet
    - run: forge script script/DeployPaymentVerifier.s.sol --rpc-url ${{ env.TENDERLY_RPC_URL }}
```

### 2.4. Snapshot para múltiplos cenários

Use snapshots para testar diferentes cenários sem recriar o ambiente:

```bash
# Salvar snapshot
curl -X POST $TENDERLY_ADMIN_RPC \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tenderly_snapshot","params":[],"id":1}'

# Restaurar snapshot
curl -X POST $TENDERLY_ADMIN_RPC \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tenderly_revert","params":["0x1"],"id":1}'
```

---

## 📊 PASSO 3: Monitoramento com Kafka UI

O Kafka UI permite visualizar tópicos, partições, grupos de consumidores e lag em tempo real — essencial durante os testes.

### 3.1. Adicionar ao `docker-compose.yml`

```yaml
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"

  kafka-ui:
    image: ghcr.io/kafbat/kafka-ui:latest
    container_name: kafka-ui
    ports:
      - "8080:8080"
    environment:
      - KAFKA_CLUSTERS_0_NAME=agent-platform
      - KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=kafka:9092
      - KAFKA_CLUSTERS_0_ZOOKEEPER=zookeeper:2181
    depends_on:
      - kafka
      - zookeeper
```

### 3.2. Iniciar e acessar

```bash
docker compose up -d
```

Acesse `http://localhost:8080` para ver:
- **Topics**: `leases`, `kill-switches`, `payments`, `audit-logs`
- **Messages**: explore payloads JSON em tempo real
- **Consumer Groups**: veja o lag de cada grupo
- **Brokers**: métricas de partições e réplicas

> 💡 **Dica:** Durante os testes de carga, monitore o **consumer lag**. Se ele crescer, seu processamento não está acompanhando a produção de eventos.

---

## 🚀 PASSO 4: Testes de Carga

### 4.1. Locust (Python) — Centenas de Agentes Autônomos

O Locust permite simular centenas de agentes solicitando leases simultaneamente.

**Instalação:**

```bash
pip install locust
```

**Crie `scripts/load-test/locustfile.py`:**

```python
from locust import HttpUser, task, between
import json
import uuid

class AgentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Cada usuário simula um agente único
        self.agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        self.owner_address = "0x" + "0"*40

        # 1. Criar agente
        resp = self.client.post("/api/v1/agents", json={
            "agent_id": self.agent_id,
            "owner_address": self.owner_address
        })

        # 2. Criar API Key
        resp = self.client.post(
            f"/api/v1/agents/{self.agent_id}/api-keys",
            json={"expires_in_days": 90}
        )
        self.api_key = resp.json()["plain_key"]
        self.headers = {"X-API-Key": self.api_key}

    @task(3)
    def list_gpus(self):
        """Listar GPUs disponíveis (3x mais frequente)"""
        self.client.get("/api/v1/gpu/hardware", headers=self.headers)

    @task(1)
    def lease_gpu(self):
        """Solicitar lease de GPU"""
        self.client.post("/api/v1/gpu/lease",
            headers=self.headers,
            json={
                "hardware_id": "gpu_001",
                "duration_hours": 1,
                "gpu_count": 1,
                "max_budget_usdc": 2.0
            },
            name="/api/v1/gpu/lease"
        )

    @task(1)
    def check_lease_status(self):
        """Consultar status de uma lease"""
        self.client.get("/api/v1/gpu/leases", headers=self.headers)
```

**Executar:**

```bash
# Com interface web
locust -f scripts/load-test/locustfile.py --host http://localhost:8000

# Headless para CI/CD
locust -f scripts/load-test/locustfile.py --host http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 5m \
  --html report.html --csv results
```

Abra `http://localhost:8089` para definir o número de usuários e taxa de spawn.

### 4.2. k6 (JavaScript) — Testes Pesados com Thresholds

O k6 é mais performático que o Locust (escrito em Go) e ideal para CI/CD.

**Instalação:**

```bash
npm install -g k6
```

**Crie `scripts/load-test/k6-test.js`:**

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up
    { duration: '5m', target: 50 },   // Mantém
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% das reqs < 500ms
    http_req_failed: ['rate<0.01'],   // < 1% de falhas
  },
};

export default function () {
  const agentId = `agent_${randomString(8)}`;
  const headers = { 'Content-Type': 'application/json' };

  // 1. Criar agente
  let res = http.post('http://localhost:8000/api/v1/agents',
    JSON.stringify({
      agent_id: agentId,
      owner_address: '0x' + '0'.repeat(40)
    }),
    { headers }
  );
  check(res, { 'agent created': (r) => r.status === 201 });

  // Extrair API Key
  const apiKeyResp = http.post(
    `http://localhost:8000/api/v1/agents/${agentId}/api-keys`,
    JSON.stringify({ expires_in_days: 90 }),
    { headers }
  );
  const apiKey = apiKeyResp.json('plain_key');
  const authHeaders = { 'X-API-Key': apiKey };

  // 2. Listar GPUs
  res = http.get('http://localhost:8000/api/v1/gpu/hardware', { headers: authHeaders });
  check(res, { 'list GPUs': (r) => r.status === 200 });

  // 3. Solicitar lease (33% das iterações)
  if (Math.random() < 0.33) {
    res = http.post('http://localhost:8000/api/v1/gpu/lease',
      JSON.stringify({
        hardware_id: 'gpu_001',
        duration_hours: 1,
        gpu_count: 1,
        max_budget_usdc: 2.0
      }),
      { headers: authHeaders }
    );
    check(res, { 'lease created': (r) => r.status === 201 });
  }

  sleep(1);
}
```

**Executar:**

```bash
k6 run scripts/load-test/k6-test.js

# Com relatório JSON
k6 run --out json=results.json scripts/load-test/k6-test.js
```

### 4.3. Comparação Rápida: Locust vs k6

| Característica | Locust | k6 |
|----------------|--------|-----|
| Linguagem | Python | JavaScript (ES6) |
| Performance | Bom (greenlets) | **Excelente (Go)** |
| Concorrência | Síncrona | **Assíncrona** |
| Interface | Web UI nativa | CLI + extensões |
| CI/CD | Suportado | **Nativo** |
| gRPC | Limitado | **Nativo** |

> 💡 **Escolha:** Use **Locust** se prefere Python e quer interface web. Use **k6** para CI/CD e testes mais pesados.

---

## 🌐 PASSO 5: Ambiente de Testnet (Base Sepolia)

> ⚠️ **Nota:** Este ambiente usa ETH real de testnet (faucet). Prefira Hardhat Fork ou Tenderly para desenvolvimento.

### 5.1. Configurar MetaMask para Base Sepolia

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

### 5.2. Deploy dos Contratos

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

### 5.3. Configurar o Backend

Atualize `.env`:

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

Inicie o backend:

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

---

## 🔑 PASSO 6: Fluxo de Autenticação (API Key)

O projeto usa **API Keys** (não Sign-In with Ethereum).

### 6.1. Criar um Agente

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_abc123",
    "owner_address": "0x<seu_endereco_metamask>"
  }'
```

**Resposta:**
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

### 6.2. Criar uma API Key

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/agent_abc123/api-keys \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent_abc123", "expires_in_days": 90}'
```

**Resposta:**
```json
{
  "key_id": "550e8400-e29b-41d4-a716-446655440000",
  "plain_key": "550e8400-e29b-41d4-a716-446655440000.abc123...xyz",
  "expires_at": "2026-09-20T00:00:00Z",
  "agent_id": "agent_abc123"
}
```

> ⚠️ **A `plain_key` é mostrada apenas uma vez!** Salve-a imediatamente.

### 6.3. Usar a API Key

Todas as requisições autenticadas usam o header:

```
X-API-Key: key_id.plain_key
```

---

## 🖥️ PASSO 7: Testar os Endpoints

### 7.1. Listar GPUs Disponíveis

```bash
curl -s http://localhost:8000/api/v1/gpu/hardware \
  -H "X-API-Key: <sua_api_key>"
```

### 7.2. Solicitar Lease de GPU

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

### 7.3. Consultar Status da Lease

```bash
curl -s http://localhost:8000/api/v1/gpu/leases/<lease_id> \
  -H "X-API-Key: <sua_api_key>"
```

---

## 🌐 PASSO 8: Usar o Frontend de Teste

Abra o arquivo `frontend-test.html` na raiz do projeto:

```bash
start frontend-test.html
```

O frontend guiará você pelos 7 passos:

| Passo | Ação | Descrição |
|-------|------|-----------|
| 1 | 🔗 Conectar MetaMask | Conecta à rede configurada |
| 2 | 👤 Criar Agente | Cria agente associado ao seu endereço |
| 3 | 🔑 Criar API Key | Gera chave de API (mostrada uma vez) |
| 4 | 🔒 Usar API Key | Configura a chave (automático ou manual) |
| 5 | 🖥️ Listar GPUs | Consulta hardware disponível na io.net |
| 6 | 💻 Solicitar Lease | Cria uma lease de GPU |
| 7 | 📊 Ver Status | Consulta o status da lease |

---

## 🤖 PASSO 9: Script Automatizado com DeepSeek API

Para simular um **agente autônomo real** que toma decisões como um cliente:

```python
"""Simulador de agente autônomo para testes E2E."""
import os
import requests
from openai import OpenAI

# Configuração
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

def criar_agente():
    """Passo 1: Criar um agente na plataforma."""
    resp = requests.post(f"{BASE_URL}/api/v1/agents", json={
        "agent_id": "agent_deepseek_test",
        "owner_address": "0x" + "0" * 40
    })
    return resp.json()

def criar_api_key(agent_id):
    """Passo 2: Gerar API Key."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/agents/{agent_id}/api-keys",
        json={"expires_in_days": 90}
    )
    return resp.json()["plain_key"]

def consultar_deepseek(gpus_disponiveis, orcamento):
    """Usar DeepSeek para decidir qual GPU alugar."""
    prompt = f"""Você é um agente autônomo de IA. 
GPUs disponíveis: {gpus_disponiveis}
Orçamento máximo: ${orcamento} USDC/hora

Qual GPU você recomenda alugar? Responda apenas o hardware_id."""
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()

def fluxo_completo():
    """Executa o fluxo E2E completo com decisão da DeepSeek."""
    print("🚀 Iniciando fluxo E2E com DeepSeek...")
    
    # 1. Criar agente
    agente = criar_agente()
    print(f"✅ Agente criado: {agente['agent_id']}")
    
    # 2. Criar API Key
    api_key = criar_api_key(agente["agent_id"])
    headers = {"X-API-Key": api_key}
    print(f"✅ API Key gerada")
    
    # 3. Listar GPUs
    gpus = requests.get(f"{BASE_URL}/api/v1/gpu/hardware", headers=headers).json()
    print(f"✅ GPUs disponíveis: {len(gpus)}")
    
    # 4. DeepSeek decide qual GPU alugar
    escolha = consultar_deepseek(gpus, orcamento=2.0)
    print(f"🤖 DeepSeek escolheu: {escolha}")
    
    # 5. Solicitar lease
    lease = requests.post(f"{BASE_URL}/api/v1/gpu/lease",
        headers=headers,
        json={
            "hardware_id": escolha,
            "duration_hours": 1,
            "gpu_count": 1,
            "max_budget_usdc": 2.0
        }
    ).json()
    print(f"✅ Lease criada: {lease.get('lease_id', 'N/A')}")
    
    # 6. Verificar status
    status = requests.get(
        f"{BASE_URL}/api/v1/gpu/leases/{lease.get('lease_id')}",
        headers=headers
    ).json()
    print(f"📊 Status da lease: {status}")
    
    return status

if __name__ == "__main__":
    fluxo_completo()
```

---

## ✅ Checklist Final

### Ambiente Local (Hardhat Fork)
- [ ] Hardhat instalado e configurado
- [ ] Nó local rodando (`npx hardhat node`)
- [ ] MetaMask conectada à rede local (Chain ID: 31337)
- [ ] Conta de teste importada com ETH infinito
- [ ] Contratos deployados no fork
- [ ] Backend rodando (`docker compose up -d`)
- [ ] Kafka UI acessível (`http://localhost:8080`)

### Ambiente de Staging (Tenderly)
- [ ] Conta Tenderly criada
- [ ] Virtual TestNet configurada
- [ ] Variáveis de ambiente exportadas
- [ ] Contratos deployados via Tenderly
- [ ] CI/CD configurado (GitHub Actions)

### Testes de Carga
- [ ] Locust ou k6 instalado
- [ ] Script de carga criado
- [ ] Teste executado com 50+ usuários simultâneos
- [ ] Thresholds validados (p(95) < 500ms, falhas < 1%)
- [ ] Consumer lag do Kafka monitorado

### Testnet Pública (Base Sepolia)
- [ ] MetaMask configurada para Base Sepolia (Chain ID: 84532)
- [ ] ETH de teste obtido no faucet
- [ ] Contratos deployados na Base Sepolia
- [ ] `.env` atualizado com endereços dos contratos
- [ ] Fluxo completo testado (Auth → List → Lease → Status)

### Fluxo do Cliente
- [ ] `frontend-test.html` funcionando
- [ ] Agente criado via API
- [ ] API Key criada e salva
- [ ] GPUs listadas com sucesso
- [ ] Lease solicitada e status consultado
- [ ] Script DeepSeek executado com sucesso

---

## 🐛 Troubleshooting

| Problema | Causa Provável | Solução |
|----------|---------------|---------|
| `409 Conflict` ao criar agente | Agente já existe | Use outro `agent_id` ou prossiga |
| `401 Unauthorized` | API Key inválida | Re-crie a API Key |
| `X-API-Key` não reconhecido | Formato incorreto | Use `key_id.plain_key` |
| MetaMask "Wrong Network" | Rede não configurada | Verifique Chain ID (31337 ou 84532) |
| `No GPUs available` | io.net sem hardware | Tente novamente mais tarde |
| `Lease failed` | Saldo insuficiente | Verifique budget e saldo |
| Hardhat "Fork block not found" | Bloco especificado não existe | Use `latest` ou um bloco válido |
| Tenderly "Access denied" | Access Key inválida | Verifique `TENDERLY_ACCESS_KEY` |
| Kafka UI "Connection refused" | Kafka não iniciou | `docker compose logs kafka` |
| Locust "Connection refused" | Backend não está rodando | `docker compose up -d` |
| k6 "threshold exceeded" | Performance abaixo do esperado | Escalone workers ou otimize queries |

---

## 📚 Referências

- [Arquitetura do Projeto](../ARCHITECTURE.md)
- [API Conventions](../.ai/knowledge-base/api_conventions.md)
- [Production Readiness Audit](PRODUCTION_READINESS_AUDIT.md)
- [Mainnet Checklist](MAINNET_CHECKLIST.md)
- [Chaos Engineering Plan](chaos-engineering-plan.md)
- [Tenderly Virtual Environments](https://docs.tenderly.co/virtual-environments/overview)
- [Hardhat Forking Guide](https://v2.hardhat.org/hardhat-network/docs/guides/forking-other-networks)
- [Locust Documentation](https://docs.locust.io/)
- [k6 Documentation](https://k6.io/docs/)
- [Kafbat UI GitHub](https://github.com/kafbat/kafka-ui)
