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

def debug_analyze_ticker_positions():
    """Debug analyze_ticker_positions with JBLU example"""
    print("=== DEBUGGING analyze_ticker_positions ===")
    
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
    
    options = WheelDetectionOptions(
        risk_tolerance="moderate",
        include_historical=False,
        cash_balance=None
    )
    
    print(f"Testing with position: {jblu_position}")
    print(f"Position details:")
    print(f"  symbol: {jblu_position.symbol}")
    print(f"  is_option: {jblu_position.is_option}")
    print(f"  option_type: {jblu_position.option_type}")
    print(f"  contracts: {jblu_position.contracts}")
    print(f"  shares: {jblu_position.shares}")
    
    # Test the function
    try:
        result = analyze_ticker_positions("JBLU", [jblu_position], options)
        print(f"\n✅ Result: {result}")
        if result:
            print(f"Strategy: {result.strategy}")
            print(f"Confidence: {result.confidence_score}")
        else:
            print("❌ No strategy detected")
    except Exception as e:
        print(f"❌ Error in analyze_ticker_positions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_analyze_ticker_positions()
