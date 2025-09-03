"""
Unit tests for P&L calculation service
"""

import pytest
from app.services.pnl_service import OptionPnLCalculator, calculate_option_pnl


class TestOptionPnLCalculator:
    """Test the OptionPnLCalculator class methods."""
    
    def test_calculate_basic_pnl_long_position_profit(self):
        """Test P&L calculation for profitable long option position."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='long',
            contracts=2,
            average_price=5.50,
            current_price=7.25
        )
        
        # Long: bought at $5.50, current $7.25, profit = (7.25 - 5.50) * 2 * 100 = $350
        assert result['profit_loss'] == 350.0
        assert result['profit_loss_percent'] == 31.82  # 350/1100 * 100
        assert result['market_value'] == 1450.0  # 7.25 * 2 * 100
        assert result['cost_basis'] == 1100.0  # 5.50 * 2 * 100
    
    def test_calculate_basic_pnl_long_position_loss(self):
        """Test P&L calculation for losing long option position."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='long',
            contracts=1,
            average_price=8.00,
            current_price=3.50
        )
        
        # Long: bought at $8.00, current $3.50, loss = (3.50 - 8.00) * 1 * 100 = -$450
        assert result['profit_loss'] == -450.0
        assert result['profit_loss_percent'] == -56.25  # -450/800 * 100
        assert result['market_value'] == 350.0
        assert result['cost_basis'] == 800.0
    
    def test_calculate_basic_pnl_short_position_profit(self):
        """Test P&L calculation for profitable short option position."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='short',
            contracts=-1,  # Negative indicates short
            average_price=4.00,
            current_price=1.50
        )
        
        # Short: sold at $4.00, current $1.50, profit = (4.00 - 1.50) * 1 * 100 = $250
        assert result['profit_loss'] == 250.0
        assert result['profit_loss_percent'] == 62.5  # 250/400 * 100
        assert result['market_value'] == 150.0
        assert result['cost_basis'] == 400.0
    
    def test_calculate_basic_pnl_short_position_loss(self):
        """Test P&L calculation for losing short option position."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='short',
            contracts=-2,
            average_price=2.00,
            current_price=5.50
        )
        
        # Short: sold at $2.00, current $5.50, loss = (2.00 - 5.50) * 2 * 100 = -$700
        assert result['profit_loss'] == -700.0
        assert result['profit_loss_percent'] == -175.0  # -700/400 * 100
        assert result['market_value'] == 1100.0
        assert result['cost_basis'] == 400.0
    
    def test_calculate_strategy_pnl_wheel_put(self):
        """Test strategy-specific P&L for wheel (cash-secured put)."""
        option_data = {
            'contracts': -1,  # Short put
            'average_price': 3.50,
            'current_price': 1.25,
            'option_type': 'PUT',
            'strike_price': 150.0
        }
        
        result = OptionPnLCalculator.calculate_strategy_pnl(option_data, 'wheel')
        
        assert result['profit_loss'] == 225.0  # (3.50 - 1.25) * 100
        assert result['strategy_type'] == 'wheel'
        assert result['risk_level'] == 'low'
        assert result['breakeven_price'] == 146.5  # 150 - 3.50
        assert result['max_profit'] == 350.0  # 3.50 * 100
    
    def test_calculate_strategy_pnl_covered_call(self):
        """Test strategy-specific P&L for covered call."""
        option_data = {
            'contracts': -2,  # Short call
            'average_price': 2.75,
            'current_price': 0.50,
            'option_type': 'CALL',
            'strike_price': 160.0
        }
        
        result = OptionPnLCalculator.calculate_strategy_pnl(option_data, 'covered_call')
        
        assert result['profit_loss'] == 450.0  # (2.75 - 0.50) * 2 * 100
        assert result['strategy_type'] == 'covered_call'
        assert result['risk_level'] == 'low'
        assert result['breakeven_price'] == 162.75  # 160 + 2.75
        assert result['max_profit'] == 550.0  # 2.75 * 2 * 100
    
    def test_calculate_portfolio_pnl(self):
        """Test portfolio-level P&L calculation."""
        positions = [
            {
                'contracts': -1,
                'average_price': 3.50,
                'current_price': 1.25,
                'option_type': 'PUT',
                'strike_price': 150.0
            },
            {
                'contracts': 2,
                'average_price': 5.00,
                'current_price': 7.50,
                'option_type': 'CALL',
                'strike_price': 155.0
            }
        ]
        
        result = OptionPnLCalculator.calculate_portfolio_pnl(positions)
        
        # Position 1: (3.50 - 1.25) * 100 = 225 profit
        # Position 2: (7.50 - 5.00) * 2 * 100 = 500 profit
        # Total: 725 profit
        assert result['total_profit_loss'] == 725.0
        assert result['position_count'] == 2
        assert result['winning_positions'] == 2
        assert result['losing_positions'] == 0
        assert result['win_rate_percent'] == 100.0
    
    def test_convenience_function(self):
        """Test the convenience function calculate_option_pnl."""
        result = calculate_option_pnl(
            contracts=-1,
            average_price=4.00,
            current_price=2.50,
            option_type='PUT',
            strategy_type='wheel'
        )
        
        assert result['profit_loss'] == 150.0  # (4.00 - 2.50) * 100
        assert result['strategy_type'] == 'wheel'
    
    def test_zero_cost_basis_handling(self):
        """Test handling of zero cost basis edge case."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='long',
            contracts=1,
            average_price=0,
            current_price=2.00
        )
        
        assert result['profit_loss'] == 200.0
        assert result['profit_loss_percent'] == 0.0  # Should handle division by zero
        assert result['cost_basis'] == 0.0
    
    def test_negative_prices_handling(self):
        """Test handling of edge cases with invalid prices."""
        result = OptionPnLCalculator.calculate_basic_pnl(
            position_type='long',
            contracts=0,
            average_price=5.00,
            current_price=3.00
        )
        
        # Zero contracts should result in zero values
        assert result['profit_loss'] == 0.0
        assert result['market_value'] == 0.0
        assert result['cost_basis'] == 0.0


if __name__ == "__main__":
    # Run basic tests
    calculator = TestOptionPnLCalculator()
    calculator.test_calculate_basic_pnl_long_position_profit()
    calculator.test_calculate_basic_pnl_short_position_profit()
    calculator.test_calculate_strategy_pnl_wheel_put()
    calculator.test_convenience_function()
    print("✅ All P&L calculation tests passed!")
