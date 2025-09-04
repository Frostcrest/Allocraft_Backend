import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.routers.wheels import (
    PositionForDetection, 
    WheelDetectionOptions,
    EnhancedPosition,
    calculate_days_to_expiration,
    create_cash_secured_put_result
)

def debug_formatted_positions():
    """Debug the formatted positions creation"""
    print("=== DEBUGGING FORMATTED POSITIONS ===")
    
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
    
    # Create formatted positions (from analyze_ticker_positions)
    formatted_positions = []
    for p in positions:
        print(f"Processing position: {p.symbol}")
        print(f"  is_option: {p.is_option}")
        print(f"  contracts: {p.contracts}")
        print(f"  option_type: {p.option_type}")
        
        is_short_position = p.is_option and (p.contracts or 0) < 0 or not p.is_option and p.shares < 0
        raw_quantity = p.contracts or 0 if p.is_option else p.shares
        days_to_expiration = calculate_days_to_expiration(p.expiration_date) if p.expiration_date else None

        print(f"  is_short_position: {is_short_position}")
        print(f"  raw_quantity: {raw_quantity}")
        print(f"  days_to_expiration: {days_to_expiration}")

        enhanced_pos = EnhancedPosition(
            type='call' if p.is_option and p.option_type == 'CALL' else 'put' if p.is_option and p.option_type == 'PUT' else 'stock',
            symbol=p.symbol,
            quantity=abs(raw_quantity),
            position='short' if is_short_position else 'long',
            strike_price=p.strike_price,
            expiration_date=p.expiration_date,
            days_to_expiration=days_to_expiration,
            market_value=p.market_value,
            raw_quantity=raw_quantity,
            source=p.source
        )
        formatted_positions.append(enhanced_pos)
        
        print(f"  Enhanced position: {enhanced_pos}")
    
    # Now test create_cash_secured_put_result
    print(f"\n=== TESTING create_cash_secured_put_result ===")
    
    # Get short puts
    short_puts = [p for p in positions if p.is_option and p.option_type == 'PUT' and (p.contracts or 0) < 0]
    print(f"Short puts: {len(short_puts)}")
    
    total_stock_shares = 0  # No stock positions for JBLU
    
    options = WheelDetectionOptions(
        risk_tolerance="moderate",
        include_historical=False,
        cash_balance=None
    )
    
    try:
        result = create_cash_secured_put_result("JBLU", formatted_positions, short_puts, total_stock_shares, options)
        print(f"✅ create_cash_secured_put_result succeeded:")
        print(f"   Strategy: {result.strategy}")
        print(f"   Confidence: {result.confidence_score}")
        print(f"   Description: {result.description}")
        return result
    except Exception as e:
        print(f"❌ create_cash_secured_put_result failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_formatted_positions()
