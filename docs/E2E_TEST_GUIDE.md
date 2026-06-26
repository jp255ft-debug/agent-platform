# Guia de Teste End-to-End (E2E) — Agent Platform

> **Versão:** 2.1 — Ecossistema completo de testes
> **Data:** 26/06/2026
> **Redes Suportadas:** Hardhat Local (31337) · Tenderly Virtual TestNet · Base Sepolia (84532)

---

## ⚡ Quick Start (5 minutos)

Quer ver o fluxo funcionando agora? Vá direto para o guia da **[Testnet Pública (Base Sepolia)](test-environments/testnet.md)** e execute o `frontend-test.html`:

```bash
start frontend-test.html
```

Ou, se preferir testar localmente sem depender de internet, use o **[Hardhat Fork](test-environments/local.md)**.

---

## 💰 Custo das Ferramentas

| Ferramenta | Custo | Licença |
|------------|-------|---------|
| **Hardhat Fork** | ✅ Gratuito | MIT (Open Source) |
| **Tenderly Virtual TestNet** | ✅ Gratuito (até 5 ambientes simultâneos) | Freemium |
| **Locust** | ✅ Gratuito | MIT (Open Source) |
| **k6** | ✅ Gratuito | AGPL (Open Source, Grafana Labs) |
| **Kafka UI (Kafbat)** | ✅ Gratuito | Apache 2.0 (Open Source) |
| **Base Sepolia** | ✅ Gratuito (faucet) | Rede pública |

**Custo total para começar: R$ 0,00** — todas as ferramentas são open-source ou têm tier gratuito.

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

## 📚 Guias Detalhados por Ambiente

| # | Ambiente | Guia | Quando usar |
|---|----------|------|-------------|
| 1 | 🏗️ **Hardhat Fork** | [`docs/test-environments/local.md`](test-environments/local.md) | Desenvolvimento diário, iteração rápida |
| 2 | ☁️ **Tenderly Staging** | [`docs/test-environments/staging.md`](test-environments/staging.md) | Validação com dados reais antes do deploy |
| 3 | 📊 **Testes de Carga** | [`docs/test-environments/load.md`](test-environments/load.md) | Locust (Python) ou k6 (JS) |
| 4 | 🌐 **Base Sepolia** | [`docs/test-environments/testnet.md`](test-environments/testnet.md) | Teste em rede pública com faucet |

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

## 🖥️ Frontend de Teste

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

## 🤖 Agente Autônomo com DeepSeek

Para simular um **agente autônomo real** que toma decisões como um cliente:

```bash
export DEEPSEEK_API_KEY=sua_chave_aqui
python scripts/simulate_agent.py
```

O script completo está em [`scripts/simulate_agent.py`](../scripts/simulate_agent.py). Ele:
1. Cria um agente na plataforma
2. Gera uma API Key
3. Lista GPUs disponíveis
4. Consulta a DeepSeek para decidir qual GPU alugar
5. Solicita a lease
6. Verifica o status

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
