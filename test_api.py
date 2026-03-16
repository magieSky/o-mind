import json
import urllib.request

# Test health
req = urllib.request.Request('http://172.24.0.4:8000/health')
with urllib.request.urlopen(req) as resp:
    print("Health:", resp.read().decode())

# Create memory
data = json.dumps({
    "content": "用户喜欢绿色",
    "tags": ["preference"],
    "source": "integration-test"
}).encode('utf-8')

req = urllib.request.Request(
    'http://172.24.0.4:8000/api/memories',
    data=data,
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    print("Create:", resp.read().decode())

# List memories
req = urllib.request.Request('http://172.24.0.4:8000/api/memories?limit=5')
with urllib.request.urlopen(req) as resp:
    print("List:", resp.read().decode())
