import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position
from fastapi_project.app.routers.wheels import analyze_ticker_positions, PositionForDetection

def debug_detection():
    """Debug why wheel detection returns 0 opportunities."""
    db = SessionLocal()
    try:
        # Get all positions
        positions = db.query(Position).all()
        print(f"Total positions: {len(positions)}")
        
        # Focus on short put positions that should trigger Cash-Secured Put detection
        short_put_positions = []
        for pos in positions:
            if pos.asset_type == "OPTION" and pos.option_type == "PUT" and pos.short_quantity > 0:
                short_put_positions.append(pos)
                print(f"Short PUT found: {pos.symbol} - Long={pos.long_quantity}, Short={pos.short_quantity}")
        
        print(f"\nFound {len(short_put_positions)} short put positions")
        
        if short_put_positions:
            # Test detection with one specific short put position (JBLU)
            test_pos = None
            for pos in short_put_positions:
                if "JBLU" in pos.symbol:
                    test_pos = pos
                    break
            
            if test_pos:
                print(f"\n--- Testing detection with {test_pos.symbol} ---")
                
                # Convert to PositionForDetection format
                contracts = test_pos.long_quantity - test_pos.short_quantity
                detection_pos = PositionForDetection(
                    id=str(test_pos.id),
                    symbol=test_pos.symbol,
                    shares=test_pos.long_quantity - test_pos.short_quantity,
                    is_option=test_pos.asset_type == "OPTION",
                    underlying_symbol=test_pos.underlying_symbol,
                    option_type=test_pos.option_type,
                    strike_price=test_pos.strike_price,
                    expiration_date=test_pos.expiration_date.isoformat() if test_pos.expiration_date else None,
                    contracts=contracts,
                    market_value=test_pos.market_value or 0.0,
                    source="test"
                )
                
                print(f"PositionForDetection: contracts={detection_pos.contracts}, is_option={detection_pos.is_option}, option_type={detection_pos.option_type}")
                
                # Test analyze_ticker_positions
                ticker = test_pos.underlying_symbol or test_pos.symbol
                result = analyze_ticker_positions(ticker, [detection_pos])
                print(f"Detection result: {result}")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_detection()
