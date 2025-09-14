"""
Option Symbol Parser Utility

Parses standard option symbols like "HIMS  251017P00037000" into readable components:
- Ticker: HIMS
- Expiry: 2025-10-17  
- Type: Put
- Strike: $37.00
"""

def parse_option_symbol(symbol):
    """
    Parse option symbol into components
    
    Format: "TICKER  YYMMDDX########"
    Example: "HIMS  251017P00037000" → HIMS 2025-10-17 Put $37.00
    
    Returns dict with ticker, expiry_date, option_type, strike_price
    """
    try:
        # Split ticker from option code
        parts = symbol.strip().split()
        if len(parts) < 2:
            return None
            
        ticker = parts[0]
        option_code = parts[1]
        
        # Validate minimum length (YYMMDDX######## = 15 chars)
        if len(option_code) < 15:
            return None
        
        # Extract date components
        year_code = option_code[0:2]    # "25" → 2025
        month = option_code[2:4]        # "10" → October  
        day = option_code[4:6]          # "17" → 17th
        option_type_code = option_code[6]  # "P" → Put
        strike_code = option_code[7:15]    # "00037000" → 37000
        
        # Convert year (handle 2000s properly)
        year = 2000 + int(year_code)
        
        # Format expiry date
        expiry_date = f"{year}-{month}-{day}"
        
        # Convert option type
        option_type = "Put" if option_type_code == "P" else "Call"
        
        # Convert strike price (from thousandths to dollars)
        strike_price = int(strike_code) / 1000.0
        
        return {
            "ticker": ticker,
            "expiry_date": expiry_date,
            "option_type": option_type,
            "strike_price": strike_price
        }
        
    except (ValueError, IndexError) as e:
        # Return None for unparseable symbols
        return None

def test_parser():
    pass
