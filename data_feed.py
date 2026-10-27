"""
Modul Pengambilan Data Saham IDX (Yahoo Finance / Stockbit Data Feed)
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
import requests
import pandas as pd
import numpy as np

from config import CACHE_DIR

class IDXDataFeed:
    """
    Kelas untuk mengambil, membersihkan, dan meng-cache data historis saham IDX.
    """
    def __init__(self, cache_dir: Path = CACHE_DIR, cache_expiry_hours: int = 12):
        self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.cache_dir = Path("/tmp/cache")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_expiry_sec = cache_expiry_hours * 3600
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def _normalize_ticker(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        if not ticker.endswith(".JK"):
            ticker = f"{ticker}.JK"
        return ticker

    def fetch_historical_data(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Mengambil data historis OHLCV untuk saham IDX.
        period: '1mo', '3mo', '6mo', '1y', '2y', '5y'
        interval: '1d', '1wk', '1h', '15m', '5m'
        """
        symbol = self._normalize_ticker(ticker)
        cache_file = self.cache_dir / f"{symbol}_{period}_{interval}.csv"

        # Cek cache lokal
        if not force_refresh and cache_file.exists():
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < self.cache_expiry_sec:
                try:
                    df = pd.read_csv(cache_file, parse_dates=["Date"], index_col="Date")
                    if not df.empty:
                        return df
                except Exception:
                    pass

        # Request ke endpoint Yahoo Finance v8 chart
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={period}&interval={interval}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                print(f"[DataFeed] Gagal mengambil data {symbol}: HTTP {resp.status_code}")
                return pd.DataFrame()

            payload = resp.json()
            chart = payload.get("chart", {})
            results = chart.get("result")
            if not results:
                print(f"[DataFeed] Tidak ada data ditemukan untuk {symbol}")
                return pd.DataFrame()

            res = results[0]
            timestamps = res.get("timestamp", [])
            indicators = res.get("indicators", {})
            quotes = indicators.get("quote", [{}])[0]

            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            # Bangun DataFrame
            dates = [datetime.fromtimestamp(ts) for ts in timestamps]
            df = pd.DataFrame({
                "Date": dates,
                "Open": opens,
                "High": highs,
                "Low": lows,
                "Close": closes,
                "Volume": volumes
            })

            # Bersihkan baris null / NaN
            df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
            # Filter baris dengan harga 0 atau negatif
            df = df[(df["Close"] > 0) & (df["Volume"] >= 0)]

            if df.empty:
                return pd.DataFrame()

            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)

            # Simpan ke cache jika diizinkan (abaikan error filesystem read-only)
            try:
                df.to_csv(cache_file)
            except Exception:
                pass

            return df

        except Exception as e:
            print(f"[DataFeed] Error fetching {symbol}: {e}")
            return pd.DataFrame()

    def fetch_multiple(self, tickers: list, period: str = "1y", interval: str = "1d") -> dict[str, pd.DataFrame]:
        """
        Mengambil data beberapa saham sekaligus.
        """
        results = {}
        for ticker in tickers:
            symbol = self._normalize_ticker(ticker)
            df = self.fetch_historical_data(symbol, period=period, interval=interval)
            if not df.empty:
                results[symbol] = df
        return results


if __name__ == "__main__":
    feed = IDXDataFeed()
    print("Menguji data feed untuk BBCA.JK...")
    df_bbca = feed.fetch_historical_data("BBCA.JK", period="3mo")
    print("Shape:", df_bbca.shape)
    print("Head:\n", df_bbca.head(3))
    print("Tail:\n", df_bbca.tail(3))
