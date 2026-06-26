# Ambiente de Staging — Tenderly Virtual TestNet

> **Custo:** Gratuito (até 5 Virtual TestNets simultâneos) · **ETH:** ♾️ Infinito · **Dados:** Fork da Mainnet

## O que é

O Tenderly oferece **Virtual Environments** — ambientes privados que fazem fork de uma rede ao vivo (Mainnet, Base, Sepolia) e se comportam como uma mainnet que você controla. Ao contrário de testnets públicas, um Virtual Environment fork o estado real de produção, com preços de oráculos, liquidez e contratos já deployados.

## Por que usar

- Testar o `PaymentVerifier` e o `AgentDelegation` com **dados reais de preços de GPU** da io.net (se usarem oráculos on-chain).
- Simular o **kill-switch** em cenários de estouro de orçamento com gas fees realistas.
- **Ambiente de staging para toda a equipe**: times de frontend, backend e contratos podem trabalhar em paralelo.
- **CI/CD**: provisionar um ambiente novo por pull request, rodar os testes e destruir.

## Configuração

### 1. Criar conta

Crie uma conta gratuita em [Tenderly](https://tenderly.co).

### 2. Configurar variáveis de ambiente

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

### 3. Script de deploy

Crie `scripts/deploy/deploy-to-testnet.sh`:

```bash
#!/bin/bash
cd contracts

forge script script/DeployPaymentVerifier.s.sol \
  --broadcast \
  --rpc-url $TENDERLY_VIRTUAL_TESTNET_RPC \
  --verify \
  --verifier-url $VERIFICATION_URL \
  --private-key $DEPLOYER_PRIVATE_KEY

echo "Contratos deployados. RPC: $TENDERLY_VIRTUAL_TESTNET_RPC"
```

### 4. Executar

```bash
source .env
export VIRTUAL_NETWORK_RPC_URL=$(./create-testnet.sh)
./deploy-to-testnet.sh
```

O RPC Link e os endereços dos contratos serão exibidos no output.

## Multi-Region RPCs

O Tenderly permite escolher a região do RPC (US West, US East, Europa) para **até 30% mais performance** em testes automatizados.

## Snapshot para múltiplos cenários

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

## CI/CD com GitHub Actions

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

## Links úteis

- [Virtual Environments Overview](https://docs.tenderly.co/virtual-environments/overview)
- [Stage Contracts on TestNets](https://docs.tenderly.co/virtual-testnets/ci-cd/stage-contracts)
- [GitHub Actions with Foundry](https://docs.tenderly.co/virtual-environments/ci-cd/github-actions-foundry)
- [Multi-Region RPCs](https://blog.tenderly.co/changelog/virtual-testnet-forking-and-multi-region-rpcs/)
