import requests
import json

# Test script to verify mock endpoints
BASE_URL = "http://localhost:8000"

# Get a token first
login_data = {
    "username": "admin@example.com",
    "password": "admin123"
}

print("🔐 Logging in...")
response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
print(f"Login response status: {response.status_code}")
print(f"Login response: {response.text}")
if response.status_code == 200:
    token = response.json()["access_token"]
    print("✅ Login successful")
else:
    print(f"❌ Login failed: {response.status_code}")
    exit()

# Headers for authenticated requests
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("\n📊 Testing mock endpoints...")

# Test mock positions endpoint
print("\n1. Testing /schwab/mock/positions")
response = requests.get(f"{BASE_URL}/schwab/mock/positions", headers=headers)
if response.status_code == 200:
    data = response.json()
    print(f"✅ Mock positions: {len(data)} accounts")
    for account in data:
        print(f"   - Account {account['accountNumber']}: {len(account['positions'])} positions")
else:
    print(f"❌ Mock positions failed: {response.status_code}")

# Test load mock data endpoint
print("\n2. Testing /schwab/mock/load-data")
response = requests.post(f"{BASE_URL}/schwab/mock/load-data", headers=headers)
if response.status_code == 200:
    data = response.json()
    print(f"✅ Mock data loaded: {data['result']}")
else:
    print(f"❌ Load mock data failed: {response.status_code}")

# Test unified positions endpoint
print("\n3. Testing /stocks/all-positions")
response = requests.get(f"{BASE_URL}/stocks/all-positions", headers=headers)
if response.status_code == 200:
    data = response.json()
    print(f"✅ All positions: {len(data['positions'])} total positions")
    stocks = [p for p in data['positions'] if not p.get('isOption')]
    options = [p for p in data['positions'] if p.get('isOption')]
    print(f"   - Stocks: {len(stocks)}")
    print(f"   - Options: {len(options)}")
else:
    print(f"❌ All positions failed: {response.status_code}")

print("\n🎉 Mock data system test complete!")
