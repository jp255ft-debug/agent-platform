# Ambiente de Desenvolvimento Local — Hardhat Fork

> **Chain ID:** 31337 · **RPC:** http://127.0.0.1:8545 · **ETH:** ♾️ Infinito

## O que é

O Hardhat Network permite iniciar uma instância local que **forka** (copia) o estado de uma rede como Mainnet, Sepolia ou Base. Você tem uma blockchain rodando na sua máquina, com todos os contratos, saldos e estados da rede original, mas pode fazer transações com ETH infinito e usar cheatcodes para manipular o ambiente.

## Por que usar

- Testar o fluxo completo (autenticação → listagem → lease → kill-switch) **sem depender de internet** ou de faucets.
- Reproduzir bugs de forma isolada, com logs detalhados.
- Integrar com testes automatizados no GitHub Actions para validar cada PR.

## Configuração

### 1. Instalar Hardhat

```bash
cd contracts
npm install --save-dev hardhat @nomiclabs/hardhat-ethers ethers
npm install --save-dev @nomicfoundation/hardhat-network-helpers
```

### 2. Configurar `hardhat.config.js`

```javascript
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

### 3. Iniciar o nó

```bash
npx hardhat node --fork https://sepolia.base.org --fork-block-number 12345678
```

Isso criará:
- **20 contas** com 10.000 ETH falsos cada
- RPC em `http://127.0.0.1:8545`
- Chain ID: `31337`

### 4. Conectar MetaMask

| Campo | Valor |
|-------|-------|
| **Network Name** | Hardhat Local |
| **New RPC URL** | `http://127.0.0.1:8545` |
| **Chain ID** | `31337` |
| **Currency Symbol** | `ETH` |

Importe uma conta de teste: pegue a chave privada de uma das contas exibidas no terminal do Hardhat e importe na MetaMask.

## Impersonação de contas

Com o Hardhat, você pode **assumir a identidade de qualquer endereço** da rede forkeada:

```javascript
const helpers = require("@nomicfoundation/hardhat-network-helpers");

// Impersonar um endereço específico
await helpers.impersonateAccount("0x...endereço_do_agente...");

// Agora você pode assinar transações como esse endereço
const impersonatedSigner = await ethers.getSigner("0x...endereço_do_agente...");
await impersonatedSigner.sendTransaction({ to: "...", value: ... });
```

### Outros cheatcodes úteis

| Comando | Descrição |
|---------|-----------|
| `helpers.setBalance(endereco, ethers.parseEther("1000"))` | Definir saldo de qualquer conta |
| `helpers.takeSnapshot()` / `helpers.restoreSnapshot()` | Snapshots para resetar estado |
| `helpers.mine(10)` | Minerar blocos rapidamente |
| `helpers.setNextBlockTimestamp(timestamp)` | Avançar o tempo do bloco |
| `helpers.setStorageAt(endereco, slot, valor)` | Modificar storage de contratos |

## Links úteis

- [Forking other networks (Hardhat docs)](https://v2.hardhat.org/hardhat-network/docs/guides/forking-other-networks)
- [How To Fork Ethereum Mainnet with Hardhat (QuickNode)](https://www.quicknode.com/guides/ethereum-development/smart-contracts/how-to-fork-ethereum-mainnet-with-hardhat)
- [hardhat-network-helpers reference](https://hardhat.org/docs/plugins/hardhat-network-helpers)
