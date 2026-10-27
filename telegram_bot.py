"""
Modul Bot Telegram Interaktif Dua Arah untuk AI Trading Agent IDX
Mendukung perintah interaktif:
  /start, /help - Bantuan & panduan
  /cek <TICKER> - Analisis teknikal, ADX, CMF Bandarmologi & rekomendasi emiten
  /porto        - Portofolio virtual modal Rp 100jt & posisi terbuka
  /radar        - Ringkasan Radar Support & Resistance
  /pemula       - Kurasi saham ramah modal pemula (< Rp 500rb / transaksi)
  /sinyal       - Sinyal buy/sell terkonfirmasi terkini
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import (
    DEFAULT_WATCHLIST,
    TICKER_CONGLOMERATE_MAP,
    USER_REAL_BUDGET,
    SHARES_PER_LOT
)
from data_feed import IDXDataFeed
from indicators import calculate_all_indicators
from strategy import StrategyEngine
from sr_detector import SRDetector
from db import load_portfolio_from_db, load_radar_from_db, load_scanner_from_db

class InteractiveTelegramBot:
    def __init__(self):
        self.feed = IDXDataFeed()
        self.strategy = StrategyEngine()
        self.sr_detector = SRDetector()
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
        if not self.bot_token:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                                self.bot_token = line.strip().split("=", 1)[1].strip("'\"")
                                break
                except Exception:
                    pass

    def handle_command(self, text: str) -> str:
        """Memproses teks perintah dan mengembalikan balasan berformat HTML."""
        text = text.strip()
        parts = text.split()
        if not parts:
            return self.cmd_help()

        cmd = parts[0].lower()
        # Handle format /command@BotName
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd in ["/start", "/help", "help", "bantuan"]:
            return self.cmd_help()
        elif cmd in ["/cek", "/analisis", "/check"]:
            ticker = parts[1] if len(parts) > 1 else "BBCA"
            return self.cmd_cek(ticker)
        elif cmd in ["/porto", "/portfolio", "/portofolio"]:
            return self.cmd_porto()
        elif cmd in ["/radar", "/sr"]:
            return self.cmd_radar()
        elif cmd in ["/pemula", "/budget", "/murah"]:
            return self.cmd_pemula()
        elif cmd in ["/sinyal", "/signal", "/scan"]:
            return self.cmd_sinyal()
        else:
            return f"⚠️ Perintah <code>{cmd}</code> tidak dikenali.\nKetik /help untuk melihat daftar perintah."

    def cmd_help(self) -> str:
        return (
            "🤖 <b>AI TRADING AGENT IDX • STOCKBIT BOT</b>\n\n"
            "Gunakan perintah berikut untuk memantau pasar:\n"
            "• <code>/cek &lt;TICKER&gt;</code> - Analisis teknikal, ADX & Bandarmologi (contoh: <code>/cek BBCA</code>, <code>/cek BSDE</code>)\n"
            "• <code>/porto</code> - Status portofolio virtual Rp 100jt & posisi terbuka\n"
            "• <code>/radar</code> - Snapshot Radar Support & Resistance bursa\n"
            "• <code>/pemula</code> - Saham likuid ramah budget &lt; Rp 500.000\n"
            "• <code>/sinyal</code> - Sinyal trading Buy & Sell terbaru\n\n"
            "🌐 <b>Live Web Dashboard:</b>\n"
            "https://stockbit-agent.vercel.app"
        )

    def cmd_cek(self, ticker: str) -> str:
        ticker = ticker.upper().strip()
        if not ticker.endswith(".JK"):
            ticker = f"{ticker}.JK"

        try:
            df = self.feed.fetch_historical_data(ticker, period="6mo", interval="1d")
            if df.empty or len(df) < 30:
                return f"❌ Data saham <b>{ticker}</b> tidak ditemukan di bursa IDX."

            df_ind = calculate_all_indicators(df)
            sig = self.strategy.evaluate_bar(df_ind, ticker, idx=-1)
            sr = self.sr_detector.detect_event(df, ticker)

            last_row = df_ind.iloc[-1]
            close = float(last_row["Close"])
            rsi = float(last_row.get("RSI14", 50.0))
            adx = float(last_row.get("ADX14", 25.0))
            cmf = float(last_row.get("CMF20", 0.0))
            vol_ratio = float(last_row.get("VOL_RATIO", 1.0))

            conglom = TICKER_CONGLOMERATE_MAP.get(ticker, "Umum / Regular")
            cost_per_lot = close * SHARES_PER_LOT
            max_lots_pemula = int(USER_REAL_BUDGET // cost_per_lot) if cost_per_lot > 0 else 0

            # Badge Sinyal
            if sig.action == "BUY":
                action_badge = "🟢 <b>REKOMENDASI: BUY / ENTRY</b>"
            elif sig.action == "SELL":
                action_badge = "🔴 <b>REKOMENDASI: SELL / EXIT</b>"
            else:
                action_badge = "⚪ <b>REKOMENDASI: WAIT & SEE (HOLD)</b>"

            # Badge Bandarmologi
            if cmf >= 0.08:
                flow_badge = "🟢 Akumulasi Masif (Inflow Kuat)"
            elif cmf > 0.02:
                flow_badge = "🟢 Akumulasi Ringan"
            elif cmf <= -0.08:
                flow_badge = "🔴 Distribusi Besar (Outflow)"
            else:
                flow_badge = "⚪ Netral"

            # Badge Regime ADX
            if adx >= 25:
                regime_badge = f"Trending Kuat (ADX {adx:.1f})"
            else:
                regime_badge = f"Sideways / Konsolidasi (ADX {adx:.1f})"

            lines = [
                f"📊 <b>ANALISIS EMITEN: {ticker}</b>",
                f"🏢 Grup: <i>{conglom}</i>",
                f"💵 Harga Terakhir: <b>Rp {close:,.0f}</b>",
                f"🏷 1 Lot (100 lbr): <b>Rp {cost_per_lot:,.0f}</b>\n",
                f"<b>Indikator Kuantitatif:</b>",
                f"• RSI (14): <code>{rsi:.1f}</code>",
                f"• Vol Ratio: <code>{vol_ratio:.1f}x rerata</code>",
                f"• Trend Regime: <code>{regime_badge}</code>",
                f"• Bandarmologi Proxy (CMF): <code>{flow_badge} ({cmf:.3f})</code>\n",
                f"<b>Radar Support & Resistance:</b>",
                f"• Support Terdekat: <code>Rp {sr.support_level:,.0f}</code>",
                f"• Resistance Terdekat: <code>Rp {sr.resistance_level:,.0f}</code>",
                f"• Pivot: <code>Rp {sr.pivot_point:,.0f}</code>",
                f"• Event: <b>{sr.event_type}</b>\n",
                action_badge,
                f"📝 <i>{sig.reason}</i>"
            ]

            if sig.stop_loss and sig.take_profit:
                tp1 = sig.take_profit_tp1 or sig.take_profit
                tp2 = sig.take_profit_tp2 or sig.take_profit
                lines.append(f"\n🎯 <b>Level Eksekusi:</b>")
                lines.append(f"• Stop Loss: <code>Rp {sig.stop_loss:,.0f}</code>")
                lines.append(f"• Target TP1: <code>Rp {tp1:,.0f}</code> (1:1.5 RR)")
                lines.append(f"• Target TP2: <code>Rp {tp2:,.0f}</code> (1:2.5 RR)")

            lines.append(f"\n💡 <b>Kalkulasi Modal Riil Pemula (&lt; Rp 500rb):</b>")
            if max_lots_pemula > 0:
                outlay = max_lots_pemula * cost_per_lot
                lines.append(f"• Bisa beli <b>{max_lots_pemula} lot</b> (~Rp {outlay:,.0f})")
            else:
                lines.append(f"• Harga 1 lot (Rp {cost_per_lot:,.0f}) melebihi budget Rp 500.000")

            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Terjadi kesalahan analisis untuk {ticker}: {str(e)}"

    def cmd_porto(self) -> str:
        try:
            porto = load_portfolio_from_db()
            summary = porto.get("summary", {})
            cash = summary.get("cash_balance", 0.0)
            equity = summary.get("total_equity", 0.0)
            pos_dict = porto.get("positions", {})
            positions = list(pos_dict.values()) if isinstance(pos_dict, dict) else pos_dict

            lines = [
                "💼 <b>STATUS PORTOFOLIO VIRTUAL STOCKBIT</b>",
                f"💰 Sisa Kas: <b>Rp {cash:,.0f}</b>",
                f"📈 Total Ekuitas: <b>Rp {equity:,.0f}</b>",
                f"📊 Posisi Terbuka: <b>{len(positions)} / 5 saham</b>\n"
            ]

            if not positions:
                lines.append("<i>Belum ada posisi saham aktif yang terbuka.</i>")
            else:
                lines.append("<b>Daftar Saham Aktif:</b>")
                for p in positions:
                    ticker = p.get("ticker", "-")
                    lots = p.get("lots", 0)
                    entry = p.get("entry_price", 0.0)
                    curr = p.get("current_price", entry)
                    pnl_rp = p.get("unrealized_pnl", 0.0)
                    pnl_pct = p.get("pnl_pct", 0.0)
                    sl = p.get("stop_loss", 0.0)
                    tp = p.get("take_profit", 0.0)

                    icon = "🟢" if pnl_rp >= 0 else "🔴"
                    lines.append(
                        f"• <b>{ticker}</b>: {lots} lot @ Rp {entry:,.0f}\n"
                        f"  Harga: Rp {curr:,.0f} | {icon} <b>{pnl_pct:+.2f}%</b> (Rp {pnl_rp:+,.0f})\n"
                        f"  SL: <code>Rp {sl:,.0f}</code> | TP: <code>Rp {tp:,.0f}</code>"
                    )

            lines.append("\n🌐 Dashboard: https://stockbit-agent.vercel.app")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal membaca data portofolio dari Neon DB: {str(e)}"

    def cmd_radar(self) -> str:
        try:
            snapshot = load_radar_from_db()
            if not snapshot:
                return "ℹ️ Belum ada snapshot S/R Radar tersimpan di database. Sistem akan memperbarui saat runner berikutnya."

            breakouts = [s for s in snapshot if "BREAKOUT" in s.get("event", "").upper()]
            bounces = [s for s in snapshot if "BOUNCE" in s.get("event", "").upper()]
            in_ranges = [s for s in snapshot if s.get("event") == "IN_RANGE"]

            lines = [
                "📡 <b>SNAPSHOT RADAR SUPPORT & RESISTANCE</b>",
                f"⏱ Total Pantau: <b>{len(snapshot)} emiten</b>",
                f"🚀 Breakout: <b>{len(breakouts)}</b> | 🎯 Bounce: <b>{len(bounces)}</b> | ⚖️ In Range: <b>{len(in_ranges)}</b>\n",
                "<b>Emiten Paling Menarik:</b>"
            ]

            highlights = (breakouts + bounces)
            if not highlights:
                highlights = snapshot[:6]
            else:
                highlights = highlights[:6]

            for h in highlights:
                tick = h.get("ticker", "-")
                ev = h.get("event", "-")
                pr = h.get("price", 0.0)
                desc = h.get("description", "")
                lines.append(f"• <b>{tick}</b> @ Rp {pr:,.0f} ➔ <code>{ev}</code>\n  <i>{desc}</i>")

            lines.append("\n🌐 Radar Lengkap: https://stockbit-agent.vercel.app")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal membaca radar snapshot: {str(e)}"

    def cmd_pemula(self) -> str:
        try:
            snapshot = load_radar_from_db()
            cheap_list = []
            for s in snapshot:
                pr = s.get("price", 0.0)
                cost_lot = s.get("cost_per_lot", pr * SHARES_PER_LOT)
                if 0 < cost_lot <= USER_REAL_BUDGET:
                    cheap_list.append({
                        "ticker": s.get("ticker"),
                        "price": pr,
                        "cost_lot": cost_lot,
                        "max_lots": s.get("max_lots", int(USER_REAL_BUDGET // cost_lot)),
                        "event": s.get("event")
                    })

            # Urutkan berdasarkan harga termurah
            cheap_list.sort(key=lambda x: x["cost_lot"])

            lines = [
                "💡 <b>KURASI SAHAM RAMAH MODAL PEMULA</b>",
                f"💵 Batas Modal Transaksi: <b>&lt; Rp {USER_REAL_BUDGET:,.0f}</b>\n"
            ]

            if not cheap_list:
                lines.append("<i>Belum ada data saham murah yang tersimpan di radar.</i>")
            else:
                for c in cheap_list[:8]:
                    lines.append(
                        f"• <b>{c['ticker']}</b> @ Rp {c['price']:,.0f} (Rp {c['cost_lot']:,.0f}/lot)\n"
                        f"  Dapat: <b>{c['max_lots']} lot</b> | S/R: <code>{c['event']}</code>"
                    )

            lines.append("\n🛡 <i>Tetap gunakan batasan risiko dan Stop Loss disiplin.</i>")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal memuat kurasi pemula: {str(e)}"

    def cmd_sinyal(self) -> str:
        try:
            signals = load_scanner_from_db()
            buys = [s for s in signals if s.get("action") == "BUY"]
            sells = [s for s in signals if s.get("action") == "SELL"]

            lines = [
                "⚡ <b>SINYAL TRADING IDX (SCANNER AKTIF)</b>\n"
            ]

            if not buys and not sells:
                lines.append("⚪ <i>Belum ada sinyal BUY / SELL baru yang terkonfirmasi hari ini. Pasar cenderung sideways/wait & see.</i>")
            else:
                if buys:
                    lines.append(f"🟢 <b>Rekomendasi BUY ({len(buys)} Saham):</b>")
                    for b in buys[:5]:
                        tick = b.get("ticker", "-")
                        pr = b.get("price", 0.0)
                        sl = b.get("stop_loss", 0.0)
                        tp = b.get("take_profit", 0.0)
                        rsn = b.get("reason", "")
                        lines.append(
                            f"• <b>{tick}</b> @ Rp {pr:,.0f}\n"
                            f"  SL: <code>Rp {sl:,.0f}</code> | TP: <code>Rp {tp:,.0f}</code>\n"
                            f"  <i>{rsn}</i>"
                        )
                if sells:
                    lines.append(f"\n🔴 <b>Rekomendasi SELL ({len(sells)} Saham):</b>")
                    for s in sells[:3]:
                        tick = s.get("ticker", "-")
                        pr = s.get("price", 0.0)
                        rsn = s.get("reason", "")
                        lines.append(f"• <b>{tick}</b> @ Rp {pr:,.0f} — <i>{rsn}</i>")

            lines.append("\n🌐 Live Dashboard: https://stockbit-agent.vercel.app")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal memuat sinyal: {str(e)}"

    def run_polling(self):
        """Menjalankan bot dalam mode long-polling sederhana."""
        if not self.bot_token:
            print("❌ TELEGRAM_BOT_TOKEN belum diset di environment / .env")
            return

        print(f"🤖 Bot Telegram Stockbit Agent aktif dalam mode polling...")
        offset = None
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?timeout=20"
                if offset:
                    url += f"&offset={offset}"
                res = requests.get(url, timeout=25).json()

                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")

                    if text and chat_id:
                        print(f"📩 Menerima pesan dari {chat_id}: {text}")
                        reply = self.handle_command(text)
                        send_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                        requests.post(send_url, json={
                            "chat_id": chat_id,
                            "text": reply,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True
                        }, timeout=10)

                time.sleep(1)
            except KeyboardInterrupt:
                print("🛑 Polling dihentikan pengguna.")
                break
            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(3)


if __name__ == "__main__":
    bot = InteractiveTelegramBot()
    if len(sys.argv) > 1:
        cmd_arg = " ".join(sys.argv[1:])
        print(f"--- Eksekusi Perintah: {cmd_arg} ---")
        out = bot.handle_command(cmd_arg)
        print(out)
    else:
        print("Penggunaan CLI:\n  python telegram_bot.py '/cek BBCA'\n  python telegram_bot.py --poll")
