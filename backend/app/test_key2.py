import urllib.request, json

# Create API Key
body = json.dumps({"expires_in_days": 90}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/v1/agents/agent_test_789/api-keys",
    data=body,
    headers={"Content-Type": "application/json", "X-Bootstrap-Key": "true"}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("CREATE:", resp.status, json.dumps(data, indent=2))
print()
print("KEY_ID:", data["key_id"])
print("PLAIN_KEY:", data["plain_key"])

# Now try to use the key
full_key = data["key_id"] + "." + data["plain_key"]
print("FULL_KEY:", full_key)

body2 = json.dumps({"expires_in_days": 30}).encode()
req2 = urllib.request.Request(
    "http://localhost:8000/api/v1/agents/agent_test_789/api-keys",
    data=body2,
    headers={"Content-Type": "application/json", "X-API-Key": full_key}
)
try:
    resp2 = urllib.request.urlopen(req2)
    data2 = json.loads(resp2.read())
    print("AUTH:", resp2.status, json.dumps(data2, indent=2))
except urllib.error.HTTPError as e:
    print("AUTH ERROR:", e.code, e.read().decode())
