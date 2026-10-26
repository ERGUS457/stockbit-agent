"""
Modul Kalkulasi Indikator Teknikal Kuantitatif
"""

import pandas as pd
import numpy as np

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Menghitung Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Menghitung Simple Moving Average (SMA)."""
    return series.rolling(window=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Menghitung Relative Strength Index (RSI) dengan metode Wilder's Smoothing.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    # Wilder's smoothing via ewm (alpha = 1 / period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    # Jika avg_loss == 0 dan avg_gain > 0, RSI = 100
    rsi = rsi.fillna(100)
    return rsi

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Menghitung Average True Range (ATR) untuk mengukur volatilitas pasar.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr

def calculate_macd(
    series: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Menghitung MACD Line, Signal Line, dan Histogram.
    """
    ema_fast = calculate_ema(series, fast_period)
    ema_slow = calculate_ema(series, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menambahkan seluruh indikator penting ke DataFrame OHLCV.
    """
    if df.empty or len(df) < 50:
        return df

    res = df.copy()
    close = res["Close"]
    volume = res["Volume"]

    # Moving Averages
    res["EMA20"] = calculate_ema(close, 20)
    res["EMA50"] = calculate_ema(close, 50)
    res["EMA200"] = calculate_ema(close, 200)

    # Momentum
    res["RSI14"] = calculate_rsi(close, 14)
    macd_line, macd_sig, macd_hist = calculate_macd(close)
    res["MACD"] = macd_line
    res["MACD_SIGNAL"] = macd_sig
    res["MACD_HIST"] = macd_hist

    # Volatilitas & Risiko
    res["ATR14"] = calculate_atr(res, 14)

    # Volume Analysis
    res["VOL_MA20"] = calculate_sma(volume, 20)
    res["VOL_RATIO"] = res["Volume"] / (res["VOL_MA20"].replace(0, np.nan))

    return res
