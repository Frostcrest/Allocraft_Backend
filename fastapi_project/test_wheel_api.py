import requests
import json

# Test the wheel detection API directly
url = "http://127.0.0.1:8000/wheels/detect"

payload = {
    "account_id": 1,
    "specific_tickers": [],
    "options": {
        "risk_tolerance": "moderate",
        "include_historical": False,
        "cash_balance": None
    }
}

print("🔍 Testing wheel detection API...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=10)
    
    print(f"\n📊 Response Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Success! Found {len(result)} opportunities:")
        for i, opportunity in enumerate(result):
            print(f"\n  Opportunity {i+1}:")
            print(f"    Ticker: {opportunity.get('ticker')}")
            print(f"    Strategy: {opportunity.get('strategy')}")
            print(f"    Confidence: {opportunity.get('confidence_score')}%")
            print(f"    Positions: {len(opportunity.get('positions', []))}")
    else:
        print(f"\n❌ Error Response:")
        print(response.text)
        
except Exception as e:
    print(f"\n💥 Request failed: {e}")
