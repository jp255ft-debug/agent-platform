import urllib.request, json

# Create API Key
body = json.dumps({'agent_id': 'agent_test_123', 'expires_in_days': 90}).encode()
req = urllib.request.Request('http://localhost:8000/api/v1/agents/agent_test_123/api-keys', data=body, headers={'Content-Type': 'application/json', 'X-Bootstrap-Key': 'true'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print('CREATE:', resp.status, data)

full_key = f"{data['key_id']}.{data['plain_key']}"
print('FULL_KEY:', full_key)

# Use API Key
body2 = json.dumps({'agent_id': 'agent_test_123', 'expires_in_days': 30}).encode()
req2 = urllib.request.Request('http://localhost:8000/api/v1/agents/agent_test_123/api-keys', data=body2, headers={'Content-Type': 'application/json', 'X-API-Key': full_key})
resp2 = urllib.request.urlopen(req2)
data2 = json.loads(resp2.read())
print('AUTH:', resp2.status, data2)
