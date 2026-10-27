"""
Modul Scanner Multi-Saham IDX (Screening Sinyal Buy & Sell Terkini)
"""

from datetime import datetime
import pandas as pd
from typing import Optional

from config import DEFAULT_WATCHLIST, INITIAL_CAPITAL
from data_feed import IDXDataFeed
from indicators import calculate_all_indicators
from strategy import StrategyEngine, TradeSignal
from risk_manager import RiskManager

class StockScanner:
    """
    Scanner untuk menyaring saham-saham IDX yang sedang memberikan sinyal trading.
    """
    def __init__(
        self,
        watchlist: Optional[list[str]] = None,
        data_feed: Optional[IDXDataFeed] = None,
        strategy_engine: Optional[StrategyEngine] = None,
        risk_manager: Optional[RiskManager] = None
    ):
        self.watchlist = watchlist or DEFAULT_WATCHLIST
        self.data_feed = data_feed or IDXDataFeed()
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.risk_manager = risk_manager or RiskManager()

    def scan(self, force_refresh: bool = False) -> dict:
        """
        Menjalankan scanning pada seluruh saham di watchlist.
        """
        buy_signals = []
        sell_signals = []
        hold_count = 0
        failed_count = 0

        print(f"\n[Scanner] Memulai scanning {len(self.watchlist)} saham IDX...")

        for ticker in self.watchlist:
            try:
                df = self.data_feed.fetch_historical_data(ticker, period="1y", interval="1d", force_refresh=force_refresh)
                if df.empty or len(df) < 50:
                    failed_count += 1
                    continue

                df_calc = calculate_all_indicators(df)
                sig = self.strategy_engine.evaluate_bar(df_calc, ticker, idx=-1)

                if sig.action == "BUY" and sig.stop_loss and sig.take_profit:
                    # Hitung rekomendasi order lot
                    order = self.risk_manager.calculate_buy_order(
                        ticker=ticker,
                        entry_price=sig.price,
                        stop_loss=sig.stop_loss,
                        take_profit=sig.take_profit,
                        current_cash=self.risk_manager.capital,
                        current_equity=self.risk_manager.capital,
                        active_positions_count=0
                    )
                    buy_signals.append({
                        "ticker": ticker,
                        "price": sig.price,
                        "stop_loss": sig.stop_loss,
                        "take_profit": sig.take_profit,
                        "take_profit_tp1": sig.take_profit_tp1 or sig.take_profit,
                        "take_profit_tp2": sig.take_profit_tp2 or sig.take_profit,
                        "risk_reward": sig.risk_reward_ratio,
                        "adx": sig.adx_value,
                        "cmf": sig.cmf_value,
                        "market_regime": sig.market_regime,
                        "bandarmologi_flow": sig.bandarmologi_flow,
                        "lots": order.lots if order else 0,
                        "estimated_outlay": order.total_outlay if order else 0,
                        "reason": sig.reason,
                        "strategy": sig.strategy_name,
                        "timestamp": sig.timestamp
                    })
                elif sig.action == "SELL":
                    sell_signals.append({
                        "ticker": ticker,
                        "price": sig.price,
                        "adx": sig.adx_value,
                        "cmf": sig.cmf_value,
                        "market_regime": sig.market_regime,
                        "bandarmologi_flow": sig.bandarmologi_flow,
                        "reason": sig.reason,
                        "strategy": sig.strategy_name,
                        "timestamp": sig.timestamp
                    })
                else:
                    hold_count += 1

            except Exception as e:
                print(f"[Scanner] Error scanning {ticker}: {e}")
                failed_count += 1

        return {
            "timestamp": datetime.now(),
            "total_scanned": len(self.watchlist),
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "hold_count": hold_count,
            "failed_count": failed_count
        }

    def format_telegram_report(self, scan_results: dict) -> str:
        """
        Format laporan ke teks Telegram yang rapi, informatif, dan profesional.
        """
        lines = []
        now_str = scan_results["timestamp"].strftime("%d %b %Y %H:%M WIB")
        lines.append(f"🤖 *LAPORAN AI TRADING AGENT IDX*")
        lines.append(f"⏱ *Waktu Scan:* {now_str}")
        lines.append(f"📊 *Total Saham Dipantau:* {scan_results['total_scanned']} emiten\n")

        buys = scan_results["buy_signals"]
        sells = scan_results["sell_signals"]

        if buys:
            lines.append(f"🟢 *REKOMENDASI BUY SIGNAL ({len(buys)})*")
            for b in buys:
                sl_pct = ((b['stop_loss'] - b['price']) / b['price']) * 100
                tp_pct = ((b['take_profit'] - b['price']) / b['price']) * 100
                lines.append(f"• *{b['ticker']}*")
                lines.append(f"  - Entry: `Rp {b['price']:,.0f}`")
                lines.append(f"  - Stop Loss: `Rp {b['stop_loss']:,.0f}` ({sl_pct:.1f}%)")
                lines.append(f"  - Take Profit: `Rp {b['take_profit']:,.0f}` (+{tp_pct:.1f}%)")
                lines.append(f"  - Risk/Reward: `1:{b['risk_reward']}`")
                lines.append(f"  - Rekomendasi Lot: *{b['lots']} lot* (~Rp {b['estimated_outlay']:,.0f})")
                lines.append(f"  - Sinyal: _{b['reason']}_\n")
        else:
            lines.append("🟢 *BUY SIGNAL:* Tidak ada setup valid yang terkonfirmasi hari ini.\n")

        if sells:
            lines.append(f"🔴 *PERINGATAN SELL / EXIT SIGNAL ({len(sells)})*")
            for s in sells:
                lines.append(f"• *{s['ticker']}* @ `Rp {s['price']:,.0f}`")
                lines.append(f"  - Alasan: _{s['reason']}_\n")
        else:
            lines.append("🔴 *SELL SIGNAL:* Tidak ada peringatan exit khusus.\n")

        lines.append(f"ℹ️ *Status Lainnya:* {scan_results['hold_count']} HOLD (Sideways/Netral), {scan_results['failed_count']} data tidak tersedia.")
        lines.append("🛡 *Prinsip:* Selalu disiplin Stop Loss & Money Management.")
        return "\n".join(lines)


if __name__ == "__main__":
    scanner = StockScanner()
    res = scanner.scan()
    report = scanner.format_telegram_report(res)
    print(report)
