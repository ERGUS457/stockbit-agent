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
    take_profit_tp1: Optional[float] = None   # Target profit parsial (1:1.5 RR)
    take_profit_tp2: Optional[float] = None   # Target profit ekspansi (1:2.5 RR)
    risk_reward_ratio: Optional[float] = None
    adx_value: Optional[float] = None
    cmf_value: Optional[float] = None
    market_regime: str = "Neutral"
    bandarmologi_flow: str = "Neutral"
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

        # Metrik Filter Lanjutan: ADX (Trend vs Sideways) & CMF (Smart Money Accumulation / Bandarmologi)
        adx = float(row.get("ADX14", 25.0)) if not np.isnan(row.get("ADX14", np.nan)) else 25.0
        cmf = float(row.get("CMF20", 0.0)) if not np.isnan(row.get("CMF20", np.nan)) else 0.0
        plus_di = float(row.get("PLUS_DI", 20.0)) if not np.isnan(row.get("PLUS_DI", np.nan)) else 20.0
        minus_di = float(row.get("MINUS_DI", 20.0)) if not np.isnan(row.get("MINUS_DI", np.nan)) else 20.0

        if adx >= 25 and plus_di > minus_di:
            market_regime = "Strong Bullish Trend"
        elif adx >= 25 and minus_di > plus_di:
            market_regime = "Strong Bearish Trend"
        elif adx < 20:
            market_regime = "Sideways / Choppy"
        else:
            market_regime = "Moderate Trend"

        if cmf >= 0.08:
            bandarmologi_flow = "Akumulasi Kuat (Smart Money Inflow)"
        elif cmf > 0.02:
            bandarmologi_flow = "Akumulasi Moderat"
        elif cmf <= -0.08:
            bandarmologi_flow = "Distribusi Besar (Smart Money Outflow)"
        else:
            bandarmologi_flow = "Netral / Ranging Flow"

        # -------------------------------------------------------------
        # LOGIKA 1: TREND PULLBACK BUY
        # Syarat:
        # 1. Tren Makro Bullish: Close > EMA50 dan EMA20 > EMA50
        # 2. Pullback Sehat: RSI berada di rentang 40 - 58 (tidak overbought)
        # 3. Reversal Candle: Candle hijau (Close > Open) dan memantul di atas/dekat EMA20
        # 4. Momentum MACD membaik (Histogram naik atau MACD Golden Cross)
        # 5. Filter ADX & CMF: Bukan pasar sideways berat (ADX >= 18 atau +DI > -DI) dan CMF tidak distribusi masif
        # -------------------------------------------------------------
        is_bullish_trend = (close > ema50) and (ema20 >= ema50)
        is_pullback = (self.rsi_oversold <= rsi <= 58)
        is_green_candle = (close > open_price)
        is_bouncing = (close >= ema20 * 0.985)
        is_macd_bullish = (macd >= macd_sig) or (macd > prev_macd)
        is_volume_confirmed = (vol_ratio >= 1.0)
        is_not_distributing = (cmf >= -0.10)
        is_trend_viable = (adx >= 18) or (plus_di >= minus_di)

        if is_bullish_trend and is_pullback and is_green_candle and is_bouncing and is_macd_bullish and is_volume_confirmed and is_not_distributing and is_trend_viable:
            # Hitung Stop Loss berbasis ATR (berjarak 2x ATR di bawah harga close)
            # Dibatasi maksimal 5% di bawah harga entry agar risiko terukur
            sl_distance = max(atr * self.atr_multiplier, close * 0.03)
            sl_distance = min(sl_distance, close * 0.05)
            stop_loss = round(close - sl_distance, 0)

            # Hitung Multi-Target Take Profit: TP1 (1:1.5 RR Breakeven) & TP2 (1:2.5 RR Runner)
            risk = close - stop_loss
            tp1 = round(close + (risk * 1.5), 0)
            tp2 = round(close + (risk * 2.5), 0)
            rr = (tp2 - close) / risk if risk > 0 else 2.5

            return TradeSignal(
                ticker=ticker,
                action="BUY",
                price=close,
                timestamp=timestamp,
                stop_loss=stop_loss,
                take_profit=tp2,
                take_profit_tp1=tp1,
                take_profit_tp2=tp2,
                risk_reward_ratio=round(rr, 2),
                adx_value=round(adx, 1),
                cmf_value=round(cmf, 3),
                market_regime=market_regime,
                bandarmologi_flow=bandarmologi_flow,
                reason=f"Trend Bullish (EMA20>50), RSI Pullback ({rsi:.1f}), Volume Confirmed ({vol_ratio:.1f}x), {bandarmologi_flow}",
                strategy_name="Trend-Pullback-Pro"
            )

        # -------------------------------------------------------------
        # LOGIKA 2: BREAKOUT MOMENTUM BUY
        # Syarat:
        # 1. Harga breakout menembus high 20 candle terakhir
        # 2. Volume Spike masif (>= 1.5x rata-rata 20 hari)
        # 3. RSI kuat (55 - 72)
        # 4. Filter Anti-Bulltrap: ADX >= 20 dan CMF >= -0.02 (didukung akumulasi)
        # -------------------------------------------------------------
        if len(df) >= 21:
            recent_high = float(df["High"].iloc[-21:-1].max())
            is_breakout = (close > recent_high) and (vol_ratio >= self.vol_factor)
            is_healthy_breakout = is_breakout and (55 <= rsi <= 72) and (adx >= 20) and (cmf >= -0.05)
            if is_healthy_breakout:
                stop_loss = round(close - (atr * self.atr_multiplier), 0)
                risk = close - stop_loss
                if risk > 0:
                    tp1 = round(close + (risk * 1.5), 0)
                    tp2 = round(close + (risk * 2.5), 0)
                    rr = (tp2 - close) / risk
                    return TradeSignal(
                        ticker=ticker,
                        action="BUY",
                        price=close,
                        timestamp=timestamp,
                        stop_loss=stop_loss,
                        take_profit=tp2,
                        take_profit_tp1=tp1,
                        take_profit_tp2=tp2,
                        risk_reward_ratio=round(rr, 2),
                        adx_value=round(adx, 1),
                        cmf_value=round(cmf, 3),
                        market_regime=market_regime,
                        bandarmologi_flow=bandarmologi_flow,
                        reason=f"Breakout 20-Day High ({recent_high:.0f}) + Volume Spike ({vol_ratio:.1f}x) [ADX: {adx:.1f}, {bandarmologi_flow}]",
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
                adx_value=round(adx, 1),
                cmf_value=round(cmf, 3),
                market_regime=market_regime,
                bandarmologi_flow=bandarmologi_flow,
                reason=f"Take Profit: RSI Jenuh Beli ({rsi:.1f}) dengan Bearish Rejection",
                strategy_name="Exit-Overbought"
            )

        if is_trend_broken:
            return TradeSignal(
                ticker=ticker,
                action="SELL",
                price=close,
                timestamp=timestamp,
                adx_value=round(adx, 1),
                cmf_value=round(cmf, 3),
                market_regime=market_regime,
                bandarmologi_flow=bandarmologi_flow,
                reason=f"Cut Loss/Exit: Harga Breakdown di bawah EMA50 ({ema50:.0f})",
                strategy_name="Exit-TrendBreak"
            )

        return TradeSignal(
            ticker=ticker,
            action="HOLD",
            price=close,
            timestamp=timestamp,
            adx_value=round(adx, 1),
            cmf_value=round(cmf, 3),
            market_regime=market_regime,
            bandarmologi_flow=bandarmologi_flow,
            reason="Kondisi pasar sideways atau belum memenuhi kriteria entry/exit"
        )
