"""
Mock Data Service for Development

Provides realistic mock data that matches the exact structure of Schwab API responses.
This allows for local development without requiring HTTPS/production Schwab connection.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

class MockDataService:
    """Service to generate mock Schwab API responses for development"""
    
    @staticmethod
    def generate_mock_accounts_with_positions() -> List[Dict[str, Any]]:
        """Generate mock accounts with positions matching Schwab API structure"""
        
        # Generate a few different account types
        accounts = [
            {
                "accountNumber": "123456789",
                "accountType": "Individual",
                "lastSynced": datetime.utcnow().isoformat(),
                "totalValue": 125678.45,
                "positions": MockDataService._generate_mock_positions("123456789")
            },
            {
                "accountNumber": "987654321", 
                "accountType": "IRA",
                "lastSynced": datetime.utcnow().isoformat(),
                "totalValue": 89234.12,
                "positions": MockDataService._generate_mock_positions("987654321")
            }
        ]
        
        return accounts
    
    @staticmethod
    def _generate_mock_positions(account_number: str) -> List[Dict[str, Any]]:
        """Generate realistic positions for an account"""
        positions = []
        
        # Generate stock positions suitable for wheel strategies
        stock_positions = [
            {
                "symbol": "AAPL",
                "quantity": 300,
                "marketValue": 54600.00,
                "averagePrice": 175.50,
                "profitLoss": 2400.00,
                "profitLossPercentage": 4.59,
                "assetType": "EQUITY",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": False,
                "shares": 300,
                "isShort": False
            },
            {
                "symbol": "TSLA", 
                "quantity": 100,
                "marketValue": 24500.00,
                "averagePrice": 225.00,
                "profitLoss": 2000.00,
                "profitLossPercentage": 8.89,
                "assetType": "EQUITY",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": False,
                "shares": 100,
                "isShort": False
            },
            {
                "symbol": "NVDA",
                "quantity": 200,
                "marketValue": 92000.00,
                "averagePrice": 440.00,
                "profitLoss": 4000.00,
                "profitLossPercentage": 4.55,
                "assetType": "EQUITY", 
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": False,
                "shares": 200,
                "isShort": False
            },
            {
                "symbol": "SPY",
                "quantity": 150,
                "marketValue": 67500.00,
                "averagePrice": 430.00,
                "profitLoss": 3000.00,
                "profitLossPercentage": 4.65,
                "assetType": "EQUITY",
                "lastUpdated": datetime.utcnow().isoformat(), 
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": False,
                "shares": 150,
                "isShort": False
            }
        ]
        
        # Generate option positions (both long and short for wheel strategies)
        option_positions = [
            # Short put (cash-secured put for wheel)
            {
                "symbol": "AAPL 250117P00170000",
                "quantity": 3,
                "marketValue": -900.00,
                "averagePrice": 3.50,
                "profitLoss": -150.00,
                "profitLossPercentage": -5.00,
                "assetType": "OPTION",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": True,
                "underlyingSymbol": "AAPL",
                "optionType": "Put",
                "strikePrice": 170.00,
                "expirationDate": (datetime.utcnow() + timedelta(days=45)).isoformat(),
                "contracts": 3,
                "isShort": True
            },
            # Short call (covered call for wheel)
            {
                "symbol": "TSLA 250117C00250000",
                "quantity": 1,
                "marketValue": -450.00,
                "averagePrice": 5.25,
                "profitLoss": 75.00,
                "profitLossPercentage": 20.00,
                "assetType": "OPTION",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": True,
                "underlyingSymbol": "TSLA",
                "optionType": "Call",
                "strikePrice": 250.00,
                "expirationDate": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "contracts": 1,
                "isShort": True
            },
            # Long put (protective put)
            {
                "symbol": "NVDA 241220P00420000",
                "quantity": 2,
                "marketValue": 1200.00,
                "averagePrice": 8.50,
                "profitLoss": -500.00,
                "profitLossPercentage": -20.83,
                "assetType": "OPTION",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": True,
                "underlyingSymbol": "NVDA",
                "optionType": "Put",
                "strikePrice": 420.00,
                "expirationDate": (datetime.utcnow() + timedelta(days=15)).isoformat(),
                "contracts": 2,
                "isShort": False
            },
            # Short put spread
            {
                "symbol": "SPY 241215P00425000",
                "quantity": 2,
                "marketValue": -600.00,
                "averagePrice": 4.25,
                "profitLoss": 250.00,
                "profitLossPercentage": 41.67,
                "assetType": "OPTION",
                "lastUpdated": datetime.utcnow().isoformat(),
                "accountNumber": account_number,
                "source": "schwab",
                "isOption": True,
                "underlyingSymbol": "SPY",
                "optionType": "Put",
                "strikePrice": 425.00,
                "expirationDate": (datetime.utcnow() + timedelta(days=10)).isoformat(),
                "contracts": 2,
                "isShort": True
            }
        ]
        
        return stock_positions + option_positions
    
    @staticmethod
    def generate_mock_sync_response() -> Dict[str, Any]:
        """Generate mock sync response"""
        return {
            "message": "Mock synchronization completed successfully",
            "result": {
                "status": "success",
                "force": False,
                "accounts_synced": 2,
                "positions_total": 12,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    @staticmethod
    def generate_mock_sync_status() -> Dict[str, Any]:
        """Generate mock sync status"""
        return {
            "last_sync": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            "accounts_count": 2,
            "positions_count": 12,
            "next_sync_recommended": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
