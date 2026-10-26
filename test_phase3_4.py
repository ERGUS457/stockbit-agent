"""
Test Suite untuk Fase 3 (Virtual Portfolio Execution) dan Fase 4 (S/R Detection & Telegram Alert)
"""

import unittest
import os
import shutil
import pandas as pd
import numpy as np
from datetime import datetime

from sr_detector import SRDetector, SREvent
from portfolio import VirtualPortfolio
from notifier import TelegramNotifier
from config import INITIAL_CAPITAL

TEST_PORTFOLIO_FILE = "F:/hermes/stockbit-agent/test_portfolio_temp.json"

class TestPhase3And4(unittest.TestCase):

    def setUp(self):
        # Buat dummy DataFrame OHLCV
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        base = 3000.0
        data = []
        for i in range(60):
            p = base + np.sin(i / 5.0) * 200.0 + (i * 5)
            data.append({
                "Date": dates[i],
                "Open": p - 10,
                "High": p + 30,
                "Low": p - 30,
                "Close": p + 10,
                "Volume": 1000000 + (i * 10000)
            })
        self.df = pd.DataFrame(data).set_index("Date")
        self.df["VOL_RATIO"] = 1.0
        self.df["RSI14"] = 50.0

    def tearDown(self):
        if os.path.exists(TEST_PORTFOLIO_FILE):
            os.remove(TEST_PORTFOLIO_FILE)

    def test_01_sr_detector_levels(self):
        detector = SRDetector()
        levels = detector.calculate_levels(self.df)
        
        self.assertIn("pivot", levels)
        self.assertIn("s1", levels)
        self.assertIn("r1", levels)
        self.assertIn("swing_high", levels)
        self.assertIn("swing_low", levels)
        
        # S1 harus lebih rendah dari R1
        self.assertLess(levels["s1"], levels["r1"])
        self.assertGreater(levels["r1"], levels["pivot"])

    def test_02_sr_detector_events(self):
        detector = SRDetector()
        
        # Test default in range
        event = detector.detect_event(self.df, "TEST.JK")
        self.assertIsInstance(event, SREvent)
        self.assertEqual(event.ticker, "TEST.JK")

        # Test Breakout
        breakout_df = self.df.copy()
        high_res = detector.calculate_levels(breakout_df)["swing_high"]
        breakout_df.iloc[-1, breakout_df.columns.get_loc("Close")] = high_res + 100
        breakout_df.iloc[-1, breakout_df.columns.get_loc("Open")] = high_res + 10
        breakout_df.iloc[-1, breakout_df.columns.get_loc("VOL_RATIO")] = 2.0
        
        bo_event = detector.detect_event(breakout_df, "TEST.JK")
        self.assertEqual(bo_event.event_type, "RESISTANCE_BREAKOUT")
        self.assertEqual(bo_event.severity, "BULLISH_SIGNAL")

    def test_03_virtual_portfolio_buy_and_sell(self):
        portfolio = VirtualPortfolio(filepath=TEST_PORTFOLIO_FILE)
        
        # 1. Test Buy Order
        pos = portfolio.execute_buy(
            ticker="BBCA.JK",
            price=10000.0,
            stop_loss=9500.0,
            take_profit=11000.0,
            reason="Uji Coba Buy Setup"
        )
        self.assertIsNotNone(pos)
        self.assertEqual(pos["ticker"], "BBCA.JK")
        self.assertGreater(pos["lots"], 0)
        self.assertLess(portfolio.data["cash_balance"], INITIAL_CAPITAL)
        
        # 2. Test Duplicate Buy Prevention
        pos_dup = portfolio.execute_buy(
            ticker="BBCA.JK",
            price=10000.0,
            stop_loss=9500.0,
            take_profit=11000.0,
            reason="Uji Coba Duplikat"
        )
        self.assertIsNone(pos_dup)

        # 3. Test Update Prices
        portfolio.update_prices({"BBCA.JK": 10500.0})
        summary = portfolio.get_summary()
        self.assertGreater(summary["floating_pnl_rp"], 0)

        # 4. Test Sell Order (Take Profit hit)
        closed = portfolio.execute_sell(
            ticker="BBCA.JK",
            price=11000.0,
            reason="Take profit tercapai"
        )
        self.assertIsNotNone(closed)
        self.assertGreater(closed["pnl_rp"], 0)
        self.assertEqual(len(portfolio.data["open_positions"]), 0)
        self.assertEqual(len(portfolio.data["closed_trades"]), 1)

    def test_04_telegram_notifier_formatting_and_cooldown(self):
        notifier = TelegramNotifier()
        self.assertTrue(notifier.is_available())
        
        event = SREvent(
            ticker="BBRI.JK",
            event_type="SUPPORT_BOUNCE",
            current_price=4800.0,
            support_level=4750.0,
            resistance_level=5000.0,
            pivot_point=4850.0,
            volume_ratio=1.45,
            rsi=44.2,
            description="Rebound mantul dari support kuat.",
            severity="BULLISH_SIGNAL",
            action_hint="BUY"
        )
        
        # Cek caching cooldown
        key = "BBRI.JK_SUPPORT_BOUNCE"
        notifier._sent_alerts_cache[key] = 99999999999  # Mock masa cooldown masih jauh di masa depan
        sent = notifier.send_sr_alert(event)
        self.assertFalse(sent)  # Wajib dicegah oleh cooldown

if __name__ == "__main__":
    unittest.main()
