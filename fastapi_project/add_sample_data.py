from app.database import get_db
from app.models import Stock, User
from sqlalchemy.orm import Session

# Get database session
db = next(get_db())

print('Adding sample stock positions...')

# Add sample stock positions (without user linking for now)
sample_stocks = [
    {'ticker': 'AAPL', 'shares': 200, 'cost_basis': 150.00},
    {'ticker': 'TSLA', 'shares': 150, 'cost_basis': 225.00},
    {'ticker': 'MSFT', 'shares': 300, 'cost_basis': 380.00},
    {'ticker': 'NVDA', 'shares': 100, 'cost_basis': 450.00},
]

for stock_data in sample_stocks:
    # Check if stock already exists
    existing = db.query(Stock).filter(
        Stock.ticker == stock_data['ticker']
    ).first()
    
    if not existing:
        stock = Stock(
            ticker=stock_data['ticker'],
            shares=stock_data['shares'],
            cost_basis=stock_data['cost_basis']
        )
        db.add(stock)
        print(f'Added {stock_data["ticker"]}: {stock_data["shares"]} shares')
    else:
        print(f'{stock_data["ticker"]} already exists')

db.commit()
print('Sample data added successfully')
