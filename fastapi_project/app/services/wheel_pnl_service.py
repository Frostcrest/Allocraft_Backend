"""
Wheel P&L Calculation Service
Provides real-time P&L calculations for wheel strategies using current option market values
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
from sqlalchemy.orm import Session
import json
import logging

from ..models import WheelCycle
from ..services.price_service import fetch_option_contract_price
from ..utils.option_parser import parse_option_symbol

logger = logging.getLogger(__name__)


class WheelPnLCalculator:
    """
    Calculate real-time P&L for wheel strategies using current option market values.
    
    Handles:
    - Cash-secured put strategies
    - Covered call strategies  
    - Real-time option pricing via yfinance
    - Unrealized P&L calculation: Premium Collected - Current Option Value
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.update_timestamp = datetime.now(UTC)
    
    def calculate_wheel_pnl(self, cycle: WheelCycle) -> Dict[str, Any]:
        """
        Calculate real-time P&L for a single wheel cycle.
        
        Args:
            cycle: WheelCycle object containing strategy metadata
            
        Returns:
            Dict containing P&L calculation results
        """
        try:
            # Parse detection metadata to get option details
            metadata = json.loads(cycle.detection_metadata) if cycle.detection_metadata else {}
            
            # Extract option parameters
            strike_price = metadata.get('strike_price')
            expiration_date = metadata.get('expiration_date')
            contract_count = metadata.get('contract_count', 1)
            premium_per_share = metadata.get('premium', 0)
            
            if not all([strike_price, expiration_date, premium_per_share]):
                logger.warning(f"Missing option parameters for wheel cycle {cycle.id}")
                return self._get_fallback_pnl(cycle, metadata)
            
            # Calculate premium collected (what we received when selling the option)
            premium_collected = premium_per_share * 100 * contract_count
            
            # Determine option type based on strategy
            option_type = 'Put' if cycle.strategy_type == 'cash_secured_put' else 'Call'
            
            # Fetch current option market value
            current_option_price = fetch_option_contract_price(
                ticker=cycle.ticker,
                expiry_date=expiration_date,
                option_type=option_type,
                strike_price=float(strike_price)
            )
            
            if current_option_price is None:
                logger.warning(f"Could not fetch current option price for {cycle.ticker}")
                return self._get_fallback_pnl(cycle, metadata)
            
            # Calculate current option value (what it would cost to buy back)
            current_option_value = current_option_price * 100 * contract_count
            
            # Calculate unrealized P&L
            # For short options: P&L = Premium Collected - Current Option Value
            # Positive = profit (option lost value), Negative = loss (option gained value)
            unrealized_pnl = premium_collected - current_option_value
            
            # Total P&L (for now, same as unrealized since we don't track realized events yet)
            total_pnl = unrealized_pnl
            
            logger.info(f"Calculated P&L for {cycle.ticker}: Premium=${premium_collected:.2f}, "
                       f"Current Value=${current_option_value:.2f}, P&L=${total_pnl:.2f}")
            
            return {
                'success': True,
                'premium_collected': premium_collected,
                'current_option_value': current_option_value,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_pnl,
                'current_option_price': current_option_price,
                'calculation_timestamp': self.update_timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating P&L for wheel cycle {cycle.id}: {e}")
            return self._get_fallback_pnl(cycle, metadata)
    
    def _get_fallback_pnl(self, cycle: WheelCycle, metadata: Dict) -> Dict[str, Any]:
        """
        Return fallback P&L calculation using only premium collected.
        """
        premium_per_share = metadata.get('premium', 0)
        contract_count = metadata.get('contract_count', 1)
        premium_collected = premium_per_share * 100 * contract_count
        
        return {
            'success': False,
            'premium_collected': premium_collected,
            'current_option_value': 0,
            'unrealized_pnl': premium_collected,  # Assume all premium is profit
            'total_pnl': premium_collected,
            'current_option_price': None,
            'calculation_timestamp': self.update_timestamp.isoformat(),
            'error': 'Could not fetch real-time option price'
        }
    
    def update_wheel_cycle_pnl(self, cycle: WheelCycle) -> bool:
        """
        Update a wheel cycle with calculated P&L values.
        
        Args:
            cycle: WheelCycle object to update
            
        Returns:
            bool indicating success
        """
        try:
            pnl_result = self.calculate_wheel_pnl(cycle)
            
            # Update cycle with calculated values
            cycle.current_option_value = pnl_result.get('current_option_value')
            cycle.unrealized_pnl = pnl_result.get('unrealized_pnl')
            cycle.total_pnl = pnl_result.get('total_pnl')
            cycle.price_last_updated = self.update_timestamp
            
            return pnl_result.get('success', False)
            
        except Exception as e:
            logger.error(f"Error updating wheel cycle P&L: {e}")
            return False
    
    def refresh_all_wheel_pnl(self) -> Dict[str, Any]:
        """
        Refresh P&L for all active wheel cycles.
        
        Returns:
            Summary of refresh results
        """
        try:
            # Get all active wheel cycles
            active_cycles = self.db.query(WheelCycle).filter(
                WheelCycle.status == "Open"
            ).all()
            
            if not active_cycles:
                return {
                    'success': True,
                    'message': 'No active wheel cycles found',
                    'summary': {'total_cycles': 0, 'updated': 0, 'failed': 0}
                }
            
            updated_count = 0
            failed_count = 0
            failed_cycles = []
            
            # Process each cycle
            for cycle in active_cycles:
                success = self.update_wheel_cycle_pnl(cycle)
                if success:
                    updated_count += 1
                else:
                    failed_count += 1
                    failed_cycles.append(f"{cycle.ticker} (ID: {cycle.id})")
            
            # Commit all updates
            self.db.commit()
            
            logger.info(f"Wheel P&L refresh completed: {updated_count} updated, {failed_count} failed")
            
            return {
                'success': True,
                'message': f"Updated {updated_count} of {len(active_cycles)} wheel cycles",
                'summary': {
                    'total_cycles': len(active_cycles),
                    'updated': updated_count,
                    'failed': failed_count,
                    'failed_cycles': failed_cycles[:5]  # Limit to first 5 for brevity
                },
                'refresh_timestamp': self.update_timestamp.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during wheel P&L refresh: {e}")
            return {
                'success': False,
                'message': f"Wheel P&L refresh failed: {str(e)}",
                'summary': {}
            }


def calculate_wheel_pnl_quick(
    ticker: str,
    premium_collected: float,
    strike_price: float,
    expiration_date: str,
    option_type: str = 'Put',
    contract_count: int = 1
) -> Dict[str, Any]:
    """
    Quick wheel P&L calculation without database dependency.
    Useful for API endpoints and testing.
    
    Args:
        ticker: Underlying stock symbol
        premium_collected: Total premium collected from selling option
        strike_price: Strike price of the option
        expiration_date: Option expiration date (YYYY-MM-DD)
        option_type: 'Put' or 'Call'
        contract_count: Number of contracts
        
    Returns:
        P&L calculation results
    """
    try:
        # Fetch current option price
        current_option_price = fetch_option_contract_price(
            ticker=ticker,
            expiry_date=expiration_date,
            option_type=option_type,
            strike_price=strike_price
        )
        
        if current_option_price is None:
            return {
                'success': False,
                'error': f'Could not fetch current option price for {ticker}',
                'premium_collected': premium_collected,
                'total_pnl': premium_collected  # Fallback to premium collected
            }
        
        # Calculate current option value
        current_option_value = current_option_price * 100 * contract_count
        
        # Calculate P&L
        unrealized_pnl = premium_collected - current_option_value
        
        return {
            'success': True,
            'ticker': ticker,
            'premium_collected': premium_collected,
            'current_option_price': current_option_price,
            'current_option_value': current_option_value,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': unrealized_pnl,
            'calculation_timestamp': datetime.now(UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in quick wheel P&L calculation: {e}")
        return {
            'success': False,
            'error': str(e),
            'premium_collected': premium_collected,
            'total_pnl': premium_collected
        }
