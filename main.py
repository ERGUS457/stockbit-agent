"""
CLI & Entrypoint AI Trading Agent IDX (Stockbit Assistant)
"""

import sys
import argparse
from datetime import datetime
import pandas as pd

from config import DEFAULT_WATCHLIST, INITIAL_CAPITAL
from data_feed import IDXDataFeed
from backtester import BacktestEngine
from scanner import StockScanner

def run_scanner(force_refresh: bool = False):
    """Menjalankan scanning saham real-time dan menampilkan sinyal."""
    print("=" * 60)
    print("🚀 MENJALANKAN SCANNER PASAR SAHAM IDX")
    print("=" * 60)
    scanner = StockScanner()
    res = scanner.scan(force_refresh=force_refresh)
    report = scanner.format_telegram_report(res)
    print("\n" + report + "\n")
    print("=" * 60)
    return report

def run_portfolio_backtest(period: str = "1y"):
    """
    Menjalankan backtest menyeluruh pada seluruh saham di Watchlist.
    """
    print("=" * 60)
    print(f"📊 MENJALANKAN BACKTEST PORTOFOLIO SAHAM IDX ({period})")
    print(f"💰 Modal Awal Simulasi: Rp {INITIAL_CAPITAL:,.0f}")
    print("=" * 60)

    feed = IDXDataFeed()
    engine = BacktestEngine(initial_capital=INITIAL_CAPITAL)

    results = []
    all_trades = []

    for ticker in DEFAULT_WATCHLIST:
        print(f"-> Memproses data & backtest: {ticker}...")
        df = feed.fetch_historical_data(ticker, period=period, interval="1d")
        if df.empty:
            continue
        res = engine.run_single(df, ticker)
        results.append({
            "Ticker": res.ticker.replace(".JK", ""),
            "Trades": res.total_trades,
            "Win Rate (%)": f"{res.win_rate_pct:.1f}%",
            "Profit Factor": f"{res.profit_factor:.2f}",
            "Net PnL (Rp)": f"Rp {res.net_profit_rp:,.0f}",
            "Return (%)": f"{res.net_profit_pct:.2f}%",
            "Max DD (%)": f"{res.max_drawdown_pct:.2f}%"
        })
        all_trades.extend(res.trades)

    if not results:
        print("Tidak ada data untuk backtest.")
        return

    summary_df = pd.DataFrame(results)
    print("\n" + "=" * 60)
    print("🏆 HASIL RINGKASAN BACKTEST STRATEGI PER EMITEN:")
    print("=" * 60)
    print(summary_df.to_string(index=False))

    total_trades_count = len(all_trades)
    winning_trades = len([t for t in all_trades if t.pnl_rp > 0])
    overall_win_rate = (winning_trades / total_trades_count * 100) if total_trades_count > 0 else 0.0
    total_net_pnl = sum(t.pnl_rp for t in all_trades)

    print("\n" + "-" * 60)
    print(f"📈 TOTAL AKUMULATIF TRANSAKSI : {total_trades_count} Trades")
    print(f"🎯 RATA-RATA WIN RATE         : {overall_win_rate:.1f}% ({winning_trades}/{total_trades_count} Menang)")
    print(f"💵 TOTAL NET PnL              : Rp {total_net_pnl:,.0f}")
    print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="AI Trading Agent IDX Stockbit")
    parser.add_argument("--scan", action="store_true", help="Jalankan scanner pasar hari ini")
    parser.add_argument("--backtest", action="store_true", help="Jalankan backtesting portofolio")
    parser.add_argument("--period", type=str, default="1y", help="Periode backtest: 6mo, 1y, 2y")
    parser.add_argument("--refresh", action="store_true", help="Paksa download data baru tanpa cache")
    args = parser.parse_args()

    if args.scan:
        run_scanner(force_refresh=args.refresh)
    elif args.backtest:
        run_portfolio_backtest(period=args.period)
    else:
        # Default run scanner
        run_scanner(force_refresh=args.refresh)

if __name__ == "__main__":
    main()
