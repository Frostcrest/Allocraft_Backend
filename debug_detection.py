import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position
from fastapi_project.app.routers.wheels import analyze_ticker_positions

def debug_detection():
    """Debug why wheel detection returns 0 opportunities."""
    db = SessionLocal()
    try:
        # Get all positions
        positions = db.query(Position).all()
        print(f"Total positions: {len(positions)}")
        
        # Group by ticker to see what we have
        by_ticker = {}
        for pos in positions:
            ticker = pos.symbol
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(pos)
        
        print(f"\nPositions by ticker:")
        for ticker, ticker_positions in by_ticker.items():
            print(f"\n{ticker}:")
            for pos in ticker_positions:
                print(f"  {pos.symbol} ({pos.asset_type}): Long={pos.long_quantity}, Short={pos.short_quantity}")
        
        # Test detection for each ticker
        print(f"\n--- DETECTION ANALYSIS ---")
        for ticker, ticker_positions in by_ticker.items():
            print(f"\nAnalyzing {ticker}:")
            try:
                result = analyze_ticker_positions(ticker, ticker_positions)
                print(f"  Detection result: {result}")
            except Exception as e:
                print(f"  Error analyzing {ticker}: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_detection()
