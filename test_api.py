"""测试 API 端点"""
import requests
import json

# 测试 /api/backups
try:
    r = requests.get('http://127.0.0.1:8080/api/backups', params={'limit': 10}, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")

# 测试 /api/status
try:
    r = requests.get('http://127.0.0.1:8080/api/status', timeout=5)
    print(f"\nStatus API: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
