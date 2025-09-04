import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.routers.wheels import (
    PositionForDetection, 
    WheelDetectionOptions,
    is_cash_secured_put,
    is_covered_call,
    is_full_wheel,
    is_naked_stock
)

def debug_detection_conditions():
    """Debug the detection conditions step by step"""
    print("=== DEBUGGING DETECTION CONDITIONS ===")
    
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
    
    positions = [jblu_position]
    
    # Manually implement the analyze_ticker_positions logic step by step
    print("1. Separating positions...")
    stock_positions = [p for p in positions if not p.is_option]
    option_positions = [p for p in positions if p.is_option]
    call_options = [p for p in option_positions if p.option_type == 'CALL']
    put_options = [p for p in option_positions if p.option_type == 'PUT']
    
    print(f"   Stock positions: {len(stock_positions)}")
    print(f"   Option positions: {len(option_positions)}")
    print(f"   Call options: {len(call_options)}")
    print(f"   Put options: {len(put_options)}")
    
    print("\n2. Calculating totals...")
    total_stock_shares = sum(p.shares for p in stock_positions)
    print(f"   Total stock shares: {total_stock_shares}")
    
    print("\n3. Separating long/short options...")
    short_calls = [p for p in call_options if (p.contracts or 0) < 0]
    short_puts = [p for p in put_options if (p.contracts or 0) < 0]
    
    print(f"   Short calls: {len(short_calls)}")
    print(f"   Short puts: {len(short_puts)}")
    
    for put in put_options:
        print(f"   PUT option: {put.symbol}, contracts={put.contracts}, option_type='{put.option_type}'")
    
    for short_put in short_puts:
        print(f"   SHORT PUT: {short_put.symbol}, contracts={short_put.contracts}")
    
    print("\n4. Testing detection conditions...")
    
    # Test each condition
    print(f"   is_full_wheel({total_stock_shares}, {len(short_calls)}, {len(short_puts)}): ", end="")
    full_wheel_result = is_full_wheel(total_stock_shares, short_calls, short_puts)
    print(full_wheel_result)
    
    print(f"   is_covered_call({total_stock_shares}, {len(short_calls)}): ", end="")
    covered_call_result = is_covered_call(total_stock_shares, short_calls)
    print(covered_call_result)
    
    print(f"   is_cash_secured_put({len(short_puts)}): ", end="")
    csp_result = is_cash_secured_put(short_puts)
    print(csp_result)
    
    print(f"   is_naked_stock({total_stock_shares}, {len(option_positions)}): ", end="")
    naked_stock_result = is_naked_stock(total_stock_shares, option_positions)
    print(naked_stock_result)
    
    print("\n5. Expected flow:")
    if full_wheel_result:
        print("   Should create full_wheel_result")
    elif covered_call_result:
        print("   Should create covered_call_result")
    elif csp_result:
        print("   Should create cash_secured_put_result ✅")
    elif naked_stock_result and total_stock_shares >= 100:
        print("   Should create naked_stock_result")
    else:
        print("   No strategy detected ❌")

if __name__ == "__main__":
    debug_detection_conditions()
