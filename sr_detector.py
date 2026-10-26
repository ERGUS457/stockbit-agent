"""
Modul Deteksi Support & Resistance (S/R) Saham IDX
Menganalisis level Pivot Points, Swing Levels, dan Event Rebound / Breakout / Rejection.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np

@dataclass
class SREvent:
    ticker: str
    event_type: str  # "SUPPORT_BOUNCE", "RESISTANCE_BREAKOUT", "RESISTANCE_REJECTION", "SUPPORT_BREAKDOWN", "IN_RANGE"
    current_price: float
    support_level: float
    resistance_level: float
    pivot_point: float
    volume_ratio: float
    rsi: float
    description: str
    severity: str    # "BULLISH_SIGNAL", "BEARISH_WARNING", "NEUTRAL"
    action_hint: str # "BUY", "SELL", "HOLD"

class SRDetector:
    """
    Engine untuk mengidentifikasi level Support & Resistance kunci serta mendeteksi interaksi harga.
    """
    def __init__(self, tolerance_pct: float = 0.012, swing_window: int = 20):
        self.tolerance_pct = tolerance_pct  # 1.2% zona toleransi uji level
        self.swing_window = swing_window

    def calculate_levels(self, df: pd.DataFrame) -> dict:
        """
        Menghitung Pivot Point, Support 1-3, Resistance 1-3, dan Swing High/Low.
        """
        if len(df) < 5:
            return {}

        prev_bar = df.iloc[-2]
        curr_bar = df.iloc[-1]

        high = float(prev_bar["High"])
        low = float(prev_bar["Low"])
        close = float(prev_bar["Close"])

        # Classic Floor Pivot Points
        pivot = (high + low + close) / 3.0
        r1 = (2.0 * pivot) - low
        s1 = (2.0 * pivot) - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        r3 = high + 2.0 * (pivot - low)
        s3 = low - 2.0 * (high - pivot)

        # 20-day Swing High & Swing Low (Level Struktural)
        window_df = df.iloc[-min(len(df), self.swing_window+1):-1]
        swing_high = float(window_df["High"].max())
        swing_low = float(window_df["Low"].min())

        return {
            "pivot": round(pivot, 2),
            "s1": round(s1, 2),
            "s2": round(s2, 2),
            "s3": round(s3, 2),
            "r1": round(r1, 2),
            "r2": round(r2, 2),
            "r3": round(r3, 2),
            "swing_high": round(swing_high, 2),
            "swing_low": round(swing_low, 2)
        }

    def detect_event(self, df: pd.DataFrame, ticker: str) -> SREvent:
        """
        Mendeteksi apakah saat ini sedang terjadi interaksi kunci dengan level Support/Resistance.
        """
        levels = self.calculate_levels(df)
        if not levels:
            curr_close = float(df.iloc[-1]["Close"]) if not df.empty else 0.0
            return SREvent(
                ticker=ticker,
                event_type="IN_RANGE",
                current_price=curr_close,
                support_level=0.0,
                resistance_level=0.0,
                pivot_point=0.0,
                volume_ratio=1.0,
                rsi=50.0,
                description="Data historis belum mencukupi untuk kalkulasi S/R.",
                severity="NEUTRAL",
                action_hint="HOLD"
            )

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(curr["Close"])
        open_p = float(curr["Open"])
        high = float(curr["High"])
        low = float(curr["Low"])

        vol_ratio = float(curr.get("VOL_RATIO", 1.0))
        rsi = float(curr.get("RSI14", 50.0))

        # Tentukan Support dan Resistance terdekat
        pivot = levels["pivot"]
        s1 = levels["s1"]
        s2 = levels["s2"]
        r1 = levels["r1"]
        r2 = levels["r2"]
        swing_high = levels["swing_high"]
        swing_low = levels["swing_low"]

        # Support terdekat di bawah harga saat ini
        s3 = levels["s3"]
        r3 = levels["r3"]
        supports_below = [s for s in [s3, s2, s1, swing_low, pivot] if s < close]
        nearest_support = max(supports_below) if supports_below else s1

        # Resistance terdekat di atas harga saat ini
        resistances_above = [r for r in [r1, r2, r3, swing_high, pivot] if r > close]
        nearest_resistance = min(resistances_above) if resistances_above else r1

        tol = self.tolerance_pct

        # 1. DETEKSI RESISTANCE BREAKOUT (Menembus R1 atau Swing High dengan Volume Kuat)
        target_res = swing_high if abs(close - swing_high) < abs(close - r1) else r1
        if (close > target_res) and (prev["Close"] <= target_res * (1 + tol/2)):
            if vol_ratio >= 1.25 and close > open_p:
                return SREvent(
                    ticker=ticker,
                    event_type="RESISTANCE_BREAKOUT",
                    current_price=close,
                    support_level=target_res,
                    resistance_level=r2 if target_res == r1 else target_res * 1.05,
                    pivot_point=pivot,
                    volume_ratio=vol_ratio,
                    rsi=rsi,
                    description=f"Konfirmasi Breakout di atas Resistance Rp {target_res:,.0f} dengan lonjakan volume {vol_ratio:.1f}x.",
                    severity="BULLISH_SIGNAL",
                    action_hint="BUY"
                )

        # 2. DETEKSI SUPPORT BOUNCE (Menguji Support lalu mantul dengan candle hijau / rejection)
        target_sup = swing_low if abs(low - swing_low) < abs(low - s1) else s1
        if (low <= target_sup * (1 + tol)) and (close >= target_sup):
            # Candle berbalik naik (pantulan)
            if close > open_p or (close - low) > (high - close):
                if rsi <= 60:
                    return SREvent(
                        ticker=ticker,
                        event_type="SUPPORT_BOUNCE",
                        current_price=close,
                        support_level=target_sup,
                        resistance_level=pivot if target_sup < pivot else r1,
                        pivot_point=pivot,
                        volume_ratio=vol_ratio,
                        rsi=rsi,
                        description=f"Rebound/Pantulan kuat dari zona Support Rp {target_sup:,.0f}. Ekor bawah menolak turun (Hammer/Rejection).",
                        severity="BULLISH_SIGNAL",
                        action_hint="BUY"
                    )

        # 3. DETEKSI RESISTANCE REJECTION (Gagal menembus Resistance, candle berbalik merah)
        if (high >= target_res * (1 - tol)) and (close < target_res) and (close < open_p):
            if rsi >= 62 or (high - close) > (close - low):
                return SREvent(
                    ticker=ticker,
                    event_type="RESISTANCE_REJECTION",
                    current_price=close,
                    support_level=nearest_support,
                    resistance_level=target_res,
                    pivot_point=pivot,
                    volume_ratio=vol_ratio,
                    rsi=rsi,
                    description=f"Gagal menembus (Rejection) pada Resistance Rp {target_res:,.0f}. Tekanan jual meningkat.",
                    severity="BEARISH_WARNING",
                    action_hint="SELL"
                )

        # 4. DETEKSI SUPPORT BREAKDOWN (Jebol ke bawah Support kunci)
        if (close < target_sup * (1 - tol/2)) and (prev["Close"] >= target_sup * (1 - tol)):
            return SREvent(
                ticker=ticker,
                event_type="SUPPORT_BREAKDOWN",
                current_price=close,
                support_level=s2 if target_sup == s1 else target_sup * 0.95,
                resistance_level=target_sup,
                pivot_point=pivot,
                volume_ratio=vol_ratio,
                rsi=rsi,
                description=f"Peringatan! Harga jebol (Breakdown) di bawah Support kunci Rp {target_sup:,.0f}. Risiko penurunan berlanjut.",
                severity="BEARISH_WARNING",
                action_hint="SELL"
            )

        # 5. DEFAULT: IN RANGE / CONSOLIDATION
        return SREvent(
            ticker=ticker,
            event_type="IN_RANGE",
            current_price=close,
            support_level=nearest_support,
            resistance_level=nearest_resistance,
            pivot_point=pivot,
            volume_ratio=vol_ratio,
            rsi=rsi,
            description=f"Harga bergerak stabil di dalam rentang Support Rp {nearest_support:,.0f} dan Resistance Rp {nearest_resistance:,.0f}.",
            severity="NEUTRAL",
            action_hint="HOLD"
        )
