"""
Profit & Loss Calculation Service for Options Trading

This service provides comprehensive P&L calculations for option positions,
handling both long and short positions with strategy-specific logic.
"""

from typing import Dict, Optional, List, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class OptionPnLCalculator:
    """
    Advanced P&L calculator for option positions with strategy support.
    
    Handles:
    - Long/Short option positions
    - Strategy-specific calculations (PMCC, Covered Calls, Wheels)
    - Real-time market value updates
    - Risk-adjusted calculations
    """
    
    @staticmethod
    def calculate_basic_pnl(
        position_type: str,
        contracts: float,
        average_price: float,
        current_price: float,
        multiplier: int = 100
    ) -> Dict[str, float]:
        """
        Calculate basic P&L for option positions.
        
        Args:
            position_type: 'long' or 'short'
            contracts: Number of contracts (positive for long, negative for short)
            average_price: Average entry price per contract
            current_price: Current market price per contract
            multiplier: Contract multiplier (typically 100 for equity options)
            
        Returns:
            Dict containing profit_loss, profit_loss_percent, market_value, cost_basis
            
        Example:
            >>> calc = OptionPnLCalculator()
            >>> result = calc.calculate_basic_pnl('long', 2, 5.50, 7.25)
            >>> print(result['profit_loss'])  # 350.0
        """
        try:
            abs_contracts = abs(contracts)
            
            # Calculate cost basis and market value
            cost_basis = average_price * abs_contracts * multiplier
            market_value = current_price * abs_contracts * multiplier
            
            # Calculate P&L based on position type
            if contracts > 0:  # Long position
                # Long: profit when current > average
                profit_loss = market_value - cost_basis
            else:  # Short position
                # Short: profit when current < average (we sold high, buying back low)
                profit_loss = cost_basis - market_value
            
            # Calculate percentage
            profit_loss_percent = (profit_loss / cost_basis * 100) if cost_basis > 0 else 0
            
            return {
                "profit_loss": round(profit_loss, 2),
                "profit_loss_percent": round(profit_loss_percent, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "daily_change": 0.0  # Placeholder for daily change calculation
            }
            
        except Exception as e:
            logger.error(f"Error calculating basic P&L: {e}")
            return {
                "profit_loss": 0.0,
                "profit_loss_percent": 0.0,
                "market_value": 0.0,
                "cost_basis": 0.0,
                "daily_change": 0.0
            }
    
    @staticmethod
    def calculate_strategy_pnl(
        option_data: Dict[str, Any],
        strategy_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate P&L with strategy-specific considerations.
        
        Args:
            option_data: Position data including symbol, contracts, prices, etc.
            strategy_type: 'wheel', 'covered_call', 'pmcc', 'naked', etc.
            
        Returns:
            Enhanced P&L data with strategy insights
        """
        try:
            # Get basic P&L calculation
            contracts = option_data.get('contracts', 0)
            average_price = option_data.get('average_price', 0)
            current_price = option_data.get('current_price', 0)
            option_type = option_data.get('option_type', '').upper()
            
            basic_pnl = OptionPnLCalculator.calculate_basic_pnl(
                'long' if contracts > 0 else 'short',
                contracts,
                average_price,
                current_price
            )
            
            # Add strategy-specific enhancements
            strategy_insights = OptionPnLCalculator._get_strategy_insights(
                option_data, strategy_type, basic_pnl
            )
            
            return {
                **basic_pnl,
                **strategy_insights,
                "calculation_timestamp": datetime.now().isoformat(),
                "strategy_type": strategy_type or "unknown"
            }
            
        except Exception as e:
            logger.error(f"Error calculating strategy P&L: {e}")
            return OptionPnLCalculator.calculate_basic_pnl('long', 0, 0, 0)
    
    @staticmethod
    def _get_strategy_insights(
        option_data: Dict[str, Any],
        strategy_type: Optional[str],
        basic_pnl: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Add strategy-specific insights to P&L calculation.
        """
        insights = {
            "risk_level": "medium",
            "time_decay_impact": "neutral",
            "breakeven_price": 0.0,
            "max_profit": None,
            "max_loss": None
        }
        
        contracts = option_data.get('contracts', 0)
        strike_price = option_data.get('strike_price', 0)
        average_price = option_data.get('average_price', 0)
        option_type = option_data.get('option_type', '').upper()
        
        if strategy_type == 'wheel' and option_type == 'PUT' and contracts < 0:
            # Cash-secured put (wheel start)
            insights.update({
                "risk_level": "low",
                "time_decay_impact": "positive",
                "breakeven_price": strike_price - average_price,
                "max_profit": average_price * abs(contracts) * 100,
                "strategy_notes": "Cash-secured put - profit from premium, assignment at strike"
            })
        
        elif strategy_type == 'covered_call' and option_type == 'CALL' and contracts < 0:
            # Covered call
            insights.update({
                "risk_level": "low",
                "time_decay_impact": "positive",
                "breakeven_price": strike_price + average_price,
                "max_profit": average_price * abs(contracts) * 100,
                "strategy_notes": "Covered call - income strategy with upside cap"
            })
        
        elif strategy_type == 'pmcc':
            # Poor Man's Covered Call
            insights.update({
                "risk_level": "medium",
                "time_decay_impact": "neutral",
                "strategy_notes": "PMCC - synthetic covered call using long call"
            })
        
        return insights
    
    @staticmethod
    def calculate_portfolio_pnl(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate aggregate P&L for a portfolio of option positions.
        
        Args:
            positions: List of option position dictionaries
            
        Returns:
            Portfolio-level P&L metrics
        """
        try:
            total_pnl = 0.0
            total_cost_basis = 0.0
            total_market_value = 0.0
            position_count = len(positions)
            
            winning_positions = 0
            losing_positions = 0
            
            strategy_breakdown = {}
            
            for position in positions:
                # Calculate individual position P&L
                pnl_result = OptionPnLCalculator.calculate_strategy_pnl(position)
                
                total_pnl += pnl_result['profit_loss']
                total_cost_basis += pnl_result['cost_basis']
                total_market_value += pnl_result['market_value']
                
                # Track winning/losing positions
                if pnl_result['profit_loss'] > 0:
                    winning_positions += 1
                elif pnl_result['profit_loss'] < 0:
                    losing_positions += 1
                
                # Track by strategy
                strategy = pnl_result.get('strategy_type', 'unknown')
                if strategy not in strategy_breakdown:
                    strategy_breakdown[strategy] = {
                        'count': 0,
                        'total_pnl': 0.0,
                        'total_value': 0.0
                    }
                
                strategy_breakdown[strategy]['count'] += 1
                strategy_breakdown[strategy]['total_pnl'] += pnl_result['profit_loss']
                strategy_breakdown[strategy]['total_value'] += pnl_result['market_value']
            
            # Calculate portfolio metrics
            portfolio_pnl_percent = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0
            win_rate = (winning_positions / position_count * 100) if position_count > 0 else 0
            
            return {
                "total_profit_loss": round(total_pnl, 2),
                "total_profit_loss_percent": round(portfolio_pnl_percent, 2),
                "total_market_value": round(total_market_value, 2),
                "total_cost_basis": round(total_cost_basis, 2),
                "position_count": position_count,
                "winning_positions": winning_positions,
                "losing_positions": losing_positions,
                "win_rate_percent": round(win_rate, 2),
                "strategy_breakdown": strategy_breakdown,
                "calculation_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio P&L: {e}")
            return {
                "total_profit_loss": 0.0,
                "total_profit_loss_percent": 0.0,
                "total_market_value": 0.0,
                "total_cost_basis": 0.0,
                "position_count": 0,
                "winning_positions": 0,
                "losing_positions": 0,
                "win_rate_percent": 0.0,
                "strategy_breakdown": {},
                "calculation_timestamp": datetime.now().isoformat()
            }


def calculate_option_pnl(
    contracts: float,
    average_price: float,
    current_price: float,
    option_type: str = 'CALL',
    strategy_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for quick option P&L calculation.
    
    Args:
        contracts: Number of contracts (positive=long, negative=short)
        average_price: Entry price per contract
        current_price: Current market price per contract
        option_type: 'CALL' or 'PUT'
        strategy_type: Optional strategy classification
        
    Returns:
        P&L calculation results
        
    Example:
        >>> result = calculate_option_pnl(-2, 3.50, 1.25, 'PUT', 'wheel')
        >>> print(f"P&L: ${result['profit_loss']}")
    """
    position_data = {
        'contracts': contracts,
        'average_price': average_price,
        'current_price': current_price,
        'option_type': option_type,
        'strike_price': 0,  # Would need real data for strategy calculations
    }
    
    return OptionPnLCalculator.calculate_strategy_pnl(position_data, strategy_type)
