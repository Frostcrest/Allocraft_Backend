import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.routers.wheels import (
    PositionForDetection, 
    analyze_ticker_positions,
    WheelDetectionOptions
)

def debug_jblu_with_endpoint_options():
    """Debug JBLU analysis with exact endpoint options"""
    print("=== DEBUGGING JBLU WITH ENDPOINT OPTIONS ===")
    
    # Create the exact position from our debug output
    jblu_position = PositionForDetection(
        id="9",
        symbol="JBLU  251017P00005000",
        shares=-5.0,
        is_option=True,
        underlying_symbol="JBLU",
        option_type="PUT", 
        strike_price=5.0,
        expiration_date="2025-10-17T00:00:00",
        contracts=-5.0,
        market_value=160.0,
        source="unknown"
    )
    
    # Test with None options (like the endpoint might pass)
    print("1. Testing with None options...")
    try:
        result1 = analyze_ticker_positions("JBLU", [jblu_position], None)
        print(f"   Result with None: {result1}")
    except Exception as e:
        print(f"   Error with None: {e}")
        import traceback
        traceback.print_exc()
    
    # Test with WheelDetectionOptions object
    print("\n2. Testing with WheelDetectionOptions object...")
    options = WheelDetectionOptions(
        risk_tolerance="moderate",
        include_historical=False,
        cash_balance=None
    )
    try:
        result2 = analyze_ticker_positions("JBLU", [jblu_position], options)
        print(f"   Result with options: {result2}")
    except Exception as e:
        print(f"   Error with options: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_jblu_with_endpoint_options()
