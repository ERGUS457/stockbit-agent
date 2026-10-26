"""
Market Monitor & S/R Alert Daemon (Fase 3 & 4)
Memindai interaksi Support & Resistance secara otomatis dan mengirim alert ke Telegram.
"""

import sys
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any

from config import DEFAULT_WATCHLIST, INITIAL_CAPITAL, TICKER_CONGLOMERATE_MAP, USER_REAL_BUDGET
from data_feed import IDXDataFeed
from indicators import calculate_all_indicators
from strategy import StrategyEngine
from risk_manager import RiskManager
from sr_detector import SRDetector, SREvent
from portfolio import VirtualPortfolio
from notifier import TelegramNotifier

class MarketMonitor:
    def __init__(self, watchlist: List[str] = DEFAULT_WATCHLIST):
        self.watchlist = watchlist
        self.data_feed = IDXDataFeed()
        self.strategy_engine = StrategyEngine()
        self.risk_manager = RiskManager(capital=INITIAL_CAPITAL)
        self.sr_detector = SRDetector()
        self.portfolio = VirtualPortfolio()
        self.notifier = TelegramNotifier()

    def run_cycle(self, force_refresh: bool = False, auto_trade: bool = True) -> Dict[str, Any]:
        """
        Menjalankan 1 putaran siklus pemantauan:
        1. Cek update harga posisi terbuka di portofolio virtual.
        2. Analisis Support & Resistance tiap emiten.
        3. Kirim alert ke Telegram jika terjadi event S/R kunci.
        4. Catat transaksi virtual jika setup valid.
        """
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Memulai pemantauan {len(self.watchlist)} saham IDX...")
        
        current_prices = {}
        detected_events: List[SREvent] = []
        radar_records = []
        alerts_sent = 0
        executed_trades = 0

        for ticker in self.watchlist:
            try:
                df = self.data_feed.fetch_historical_data(ticker, period="6mo", interval="1d", force_refresh=force_refresh)
                if df.empty or len(df) < 30:
                    continue

                df_calc = calculate_all_indicators(df)
                last_price = float(df_calc.iloc[-1]["Close"])
                current_prices[ticker] = last_price

                # Deteksi event Support & Resistance & Pivot levels
                levels = self.sr_detector.calculate_levels(df)
                sr_event = self.sr_detector.detect_event(df_calc, ticker)
                
                cost_per_lot = round(last_price * 100 * (1 + 0.0015), 0)
                affordable = cost_per_lot <= USER_REAL_BUDGET
                max_lots = int(USER_REAL_BUDGET // cost_per_lot) if affordable else 0

                radar_records.append({
                    "ticker": ticker,
                    "conglomerate": TICKER_CONGLOMERATE_MAP.get(ticker, "Konglomerat"),
                    "price": last_price,
                    "cost_per_lot": cost_per_lot,
                    "affordable": affordable,
                    "max_lots": max_lots,
                    "pivot": levels.get("pivot", 0.0),
                    "r1": levels.get("r1", 0.0),
                    "r2": levels.get("r2", 0.0),
                    "s1": levels.get("s1", 0.0),
                    "s2": levels.get("s2", 0.0),
                    "event": sr_event.event_type if sr_event else "IN_RANGE",
                    "description": sr_event.description if sr_event else "Harga dalam rentang normal.",
                    "volume_ratio": sr_event.volume_ratio if sr_event else 1.0,
                    "rsi": sr_event.rsi if sr_event else float(df_calc["RSI14"].iloc[-1])
                })
                
                if sr_event and sr_event.event_type != "IN_RANGE":
                    detected_events.append(sr_event)
                    print(f"  👉 {ticker.replace('.JK','')}: {sr_event.event_type} @ Rp {sr_event.current_price:,.0f} - {sr_event.description}")

                    # Hitung ukuran order jika sinyal BUY
                    lots = None
                    outlay = None
                    if sr_event.action_hint == "BUY":
                        sl = sr_event.support_level * 0.97  # SL 3% di bawah support
                        tp = sr_event.current_price + (2.0 * (sr_event.current_price - sl))
                        order = self.risk_manager.calculate_buy_order(
                            ticker=ticker,
                            entry_price=sr_event.current_price,
                            stop_loss=sl,
                            take_profit=tp,
                            current_cash=self.portfolio.data["cash_balance"],
                            current_equity=self.portfolio.data["total_equity"],
                            active_positions_count=len(self.portfolio.data.get("open_positions", {}))
                        )
                        if order:
                            lots = order.lots
                            outlay = order.total_outlay

                    # Kirim notifikasi ke bot Telegram
                    sent = self.notifier.send_sr_alert(sr_event, lots=lots, outlay=outlay)
                    if sent:
                        alerts_sent += 1

                    # Eksekusi virtual otomatis jika diaktifkan dan memenuhi syarat
                    if auto_trade and sr_event.action_hint == "BUY" and lots and lots > 0:
                        buy_pos = self.portfolio.execute_buy(
                            ticker=ticker,
                            price=sr_event.current_price,
                            stop_loss=sr_event.support_level * 0.97,
                            take_profit=sr_event.current_price + (2.0 * (sr_event.current_price - (sr_event.support_level * 0.97))),
                            reason=f"S/R {sr_event.event_type}: {sr_event.description}"
                        )
                        if buy_pos:
                            executed_trades += 1
                            self.notifier.send_order_alert("BUY", buy_pos)

            except Exception as e:
                print(f"  ❌ Error memproses {ticker}: {e}")

        # Simpan snapshot radar ke Neon DB
        if radar_records:
            try:
                import db
                db.save_radar_to_db(radar_records)
                print(f"📡 Snapshot {len(radar_records)} emiten berhasil disinkronkan ke Neon DB.")
            except Exception as e:
                print(f"⚠️ Gagal menyimpan snapshot radar ke Neon DB: {e}")

        # Perbarui harga posisi portofolio terbuka & cek Stop Loss / Take Profit
        triggered_exits = self.portfolio.update_prices(current_prices)
        for exit_rec in triggered_exits:
            executed_trades += 1
            self.notifier.send_order_alert("SELL", exit_rec)

        summary = self.portfolio.get_summary()
        print(f"✅ Pemantauan selesai. {len(detected_events)} event S/R terdeteksi, {alerts_sent} alert terkirim, {len(triggered_exits)} posisi keluar.")
        print(f"💼 Saldo Kas: Rp {summary['cash_balance']:,.0f} | Total Ekuitas: Rp {summary['total_equity']:,.0f} | Posisi Terbuka: {summary['open_positions_count']}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "events_count": len(detected_events),
            "alerts_sent": alerts_sent,
            "portfolio_summary": summary
        }

    def run_daemon(self, interval_seconds: int = 300):
        """
        Menjalankan loop pemantauan berkala (misal setiap 5 menit / 300 detik).
        """
        print(f"🚀 Memulai daemon pemantau pasar IDX (Interval: {interval_seconds} detik)...")
        print("Tekan Ctrl+C untuk menghentikan.")
        
        while True:
            try:
                self.run_cycle(force_refresh=True, auto_trade=True)
            except Exception as e:
                print(f"⚠️ Error dalam siklus pemantauan: {e}")
            
            time.sleep(interval_seconds)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Market Monitor & S/R Alert Daemon")
    parser.add_argument("--once", action="store_true", help="Jalankan pemantauan 1 kali")
    parser.add_argument("--daemon", action="store_true", help="Jalankan pemantauan berkelanjutan (daemon)")
    parser.add_argument("--interval", type=int, default=300, help="Interval loop daemon dalam detik (default: 300)")
    parser.add_argument("--no-trade", action="store_true", help="Hanya kirim alert tanpa eksekusi virtual")
    
    args = parser.parse_args()
    monitor = MarketMonitor()

    if args.daemon:
        monitor.run_daemon(interval_seconds=args.interval)
    else:
        # Default run once
        monitor.run_cycle(force_refresh=False, auto_trade=not args.no_trade)
