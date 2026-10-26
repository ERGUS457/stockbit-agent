"""
Test Suite Komprehensif AI Trading Agent IDX (Fase 1 & Fase 2)
"""

import unittest
from datetime import datetime
import pandas as pd
import numpy as np

from config import (
    INITIAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    SHARES_PER_LOT,
    DEFAULT_WATCHLIST
)
from data_feed import IDXDataFeed
from indicators import (
    calculate_ema,
    calculate_sma,
    calculate_rsi,
    calculate_atr,
    calculate_macd,
    calculate_all_indicators
)
from strategy import StrategyEngine, TradeSignal
from risk_manager import RiskManager
from backtester import BacktestEngine, BacktestResult
from scanner import StockScanner

class TestIDXTradingAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Buat dummy DataFrame OHLCV sintetis untuk pengujian deterministik
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        
        # Buat tren naik dengan volatilitas
        trend = np.linspace(4000, 6000, n)
        noise = np.random.normal(0, 50, n)
        close = trend + noise
        open_p = close - np.random.normal(0, 30, n)
        high = np.maximum(open_p, close) + np.random.exponential(30, n)
        low = np.minimum(open_p, close) - np.random.exponential(30, n)
        volume = np.random.randint(1_000_000, 10_000_000, n)

        cls.dummy_df = pd.DataFrame({
            "Open": open_p,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume
        }, index=dates)

        cls.data_feed = IDXDataFeed()
        cls.strategy = StrategyEngine()
        cls.risk_mgr = RiskManager(capital=INITIAL_CAPITAL)

    def test_01_indicators_calculation(self):
        """Memverifikasi seluruh indikator teknikal terhitung dengan valid."""
        df_ind = calculate_all_indicators(self.dummy_df)
        self.assertIn("EMA20", df_ind.columns)
        self.assertIn("EMA50", df_ind.columns)
        self.assertIn("RSI14", df_ind.columns)
        self.assertIn("ATR14", df_ind.columns)
        self.assertIn("MACD", df_ind.columns)
        self.assertIn("VOL_RATIO", df_ind.columns)

        # Cek batas logis RSI (0 - 100)
        valid_rsi = df_ind["RSI14"].dropna()
        self.assertTrue((valid_rsi >= 0).all() and (valid_rsi <= 100).all())

        # Cek ATR bernilai positif
        valid_atr = df_ind["ATR14"].dropna()
        self.assertTrue((valid_atr > 0).all())

    def test_02_risk_manager_position_sizing(self):
        """Memverifikasi pembatasan risiko dan perhitungan lot saham."""
        entry_price = 5000.0
        stop_loss = 4800.0  # Risk per share = Rp 200 (4%)
        take_profit = 5400.0

        order = self.risk_mgr.calculate_buy_order(
            ticker="BBCA.JK",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_cash=INITIAL_CAPITAL,
            current_equity=INITIAL_CAPITAL,
            active_positions_count=0
        )
        self.assertIsNotNone(order)
        self.assertEqual(order.shares % SHARES_PER_LOT, 0)
        self.assertTrue(order.lots > 0)
        self.assertTrue(order.total_outlay <= INITIAL_CAPITAL)

        # Risiko rupiah tidak boleh melebihi batas 2% dari modal (Rp 2.000.000)
        max_allowed_risk = INITIAL_CAPITAL * MAX_RISK_PER_TRADE
        self.assertLessEqual(order.risk_amount_rp, max_allowed_risk)

    def test_03_strategy_evaluation(self):
        """Memverifikasi StrategyEngine menghasilkan TradeSignal berstruktur benar."""
        df_ind = calculate_all_indicators(self.dummy_df)
        signal = self.strategy.evaluate_bar(df_ind, "TEST.JK", idx=-1)
        self.assertIsInstance(signal, TradeSignal)
        self.assertIn(signal.action, ["BUY", "SELL", "HOLD"])
        self.assertTrue(signal.price > 0)

    def test_04_data_feed_live_or_cache(self):
        """Memverifikasi pengunduhan data riil Yahoo Finance untuk BBCA.JK."""
        df = self.data_feed.fetch_historical_data("BBCA.JK", period="3mo", interval="1d")
        self.assertFalse(df.empty)
        self.assertGreaterEqual(len(df), 20)
        self.assertTrue("Close" in df.columns)
        self.assertTrue((df["Close"] > 0).all())

    def test_05_backtest_engine_execution(self):
        """Memverifikasi mesin backtesting berjalan tanpa crash dan menghasilkan metrik lengkap."""
        df = self.data_feed.fetch_historical_data("BBCA.JK", period="1y", interval="1d")
        if df.empty:
            df = self.dummy_df

        backtester = BacktestEngine(initial_capital=INITIAL_CAPITAL)
        res = backtester.run_single(df, "BBCA.JK")

        self.assertIsInstance(res, BacktestResult)
        self.assertEqual(res.initial_capital, INITIAL_CAPITAL)
        self.assertGreater(res.final_equity, 0)
        self.assertTrue(0 <= res.win_rate_pct <= 100)
        self.assertGreaterEqual(res.max_drawdown_pct, 0.0)
        print(f"\n[Test Backtest BBCA.JK] Trades: {res.total_trades}, Win Rate: {res.win_rate_pct}%, Net PnL: Rp {res.net_profit_rp:,.0f} ({res.net_profit_pct}%), Max DD: {res.max_drawdown_pct}%")

    def test_06_scanner_pipeline(self):
        """Memverifikasi scanner mampu mengevaluasi saham dan memformat laporan Telegram."""
        # Gunakan 3 saham utama untuk uji cepat
        test_watchlist = ["BBCA.JK", "BBRI.JK", "BMRI.JK"]
        scanner = StockScanner(watchlist=test_watchlist, data_feed=self.data_feed)
        res = scanner.scan()
        self.assertEqual(res["total_scanned"], len(test_watchlist))
        report = scanner.format_telegram_report(res)
        self.assertIn("LAPORAN AI TRADING AGENT IDX", report)
        self.assertIn("*Total Saham Dipantau:* 3 emiten", report)


if __name__ == "__main__":
    unittest.main()
