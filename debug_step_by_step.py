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
    is_cash_secured_put,
    create_cash_secured_put_result
)

def debug_analyze_ticker_positions_step_by_step():
    """Step by step debug of analyze_ticker_positions"""
    print("=== STEP BY STEP DEBUG ===")
    
    # Setup
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
    
    ticker = "JBLU"
    positions = [jblu_position]
    options = WheelDetectionOptions(
        risk_tolerance="moderate",
        include_historical=False,
        cash_balance=None
    )
    
    print(f"Input: ticker={ticker}, positions={len(positions)}, options={options}")
    
    # Step 1: Separate positions
    stock_positions = [p for p in positions if not p.is_option]
    option_positions = [p for p in positions if p.is_option]
    call_options = [p for p in option_positions if p.option_type == 'CALL']
    put_options = [p for p in option_positions if p.option_type == 'PUT']
    
    print(f"Step 1: stock={len(stock_positions)}, options={len(option_positions)}, calls={len(call_options)}, puts={len(put_options)}")
    
    # Step 2: Calculate total stock shares
    total_stock_shares = sum(p.shares for p in stock_positions)
    print(f"Step 2: total_stock_shares={total_stock_shares}")
    
    # Step 3: Separate long/short options
    short_calls = [p for p in call_options if (p.contracts or 0) < 0]
    short_puts = [p for p in put_options if (p.contracts or 0) < 0]
    
    print(f"Step 3: short_calls={len(short_calls)}, short_puts={len(short_puts)}")
    
    # Step 4: Enhanced position formatting
    formatted_positions = []
    for p in positions:
        is_short_position = p.is_option and (p.contracts or 0) < 0 or not p.is_option and p.shares < 0
        raw_quantity = p.contracts or 0 if p.is_option else p.shares
        days_to_expiration = calculate_days_to_expiration(p.expiration_date) if p.expiration_date else None

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
    
    print(f"Step 4: formatted_positions={len(formatted_positions)}")
    for fp in formatted_positions:
        print(f"   {fp.type} {fp.position} {fp.symbol} qty={fp.quantity}")
    
    # Step 5: Detection logic
    print(f"Step 5: Testing detection conditions...")
    
    # Test is_cash_secured_put
    csp_result = is_cash_secured_put(short_puts)
    print(f"   is_cash_secured_put({len(short_puts)}): {csp_result}")
    
    if csp_result:
        print(f"   Calling create_cash_secured_put_result...")
        print(f"   Parameters:")
        print(f"     ticker: {ticker}")
        print(f"     formatted_positions: {len(formatted_positions)}")
        print(f"     short_puts: {len(short_puts)}")
        print(f"     total_stock_shares: {total_stock_shares}")
        print(f"     options: {options}")
        
        try:
            result = create_cash_secured_put_result(ticker, formatted_positions, short_puts, total_stock_shares, options)
            print(f"   ✅ SUCCESS: {result.strategy}")
            return result
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None
    else:
        print(f"   ❌ is_cash_secured_put returned False")
        return None

if __name__ == "__main__":
    debug_analyze_ticker_positions_step_by_step()
