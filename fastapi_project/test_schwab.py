#!/usr/bin/env python3
"""
Test script to check Schwab configuration and functionality
"""
import os
import sys
import requests
import json
import pytest

# Skip this integration test module unless explicitly enabled
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION", "0").lower() in ("1", "true", "yes")
if not RUN_INTEGRATION:
    pytest.skip(
        "Integration test (requires running backend at localhost:8000). Set RUN_INTEGRATION=1 to enable.",
        allow_module_level=True,
    )

def test_schwab_config():
    """Test Schwab configuration"""
    print("=== Testing Schwab Configuration ===")
    
    # Check environment variables
    client_id = os.getenv("SCHWAB_CLIENT_ID", "")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET", "")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "https://allocraft-backend.onrender.com/schwab/callback")
    frontend_url = os.getenv("FRONTEND_URL", "https://allocraft.app")
    
    print(f"SCHWAB_CLIENT_ID: {'✓ Set' if client_id else '✗ Not set'}")
    print(f"SCHWAB_CLIENT_SECRET: {'✓ Set' if client_secret else '✗ Not set'}")
    print(f"SCHWAB_REDIRECT_URI: {redirect_uri}")
    print(f"FRONTEND_URL: {frontend_url}")
    
    if not client_id:
        print("\n❌ SCHWAB_CLIENT_ID is required for Schwab OAuth")
        return False
    
    if not client_secret:
        print("\n❌ SCHWAB_CLIENT_SECRET is required for Schwab OAuth")
        return False
    
    print("\n✅ Schwab OAuth configuration looks complete")
    return True

def test_backend_endpoints():
    """Test backend endpoints"""
    print("\n=== Testing Backend Endpoints ===")
    
    # First login to get a token
    try:
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        response = requests.post(
            "http://127.0.0.1:8000/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            print("✅ Login successful")
            
            # Test Schwab auth-url endpoint
            headers = {"Authorization": f"Bearer {access_token}"}
            schwab_response = requests.get("http://127.0.0.1:8000/schwab/auth-url", headers=headers)
            
            if schwab_response.status_code == 200:
                auth_data = schwab_response.json()
                print("✅ Schwab auth-url endpoint working")
                print(f"Auth URL: {auth_data.get('auth_url', 'N/A')[:100]}...")
                return True
            elif schwab_response.status_code == 500:
                error_data = schwab_response.json()
                print(f"❌ Schwab auth-url failed: {error_data.get('detail', 'Unknown error')}")
                return False
            else:
                print(f"❌ Schwab auth-url returned {schwab_response.status_code}")
                return False
        else:
            print(f"❌ Login failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server. Make sure it's running on port 8000")
        return False
    except Exception as e:
        print(f"❌ Error testing endpoints: {e}")
        return False

def main():
    """Main test function"""
    print("Schwab Integration Test")
    print("=" * 50)
    
    config_ok = test_schwab_config()
    endpoints_ok = test_backend_endpoints()
    
    print("\n" + "=" * 50)
    if config_ok and endpoints_ok:
        print("✅ All tests passed! Schwab integration should work.")
    else:
        print("❌ Some tests failed. Check the issues above.")
        
    print("\n💡 To set up Schwab OAuth:")
    print("1. Go to https://developer.schwab.com/")
    print("2. Create an app and get Client ID and Secret")
    print("3. Set environment variables:")
    print("   - SCHWAB_CLIENT_ID=your_client_id")
    print("   - SCHWAB_CLIENT_SECRET=your_client_secret")
    print("   - SCHWAB_REDIRECT_URI=https://allocraft-backend.onrender.com/schwab/callback")

if __name__ == "__main__":
    main()
