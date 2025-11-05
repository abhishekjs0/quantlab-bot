"""Tests for T+1 Cash Management system."""

import pandas as pd
import pytest

from core.cash_management import T1CashManager


class TestT1CashManager:
    """Test T+1 settlement and cash management."""

    def test_initialization(self):
        """Test cash manager initialization."""
        mgr = T1CashManager(initial_capital=100000.0)
        assert mgr.available_cash == 100000.0
        assert mgr.blocked_cash == 0.0
        assert mgr.get_total_capital() == 100000.0
        assert len(mgr.settlement_queue) == 0

    def test_entry_deducts_cash(self):
        """Test that entry deducts from available cash."""
        mgr = T1CashManager(initial_capital=100000.0)
        entry_cost = 500 * 100 + 55  # 500 shares at 100 + commission
        mgr.record_entry(100.0, 500, 55.0)
        assert mgr.available_cash == 100000.0 - entry_cost
        assert mgr.blocked_cash == 0.0

    def test_entry_insufficient_cash(self):
        """Test that entry fails with insufficient cash."""
        mgr = T1CashManager(initial_capital=100000.0)
        # Try to buy 2000 shares at 100 each (200k cost > 100k available)
        with pytest.raises(ValueError, match="Insufficient cash"):
            mgr.record_entry(100.0, 2000, 220.0)

    def test_exit_blocks_cash(self):
        """Test that exit blocks cash until settlement."""
        mgr = T1CashManager(initial_capital=100000.0)

        # Entry
        mgr.record_entry(100.0, 500, 55.0)
        available_after_entry = mgr.available_cash

        # Exit
        exit_time = pd.Timestamp("2025-01-05")
        mgr.record_exit(exit_time, 110.0, 500, 55.0)

        # Cash should be blocked
        assert mgr.blocked_cash > 0
        assert mgr.available_cash == available_after_entry

        # Total should increase (profit from trade)
        assert mgr.get_total_capital() > 100000.0

    def test_settlement_release_cash(self):
        """Test that cash is released on settlement date."""
        mgr = T1CashManager(initial_capital=100000.0)

        # Entry and exit
        mgr.record_entry(100.0, 500, 55.0)
        exit_time = pd.Timestamp("2025-01-06")
        mgr.record_exit(exit_time, 110.0, 500, 55.0)

        blocked_before = mgr.blocked_cash
        assert blocked_before > 0

        # Process settlements on T+1
        settlement_time = exit_time + pd.Timedelta(days=1)
        settled = mgr.process_settlements(settlement_time)

        assert settled > 0
        assert mgr.blocked_cash == 0.0
        assert mgr.available_cash > 100000.0 - 55.0  # Account for commissions

    def test_multiple_exits_staggered_settlements(self):
        """Test multiple exits with staggered settlement dates."""
        mgr = T1CashManager(initial_capital=100000.0)

        # Entry
        mgr.record_entry(100.0, 500, 55.0)

        # Exit 1
        exit_time_1 = pd.Timestamp("2025-01-05")
        mgr.record_exit(exit_time_1, 105.0, 250, 26.0)
        blocked_1 = mgr.blocked_cash

        # Exit 2
        exit_time_2 = pd.Timestamp("2025-01-06")
        mgr.record_exit(exit_time_2, 108.0, 250, 27.0)
        blocked_2 = mgr.blocked_cash

        # Both exits blocked
        assert blocked_2 > blocked_1

        # Process first settlement
        settlement_1 = exit_time_1 + pd.Timedelta(days=1)
        settled_1 = mgr.process_settlements(settlement_1)
        assert settled_1 > 0
        assert mgr.blocked_cash < blocked_2

        # Second still blocked
        blocked_after_first = mgr.blocked_cash
        assert blocked_after_first > 0

        # Process second settlement
        settlement_2 = exit_time_2 + pd.Timedelta(days=1)
        settled_2 = mgr.process_settlements(settlement_2)
        assert settled_2 > 0
        assert mgr.blocked_cash == 0.0

    def test_settlement_status(self):
        """Test settlement status reporting."""
        mgr = T1CashManager(initial_capital=100000.0)
        mgr.record_entry(100.0, 500, 55.0)
        mgr.record_exit(pd.Timestamp("2025-01-05"), 105.0, 500, 55.0)

        status = mgr.get_settlement_status()
        assert status["available_cash"] == mgr.available_cash
        assert status["blocked_cash"] == mgr.blocked_cash
        assert status["pending_settlements"] == 1
        assert len(status["settlement_queue"]) == 1

    def test_cash_available_for_new_trades_after_settlement(self):
        """Test workflow: entry -> exit -> settlement -> new entry."""
        mgr = T1CashManager(initial_capital=100000.0)

        # Trade 1
        mgr.record_entry(100.0, 500, 55.0)
        exit_time = pd.Timestamp("2025-01-05")
        mgr.record_exit(exit_time, 110.0, 500, 55.0)

        # Try to enter before settlement (should fail if not enough unblocked cash)
        # This tests that blocked cash is truly unavailable
        cash_available_before = mgr.get_available_cash()
        initial_minus_entry = 100000.0 - (100.0 * 500 + 55.0)
        assert cash_available_before == initial_minus_entry

        # Process settlement
        settlement_time = exit_time + pd.Timedelta(days=1)
        mgr.process_settlements(settlement_time)

        # Now should have more cash available
        cash_available_after = mgr.get_available_cash()
        assert cash_available_after > cash_available_before

        # Should be able to enter new trade
        trade_cost = 150.0 * 300 + 49.5
        mgr.record_entry(150.0, 300, 49.5)
        assert mgr.available_cash == cash_available_after - trade_cost

    def test_reset(self):
        """Test reset functionality."""
        mgr = T1CashManager(initial_capital=100000.0)
        mgr.record_entry(100.0, 500, 55.0)
        mgr.record_exit(pd.Timestamp("2025-01-05"), 105.0, 500, 55.0)

        assert mgr.blocked_cash > 0

        mgr.reset()
        assert mgr.available_cash == 100000.0
        assert mgr.blocked_cash == 0.0
        assert len(mgr.settlement_queue) == 0

    def test_no_settlement_before_t_plus_1(self):
        """Test that settlement doesn't happen before T+1."""
        mgr = T1CashManager(initial_capital=100000.0)
        exit_time = pd.Timestamp("2025-01-05")
        mgr.record_entry(100.0, 500, 55.0)
        mgr.record_exit(exit_time, 105.0, 500, 55.0)

        # Check settlement before T+1
        current_time_day_0 = exit_time
        settled = mgr.process_settlements(current_time_day_0)
        assert settled == 0.0
        assert mgr.blocked_cash > 0

        # Check settlement on T+1
        current_time_t_plus_1 = exit_time + pd.Timedelta(days=1)
        settled = mgr.process_settlements(current_time_t_plus_1)
        assert settled > 0
        assert mgr.blocked_cash == 0.0
