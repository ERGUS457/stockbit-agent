"""
Modul Algoritma Strategi Sinyal Trading (Buy & Sell)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np

from indicators import calculate_all_indicators
from config import (
    EMA_FAST,
    EMA_SLOW,
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    VOLUME_FACTOR,
    ATR_SL_MULTIPLIER,
    MIN_RISK_REWARD_RATIO
)

@dataclass
class TradeSignal:
    ticker: str
    action: str            # 'BUY', 'SELL', 'HOLD'
    price: float           # Harga saat sinyal muncul
    timestamp: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    reason: str = ""
    strategy_name: str = "IDX-TrendMomentum"


class StrategyEngine:
    """
    Engine untuk menghasilkan sinyal BUY dan SELL berdasarkan kombinasi
    Trend (EMA), Momentum (RSI & MACD), serta Konfirmasi Volume & ATR.
    """
    def __init__(
        self,
        ema_fast: int = EMA_FAST,
        ema_slow: int = EMA_SLOW,
        rsi_oversold: float = RSI_OVERSOLD,
        rsi_overbought: float = RSI_OVERBOUGHT,
        vol_factor: float = VOLUME_FACTOR,
        atr_multiplier: float = ATR_SL_MULTIPLIER
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.vol_factor = vol_factor
        self.atr_multiplier = atr_multiplier

    def evaluate_bar(self, df_with_indicators: pd.DataFrame, ticker: str, idx: int = -1) -> TradeSignal:
        """
        Mengevaluasi bar/candle tertentu (default bar terakhir / saat ini).
        """
        df = df_with_indicators
        if df.empty or len(df) < 50:
            return TradeSignal(
                ticker=ticker,
                action="HOLD",
                price=0.0,
                timestamp=datetime.now(),
                reason="Data tidak cukup untuk kalkulasi indikator (< 50 candle)"
            )

        # Bar saat ini
        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        timestamp = df.index[idx]

        close = float(row["Close"])
        open_price = float(row["Open"])
        ema20 = float(row["EMA20"])
        ema50 = float(row["EMA50"])
        rsi = float(row["RSI14"])
        vol_ratio = float(row["VOL_RATIO"]) if not np.isnan(row["VOL_RATIO"]) else 1.0
        atr = float(row["ATR14"]) if not np.isnan(row["ATR14"]) else (close * 0.03)
        macd = float(row["MACD"])
        macd_sig = float(row["MACD_SIGNAL"])
        prev_macd = float(prev_row["MACD"])
        prev_macd_sig = float(prev_row["MACD_SIGNAL"])

        # -------------------------------------------------------------
        # LOGIKA 1: TREND PULLBACK BUY
        # Syarat:
        # 1. Tren Makro Bullish: Close > EMA50 dan EMA20 > EMA50
        # 2. Pullback Sehat: RSI berada di rentang 40 - 58 (tidak overbought)
        # 3. Reversal Candle: Candle hijau (Close > Open) dan memantul di atas/dekat EMA20
        # 4. Momentum MACD membaik (Histogram naik atau MACD Golden Cross)
        # -------------------------------------------------------------
        is_bullish_trend = (close > ema50) and (ema20 >= ema50)
        is_pullback = (self.rsi_oversold <= rsi <= 58)
        is_green_candle = (close > open_price)
        is_bouncing = (close >= ema20 * 0.985)
        is_macd_bullish = (macd >= macd_sig) or (macd > prev_macd)
        is_volume_confirmed = (vol_ratio >= 1.0)

        if is_bullish_trend and is_pullback and is_green_candle and is_bouncing and is_macd_bullish and is_volume_confirmed:
            # Hitung Stop Loss berbasis ATR (berjarak 2x ATR di bawah harga close)
            # Dibatasi maksimal 5% di bawah harga entry agar risiko terukur
            sl_distance = max(atr * self.atr_multiplier, close * 0.03)
            sl_distance = min(sl_distance, close * 0.05)
            stop_loss = round(close - sl_distance, 0)

            # Hitung Take Profit dengan Risk:Reward minimal 1:2
            risk = close - stop_loss
            take_profit = round(close + (risk * MIN_RISK_REWARD_RATIO), 0)
            rr = (take_profit - close) / risk if risk > 0 else 2.0

            return TradeSignal(
                ticker=ticker,
                action="BUY",
                price=close,
                timestamp=timestamp,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=round(rr, 2),
                reason=f"Trend Bullish (EMA20>50), RSI Pullback ({rsi:.1f}), Volume Confirmed ({vol_ratio:.1f}x)",
                strategy_name="Trend-Pullback-Pro"
            )

        # -------------------------------------------------------------
        # LOGIKA 2: BREAKOUT MOMENTUM BUY
        # Syarat:
        # 1. Harga breakout menembus high 20 candle terakhir
        # 2. Volume Spike masif (>= 1.5x rata-rata 20 hari)
        # 3. RSI kuat (55 - 72)
        # -------------------------------------------------------------
        if len(df) >= 21:
            recent_high = float(df["High"].iloc[-21:-1].max())
            is_breakout = (close > recent_high) and (vol_ratio >= self.vol_factor)
            if is_breakout and (55 <= rsi <= 72):
                stop_loss = round(close - (atr * self.atr_multiplier), 0)
                risk = close - stop_loss
                if risk > 0:
                    take_profit = round(close + (risk * MIN_RISK_REWARD_RATIO), 0)
                    rr = (take_profit - close) / risk
                    return TradeSignal(
                        ticker=ticker,
                        action="BUY",
                        price=close,
                        timestamp=timestamp,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        risk_reward_ratio=round(rr, 2),
                        reason=f"Breakout 20-Day High ({recent_high:.0f}) + Volume Spike ({vol_ratio:.1f}x)",
                        strategy_name="Breakout-Momentum"
                    )

        # -------------------------------------------------------------
        # LOGIKA 3: SELL SIGNAL (EXIT / TAKE PROFIT / STOP LOSS)
        # Syarat:
        # 1. RSI Jenuh Beli Ekstrem (> 75) dengan candle bearish (Close < Open)
        # 2. Atau Tren Patah: Close jatuh di bawah EMA50 dengan volume besar
        # -------------------------------------------------------------
        is_overbought_exit = (rsi >= self.rsi_overbought) and (close < open_price)
        is_trend_broken = (close < ema50) and (prev_row["Close"] >= prev_row["EMA50"])

        if is_overbought_exit:
            return TradeSignal(
                ticker=ticker,
                action="SELL",
                price=close,
                timestamp=timestamp,
                reason=f"Take Profit: RSI Jenuh Beli ({rsi:.1f}) dengan Bearish Rejection",
                strategy_name="Exit-Overbought"
            )

        if is_trend_broken:
            return TradeSignal(
                ticker=ticker,
                action="SELL",
                price=close,
                timestamp=timestamp,
                reason=f"Cut Loss/Exit: Harga Breakdown di bawah EMA50 ({ema50:.0f})",
                strategy_name="Exit-TrendBreak"
            )

        return TradeSignal(
            ticker=ticker,
            action="HOLD",
            price=close,
            timestamp=timestamp,
            reason="Kondisi pasar sideways atau belum memenuhi kriteria entry/exit"
        )
