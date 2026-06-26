# Testes de Carga — Locust & k6

> **Custo:** Ambos open-source · **Locust:** Python · **k6:** JavaScript/Go

## Por que testar carga

- Simular **centenas de agentes autônomos** solicitando leases simultaneamente.
- Testar a resiliência do backend (API, PostgreSQL, Redis, Kafka) sob pico de demanda.
- Validar rate limiting, filas e o comportamento do kill-switch sob estresse.

---

## 1. Locust (Python)

### Instalação

```bash
pip install locust
```

### Script de teste

Crie `scripts/load-test/locustfile.py`:

```python
from locust import HttpUser, task, between
import uuid

class AgentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        self.owner_address = "0x" + "0"*40

        resp = self.client.post("/api/v1/agents", json={
            "agent_id": self.agent_id,
            "owner_address": self.owner_address
        })

        resp = self.client.post(
            f"/api/v1/agents/{self.agent_id}/api-keys",
            json={"expires_in_days": 90}
        )
        self.api_key = resp.json()["plain_key"]
        self.headers = {"X-API-Key": self.api_key}

    @task(3)
    def list_gpus(self):
        self.client.get("/api/v1/gpu/hardware", headers=self.headers)

    @task(1)
    def lease_gpu(self):
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
        self.client.get("/api/v1/gpu/leases", headers=self.headers)
```

### Executar

```bash
# Com interface web
locust -f scripts/load-test/locustfile.py --host http://localhost:8000

# Headless para CI/CD
locust -f scripts/load-test/locustfile.py --host http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 5m \
  --html report.html --csv results
```

Abra `http://localhost:8089` para definir o número de usuários.

---

## 2. k6 (JavaScript)

### Instalação

```bash
npm install -g k6
```

### Script de teste

Crie `scripts/load-test/k6-test.js`:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomString } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

export const options = {
  stages: [
    { duration: '2m', target: 50 },
    { duration: '5m', target: 50 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const agentId = `agent_${randomString(8)}`;
  const headers = { 'Content-Type': 'application/json' };

  let res = http.post('http://localhost:8000/api/v1/agents',
    JSON.stringify({ agent_id: agentId, owner_address: '0x' + '0'.repeat(40) }),
    { headers }
  );
  check(res, { 'agent created': (r) => r.status === 201 });

  const apiKeyResp = http.post(
    `http://localhost:8000/api/v1/agents/${agentId}/api-keys`,
    JSON.stringify({ expires_in_days: 90 }),
    { headers }
  );
  const apiKey = apiKeyResp.json('plain_key');
  const authHeaders = { 'X-API-Key': apiKey };

  res = http.get('http://localhost:8000/api/v1/gpu/hardware', { headers: authHeaders });
  check(res, { 'list GPUs': (r) => r.status === 200 });

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

### Executar

```bash
k6 run scripts/load-test/k6-test.js
k6 run --out json=results.json scripts/load-test/k6-test.js
```

---

## Comparação Rápida

| Característica | Locust | k6 |
|----------------|--------|-----|
| Linguagem | Python | JavaScript (ES6) |
| Performance | Bom (greenlets) | **Excelente (Go)** |
| Concorrência | Síncrona | **Assíncrona** |
| Interface | Web UI nativa | CLI + extensões |
| CI/CD | Suportado | **Nativo** |
| gRPC | Limitado | **Nativo** |

> **Escolha:** Use **Locust** se prefere Python e quer interface web. Use **k6** para CI/CD e testes mais pesados.

## Links úteis

- [Locust Documentation](https://docs.locust.io/)
- [k6 Documentation](https://k6.io/docs/)
- [k6 GitHub - API testing examples](https://github.com/ldesoto/k6-API-TESTING)
