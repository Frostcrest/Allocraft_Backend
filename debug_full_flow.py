import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position
from fastapi_project.app.routers.wheels import PositionForDetection

def test_full_detection_flow():
    """Test the complete detection flow step by step"""
    
    db = SessionLocal()
    try:
        # Get JBLU position
        jblu_pos = None
        for pos in db.query(Position).all():
            if "JBLU" in pos.symbol and pos.asset_type == "OPTION":
                jblu_pos = pos
                break
        
        if not jblu_pos:
            print("No JBLU position found")
            return
            
        print(f"Testing with: {jblu_pos.symbol}")
        
        # Convert to PositionForDetection
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
        
        print(f"PositionForDetection created: {detection_pos}")
        
        # Import detection functions
        from fastapi_project.app.routers.wheels import (
            is_cash_secured_put, 
            create_cash_secured_put_result,
            EnhancedPosition,
            calculate_days_to_expiration
        )
        
        # Manually simulate the analyze_ticker_positions logic
        ticker = jblu_pos.underlying_symbol or jblu_pos.symbol
        positions = [detection_pos]
        
        stock_positions = [p for p in positions if not p.is_option]
        option_positions = [p for p in positions if p.is_option]
        put_options = [p for p in option_positions if p.option_type == 'PUT']
        short_puts = [p for p in put_options if (p.contracts or 0) < 0]
        total_stock_shares = sum(p.shares for p in stock_positions)
        
        print(f"Filtered short_puts: {len(short_puts)}")
        print(f"is_cash_secured_put check: {is_cash_secured_put(short_puts)}")
        
        # Create formatted positions
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
        
        print(f"Formatted positions: {len(formatted_positions)}")
        for fp in formatted_positions:
            print(f"  {fp.type} {fp.position} {fp.symbol} qty={fp.quantity}")
        
        if is_cash_secured_put(short_puts):
            print("Calling create_cash_secured_put_result...")
            try:
                result = create_cash_secured_put_result(ticker, formatted_positions, short_puts, total_stock_shares, None)
                print(f"Result: {result}")
                return result
            except Exception as e:
                print(f"Error in create_cash_secured_put_result: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("is_cash_secured_put returned False")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_full_detection_flow()
