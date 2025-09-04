import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position
from fastapi_project.app.routers.wheels import PositionForDetection

def debug_analyze_ticker_positions(ticker, positions):
    """Debug version of analyze_ticker_positions with detailed logging"""
    
    print(f"\n=== Analyzing {ticker} ===")
    print(f"Total positions: {len(positions)}")
    
    stock_positions = [p for p in positions if not p.is_option]
    option_positions = [p for p in positions if p.is_option]
    call_options = [p for p in option_positions if p.option_type == 'CALL']
    put_options = [p for p in option_positions if p.option_type == 'PUT']
    
    print(f"Stock positions: {len(stock_positions)}")
    print(f"Option positions: {len(option_positions)}")
    print(f"Call options: {len(call_options)}")
    print(f"Put options: {len(put_options)}")
    
    # Calculate total stock holdings
    total_stock_shares = sum(p.shares for p in stock_positions)
    print(f"Total stock shares: {total_stock_shares}")
    
    # Separate long/short options - Use signed values
    short_calls = [p for p in call_options if (p.contracts or 0) < 0]
    short_puts = [p for p in put_options if (p.contracts or 0) < 0]
    
    print(f"Short calls: {len(short_calls)}")
    print(f"Short puts: {len(short_puts)}")
    
    for put in put_options:
        print(f"  PUT: {put.symbol} contracts={put.contracts} option_type={put.option_type}")
    
    for short_put in short_puts:
        print(f"  SHORT PUT: {short_put.symbol} contracts={short_put.contracts}")
    
    # Test the detection conditions
    from fastapi_project.app.routers.wheels import is_cash_secured_put
    csp_result = is_cash_secured_put(short_puts)
    print(f"is_cash_secured_put result: {csp_result}")
    
    return None

def debug_detection():
    """Debug why wheel detection returns 0 opportunities."""
    db = SessionLocal()
    try:
        # Get all positions
        positions = db.query(Position).all()
        print(f"Total positions: {len(positions)}")
        
        # Test with JBLU position
        jblu_pos = None
        for pos in positions:
            if "JBLU" in pos.symbol and pos.asset_type == "OPTION":
                jblu_pos = pos
                break
        
        if jblu_pos:
            print(f"\n--- Testing detection with {jblu_pos.symbol} ---")
            
            # Convert to PositionForDetection format
            contracts = jblu_pos.long_quantity - jblu_pos.short_quantity
            detection_pos = PositionForDetection(
                id=str(jblu_pos.id),
                symbol=jblu_pos.symbol,
                shares=jblu_pos.long_quantity - jblu_pos.short_quantity,
                is_option=jblu_pos.asset_type == "OPTION",
                underlying_symbol=jblu_pos.underlying_symbol,
                option_type=jblu_pos.option_type,
                strike_price=jblu_pos.strike_price,
                expiration_date=jblu_pos.expiration_date.isoformat() if jblu_pos.expiration_date else None,
                contracts=contracts,
                market_value=jblu_pos.market_value or 0.0,
                source="test"
            )
            
            print(f"DB position: option_type='{jblu_pos.option_type}', asset_type='{jblu_pos.asset_type}'")
            print(f"Detection position: option_type='{detection_pos.option_type}', contracts={detection_pos.contracts}")
            
            # Test the debug function
            ticker = jblu_pos.underlying_symbol or jblu_pos.symbol
            debug_analyze_ticker_positions(ticker, [detection_pos])
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_detection()
