"""
Debug wheel detection by adding logging to see what's happening
"""
import sys
sys.path.append('/app')

from sqlalchemy import create_engine, text
from app.database import SessionLocal
from app.models import Position

# Create session
db = SessionLocal()

try:
    # Get positions like the API does
    positions = db.query(Position).filter(Position.is_active == True).filter(Position.account_id == 1).all()
    
    print(f"Found {len(positions)} positions for account_id=1")
    
    # Group by ticker like the detection does
    by_ticker = {}
    for pos in positions:
        ticker = pos.underlying_symbol or pos.symbol
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(pos)
    
    print(f"Grouped into {len(by_ticker)} tickers:")
    
    for ticker, ticker_positions in by_ticker.items():
        print(f"\n{ticker}:")
        
        stock_positions = [p for p in ticker_positions if p.asset_type != "OPTION"]
        option_positions = [p for p in ticker_positions if p.asset_type == "OPTION"]
        
        total_stock_shares = sum(p.long_quantity - p.short_quantity for p in stock_positions)
        
        short_puts = []
        short_calls = []
        
        for pos in option_positions:
            contracts = pos.long_quantity - pos.short_quantity
            print(f"  {pos.symbol}: {pos.option_type} contracts={contracts} (long={pos.long_quantity}, short={pos.short_quantity})")
            
            if pos.option_type == 'Put' and contracts < 0:
                short_puts.append(pos)
            elif pos.option_type == 'Call' and contracts < 0:
                short_calls.append(pos)
        
        print(f"  Stock shares: {total_stock_shares}")
        print(f"  Short puts: {len(short_puts)}")
        print(f"  Short calls: {len(short_calls)}")
        
        # Detection logic
        if total_stock_shares >= 100 and len(short_calls) > 0 and len(short_puts) > 0:
            print(f"  -> FULL WHEEL detected!")
        elif total_stock_shares >= 100 and len(short_calls) > 0:
            print(f"  -> COVERED CALL detected!")
        elif len(short_puts) > 0:
            print(f"  -> CASH SECURED PUT detected!")
        elif total_stock_shares > 0 and len(option_positions) == 0:
            if total_stock_shares >= 100:
                print(f"  -> NAKED STOCK detected!")
        else:
            print(f"  -> No strategy detected")

finally:
    db.close()
