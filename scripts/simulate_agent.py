#!/usr/bin/env python3
"""
Simulador de agente autônomo para testes E2E.

Usa a DeepSeek API para simular um agente real que toma decisões
sobre qual GPU alugar com base nas opções disponíveis.

Uso:
    python scripts/simulate_agent.py

Variáveis de ambiente:
    API_BASE_URL    (default: http://localhost:8000)
    DEEPSEEK_API_KEY (obrigatório)
"""

import os
import sys
import requests
from openai import OpenAI

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    print("❌ Erro: DEEPSEEK_API_KEY não configurada.")
    print("   Exporte a variável: export DEEPSEEK_API_KEY=sua_chave")
    sys.exit(1)

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
    resp.raise_for_status()
    return resp.json()


def criar_api_key(agent_id):
    """Passo 2: Gerar API Key."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/agents/{agent_id}/api-keys",
        json={"expires_in_days": 90}
    )
    resp.raise_for_status()
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
