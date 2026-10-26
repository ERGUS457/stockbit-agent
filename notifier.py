"""
Modul Notifikasi Telegram AI Trading Agent IDX (Fase 4)
Mengirimkan alert Support & Resistance serta laporan eksekusi portofolio secara instan ke Telegram.
"""

import os
import time
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from config import TICKER_CONGLOMERATE_MAP, USER_REAL_BUDGET

# Muat kredensial dari .env
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)

DEFAULT_CHAT_ID = "5123103700"

class TelegramNotifier:
    """
    Pengirim sinyal & laporan terformat ke bot Telegram pengguna.
    """
    def __init__(self, chat_id: str = DEFAULT_CHAT_ID):
        self.chat_id = chat_id
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

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else None
        self._sent_alerts_cache: Dict[str, float] = {}  # key -> timestamp
        self.cooldown_seconds = 14400  # 4 jam cooldown per alert identik

    def is_available(self) -> bool:
        return bool(self.bot_token and self.api_url)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Mengirim pesan teks ke Telegram menggunakan HTML."""
        if not self.is_available():
            print("[Notifier] Token bot Telegram tidak tersedia di .env")
            return False

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            res = requests.post(self.api_url, json=payload, timeout=10)
            if res.status_code == 200 and res.json().get("ok"):
                return True
            else:
                print(f"[Notifier] Respon Telegram: {res.status_code} - {res.text}")
                return False
        except Exception as e:
            print(f"[Notifier] Error mengirim pesan: {e}")
            return False

    def send_sr_alert(self, event, lots: Optional[int] = None, outlay: Optional[float] = None) -> bool:
        """
        Mengirimkan notifikasi event Support & Resistance (Bounce, Breakout, Rejection, Breakdown).
        Menerapkan filter cooldown agar tidak spamming.
        """
        # Cek cooldown alert identik
        cache_key = f"{event.ticker}_{event.event_type}"
        now = time.time()
        if cache_key in self._sent_alerts_cache:
            if now - self._sent_alerts_cache[cache_key] < self.cooldown_seconds:
                return False  # Masih dalam masa cooldown

        clean_ticker = event.ticker.replace(".JK", "")
        conglomerate_name = TICKER_CONGLOMERATE_MAP.get(event.ticker, "Konglomerat IDX")

        if event.event_type == "SUPPORT_BOUNCE":
            header = f"🟢 <b>[ALERT S/R: SUPPORT REBOUND]</b> — #{clean_ticker}"
            action_tag = "🚀 <b>POTENSI BUY / PANTULAN SEHAT</b>"
        elif event.event_type == "RESISTANCE_BREAKOUT":
            header = f"🔥 <b>[ALERT S/R: RESISTANCE BREAKOUT]</b> — #{clean_ticker}"
            action_tag = "⚡ <b>MOMENTUM BUY / PENEMBUSAN LEVEL</b>"
        elif event.event_type == "RESISTANCE_REJECTION":
            header = f"⚠️ <b>[ALERT S/R: RESISTANCE REJECTION]</b> — #{clean_ticker}"
            action_tag = "🛑 <b>WASPADA TEKANAN JUAL / AMBIL PROFIT</b>"
        elif event.event_type == "SUPPORT_BREAKDOWN":
            header = f"🚨 <b>[ALERT S/R: SUPPORT BREAKDOWN]</b> — #{clean_ticker}"
            action_tag = "🔻 <b>BAHAYA JEBOL / SIAPKAN CUT LOSS</b>"
        else:
            return False

        lines = [
            header,
            f"👑 <b>Konglomerat:</b> <code>{conglomerate_name}</code>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📊 <b>Status:</b> {action_tag}",
            f"💰 <b>Harga Terkini:</b> <code>Rp {event.current_price:,.0f}</code>",
            f"🛡️ <b>Level Support:</b> <code>Rp {event.support_level:,.0f}</code>",
            f"🎯 <b>Level Resistance:</b> <code>Rp {event.resistance_level:,.0f}</code>",
            f"⚖️ <b>Pivot Point:</b> <code>Rp {event.pivot_point:,.0f}</code>",
            f"📈 <b>Volume Ratio:</b> <code>{event.volume_ratio:.2f}x rata-rata</code>",
            f"📉 <b>RSI (14):</b> <code>{event.rsi:.1f}</code>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"📝 <b>Analisis:</b> {event.description}"
        ]

        if lots and outlay:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━",
                "💼 <b>Rekomendasi Simulasi (Rp 100jt):</b>",
                f"• Ukuran: <b>{lots} Lot</b> ({lots*100:,} lembar)",
                f"• Estimasi Modal: <code>Rp {outlay:,.0f}</code>"
            ])

        # Kalkulasi estimasi modal riil (Budget Gus <= Rp 500rb)
        cost_per_lot = event.current_price * 100 * (1 + 0.0015)
        if cost_per_lot <= USER_REAL_BUDGET:
            max_budget_lots = int(USER_REAL_BUDGET // cost_per_lot)
            rec_budget_lots = max(1, min(max_budget_lots, 5))
            rec_budget_outlay = rec_budget_lots * cost_per_lot
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━",
                "🪙 <b>Kalkulasi Modal Riil (Budget Rp 500rb):</b>",
                f"• Harga 1 Lot: <code>Rp {cost_per_lot:,.0f}</code> (RAMAH MODAL ✅)",
                f"• Muat Budget: <b>{max_budget_lots} Lot</b>",
                f"• Rekomendasi Riil: <b>{rec_budget_lots} Lot</b> (~<code>Rp {rec_budget_outlay:,.0f}</code>)"
            ])
        else:
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━",
                "🪙 <b>Kalkulasi Modal Riil (Budget Rp 500rb):</b>",
                f"• Harga 1 Lot: <code>Rp {cost_per_lot:,.0f}</code>",
                "• ⚠️ <i>Di atas budget Rp 500rb (Pantau untuk referensi)</i>"
            ])

        waktu = time.strftime('%d-%m-%Y %H:%M:%S WIB')
        lines.append(f"\n<i>Waktu Pemantauan: {waktu}</i>")

        msg = "\n".join(lines)
        success = self.send_message(msg)
        if success:
            self._sent_alerts_cache[cache_key] = now
        return success

    def send_order_alert(self, order_type: str, details: Dict[str, Any]) -> bool:
        """
        Mengirim notifikasi ketika ada posisi baru dibuka atau ditutup di Portofolio Virtual.
        """
        clean_ticker = details["ticker"].replace(".JK", "")
        conglomerate_name = TICKER_CONGLOMERATE_MAP.get(details["ticker"], "Konglomerat IDX")
        waktu = time.strftime('%d-%m-%Y %H:%M:%S WIB')

        if order_type == "BUY":
            cost_per_lot = details['entry_price'] * 100 * (1 + 0.0015)
            budget_lots = int(USER_REAL_BUDGET // cost_per_lot) if cost_per_lot <= USER_REAL_BUDGET else 0

            lines = [
                "📥 <b>[EKSEKUSI VIRTUAL STOCKBIT: BUY]</b>",
                f"👑 <b>Konglomerat:</b> <code>{conglomerate_name}</code>",
                "━━━━━━━━━━━━━━━━━━━━━━",
                f"Saham: <b>#{clean_ticker}</b>",
                f"Harga Beli: <code>Rp {details['entry_price']:,.0f}</code>",
                f"Simulasi (Rp 100jt): <b>{details['lots']} Lot</b> (<code>Rp {details['total_outlay']:,.0f}</code>)",
                f"Stop Loss (ATR): <code>Rp {details['stop_loss']:,.0f}</code>",
                f"Take Profit (1:2): <code>Rp {details['take_profit']:,.0f}</code>",
                f"Alasan: {details.get('entry_reason', '-')}",
                "━━━━━━━━━━━━━━━━━━━━━━",
                f"🪙 <b>Panduan Modal Riil (Budget Rp 500rb):</b>"
            ]

            if budget_lots > 0:
                rec_lots = max(1, min(budget_lots, 5))
                lines.extend([
                    f"• Harga 1 Lot: <code>Rp {cost_per_lot:,.0f}</code>",
                    f"• Beli Riil: <b>{rec_lots} Lot</b> (~<code>Rp {rec_lots*cost_per_lot:,.0f}</code>)"
                ])
            else:
                lines.append(f"• 1 Lot Rp {cost_per_lot:,.0f} (> Rp 500rb)")

            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━",
                "<i>Posisi otomatis tercatat di Portofolio Virtual Stockbit</i>",
                f"<i>Waktu: {waktu}</i>"
            ])
        elif order_type == "SELL":
            pnl_rp = details.get("pnl_rp", 0.0)
            pnl_pct = details.get("pnl_pct", 0.0)
            pnl_icon = "🟢" if pnl_rp >= 0 else "🔴"

            lines = [
                "📤 <b>[EKSEKUSI VIRTUAL STOCKBIT: SELL / EXIT]</b>",
                "━━━━━━━━━━━━━━━━━━━━━━",
                f"Saham: <b>#{clean_ticker}</b>",
                f"Harga Beli: <code>Rp {details['entry_price']:,.0f}</code>",
                f"Harga Jual: <code>Rp {details['exit_price']:,.0f}</code>",
                f"Jumlah: <b>{details['lots']} Lot</b>",
                f"{pnl_icon} <b>Net PnL:</b> <code>Rp {pnl_rp:,.0f}</code> (<b>{pnl_pct:+.2f}%</b>)",
                f"Total Fee: <code>Rp {(details.get('fee_buy',0)+details.get('fee_sell',0)):,.0f}</code>",
                f"Alasan Keluar: {details.get('exit_reason', '-')}",
                "━━━━━━━━━━━━━━━━━━━━━━",
                "<i>Kas hasil penjualan telah dikembalikan ke saldo virtual</i>",
                f"<i>Waktu: {waktu}</i>"
            ]
        else:
            return False

        return self.send_message("\n".join(lines))
