import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position
from fastapi_project.app.routers.wheels import (
    PositionForDetection, 
    group_positions_by_ticker,
    analyze_ticker_positions,
    WheelDetectionOptions
)

def debug_full_detection_endpoint():
    """Debug the full detection endpoint logic"""
    db = SessionLocal()
    try:
        print("=== DEBUGGING FULL DETECTION ENDPOINT ===")
        
        # Simulate the request
        account_id = 1
        specific_tickers = []
        options = WheelDetectionOptions(
            risk_tolerance="moderate",
            include_historical=False,
            cash_balance=None
        )
        
        print(f"Request params: account_id={account_id}, specific_tickers={specific_tickers}")
        
        # Get positions from unified tables
        query = db.query(Position).filter(Position.is_active == True)
        
        if account_id:
            query = query.filter(Position.account_id == account_id)
            
        positions = query.all()
        print(f"Found {len(positions)} active positions for account {account_id}")
        
        # Convert to detection format
        detection_positions = []
        for pos in positions:
            # Skip if specific tickers requested and this isn't one of them
            ticker = pos.underlying_symbol or pos.symbol
            if specific_tickers and ticker.upper() not in [t.upper() for t in specific_tickers]:
                continue
                
            # Calculate contracts for options
            contracts = None
            if pos.asset_type == "OPTION":
                # Net contracts = long - short quantity
                contracts = pos.long_quantity - pos.short_quantity
                
            detection_pos = PositionForDetection(
                id=str(pos.id),
                symbol=pos.symbol,
                shares=pos.long_quantity - pos.short_quantity,  # Net shares
                is_option=pos.asset_type == "OPTION",
                underlying_symbol=pos.underlying_symbol,
                option_type=pos.option_type,
                strike_price=pos.strike_price,
                expiration_date=pos.expiration_date.isoformat() if pos.expiration_date else None,
                contracts=contracts,
                market_value=pos.market_value or 0.0,
                source=pos.data_source or "unknown"
            )
            detection_positions.append(detection_pos)
        
        print(f"Converted to {len(detection_positions)} detection positions")
        
        if not detection_positions:
            print("❌ No detection positions found - returning empty")
            return []
        
        # Group by ticker and analyze
        grouped_positions = group_positions_by_ticker(detection_positions)
        print(f"Grouped into {len(grouped_positions)} tickers:")
        for ticker, ticker_positions in grouped_positions.items():
            print(f"  {ticker}: {len(ticker_positions)} positions")
        
        results = []
        
        for ticker, ticker_positions in grouped_positions.items():
            print(f"\n--- Analyzing {ticker} ---")
            print(f"Positions for {ticker}:")
            for pos in ticker_positions:
                print(f"  {pos.symbol} ({pos.option_type if pos.is_option else 'STOCK'}): contracts={pos.contracts if pos.is_option else pos.shares}")
            
            detection_result = analyze_ticker_positions(ticker, ticker_positions, options)
            if detection_result:
                print(f"✅ {ticker}: Found {detection_result.strategy} strategy")
                results.append(detection_result)
            else:
                print(f"❌ {ticker}: No strategy detected")
        
        print(f"\n=== FINAL RESULTS ===")
        print(f"Total strategies detected: {len(results)}")
        for result in results:
            print(f"  {result.ticker}: {result.strategy} (confidence: {result.confidence_score})")
        
        return results
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_full_detection_endpoint()
