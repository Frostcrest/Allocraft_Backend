import requests
import json

# Read the auth token
with open('c:/Users/haloi/Documents/GitHub/Allocraft/test_token.txt', 'r') as f:
    token = f.read().strip()

# Trigger sync
url = "http://localhost:8000/api/schwab/sync"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("Triggering Schwab sync...")
response = requests.post(url, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
