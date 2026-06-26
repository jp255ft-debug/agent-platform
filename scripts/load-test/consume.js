// k6 load test for /api/v1/consume endpoint
// Run: k6 run scripts/load-test/consume.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const consumeDuration = new Trend('consume_duration');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const VUS = __ENV.VUS || 10;
const DURATION = __ENV.DURATION || '30s';

export const options = {
  stages: [
    { duration: '10s', target: VUS },       // Ramp-up
    { duration: DURATION, target: VUS },     // Steady state
    { duration: '10s', target: 0 },          // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],       // 95% of requests must complete below 2s
    errors: ['rate<0.1'],                    // Error rate must be below 10%
  },
};

// Simulate a realistic agent address
function generateAgentAddress() {
  const chars = '0123456789abcdef';
  let addr = '0x';
  for (let i = 0; i < 40; i++) {
    addr += chars[Math.floor(Math.random() * chars.length)];
  }
  return addr;
}

export default function () {
  const agentAddress = generateAgentAddress();
  const payload = JSON.stringify({
    agent_address: agentAddress,
    resource_type: 'compute',
    units: Math.floor(Math.random() * 100) + 1,
    tx_hash: `0x${Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join('')}`,
    amount: (Math.floor(Math.random() * 1000) + 1).toString(),
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '10s',
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/api/v1/consume`, payload, params);
  const duration = Date.now() - start;

  consumeDuration.add(duration);
  errorRate.add(res.status >= 400);

  check(res, {
    'status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'response time < 5s': (r) => duration < 5000,
  });

  // Simulate think time between requests
  sleep(Math.random() * 0.5 + 0.1);
}
