"""
Modul Portofolio Virtual Stockbit & Eksekusi Simulasi IDX (Fase 3)
Menyimpan state akun ke portfolio.json dan mengelola siklus transaksi riil.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

from config import (
    INITIAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_ALLOCATION,
    MAX_OPEN_POSITIONS,
    SHARES_PER_LOT,
    BUY_FEE_PCT,
    SELL_FEE_PCT
)
from risk_manager import RiskManager

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")

class VirtualPortfolio:
    """
    Pengelola portofolio akun virtual Stockbit dengan kepatuhan aturan modal & transaksi BEI.
    """
    def __init__(self, filepath: str = PORTFOLIO_FILE):
        self.filepath = filepath
        self.risk_manager = RiskManager(capital=INITIAL_CAPITAL)
        self.data: Dict[str, Any] = self._load_or_initialize()

    def reset(self, initial_capital: float = INITIAL_CAPITAL):
        """Mereset seluruh portofolio ke saldo awal."""
        self.data = {
            "initial_capital": float(initial_capital),
            "cash_balance": float(initial_capital),
            "total_equity": float(initial_capital),
            "open_positions": {},
            "closed_trades": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save(self.data)
        return self.data

    def _load_or_initialize(self) -> Dict[str, Any]:
        """Memuat state portofolio dari Neon DB atau JSON, atau inisialisasi state baru."""
        # 1. Coba dari Neon PostgreSQL terlebih dahulu
        try:
            import db
            neon_data = db.load_portfolio_from_db()
            if neon_data and neon_data.get("summary"):
                summary = neon_data["summary"]
                return {
                    "initial_capital": summary["initial_capital"],
                    "cash_balance": summary["cash_balance"],
                    "total_equity": summary["total_equity"],
                    "open_positions": neon_data.get("positions", {}),
                    "closed_trades": neon_data.get("trade_history", []),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
        except Exception as e:
            print(f"[Portfolio] Neon DB bypass/error: {e}")

        # 2. Coba dari file JSON lokal
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Portfolio] Gagal membaca {self.filepath}, membuat ulang state baru: {e}")

        initial_state = {
            "initial_capital": INITIAL_CAPITAL,
            "cash_balance": INITIAL_CAPITAL,
            "total_equity": INITIAL_CAPITAL,
            "open_positions": {},  # ticker -> position dict
            "closed_trades": [],   # list of completed trade dicts
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save(initial_state)
        return initial_state

    def _save(self, state: Optional[Dict[str, Any]] = None):
        """Menyimpan state ke file JSON lokal dan Neon DB."""
        to_save = state or self.data
        to_save["updated_at"] = datetime.now().isoformat()
        
        # Simpan ke JSON lokal
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2, default=str)
        except Exception as e:
            print(f"[Portfolio] Gagal menulis {self.filepath}: {e}")

        # Simpan ke Neon DB Cloud
        try:
            import db
            cash = float(to_save["cash_balance"])
            positions = to_save.get("open_positions", {})
            market_val = sum(pos["shares"] * pos["current_price"] for pos in positions.values())
            tot_eq = cash + market_val
            closed = to_save.get("closed_trades", [])
            realized = sum(t.get("pnl_rp", 0.0) for t in closed)
            wins = len([t for t in closed if t.get("pnl_rp", 0.0) > 0])
            
            payload = {
                "summary": {
                    "initial_capital": to_save["initial_capital"],
                    "cash_balance": cash,
                    "total_equity": tot_eq,
                    "realized_pnl": realized,
                    "unrealized_pnl": sum(pos.get("floating_pnl_rp", 0.0) for pos in positions.values()),
                    "win_trades": wins,
                    "loss_trades": len(closed) - wins
                },
                "positions": positions,
                "trade_history": closed
            }
            db.save_portfolio_to_db(payload)
        except Exception as e:
            # Tetap jalan jika database offline
            pass

    def get_summary(self) -> Dict[str, Any]:
        """Mengembalikan metrik ringkasan portofolio saat ini."""
        cash = float(self.data["cash_balance"])
        positions = self.data.get("open_positions", {})
        
        market_value = 0.0
        floating_pnl_rp = 0.0
        
        for ticker, pos in positions.items():
            curr_val = pos["shares"] * pos["current_price"]
            market_value += curr_val
            floating_pnl_rp += pos.get("floating_pnl_rp", 0.0)

        total_equity = cash + market_value
        self.data["total_equity"] = round(total_equity, 2)
        
        closed = self.data.get("closed_trades", [])
        realized_pnl_rp = sum(t.get("pnl_rp", 0.0) for t in closed)
        wins = len([t for t in closed if t.get("pnl_rp", 0.0) > 0])
        win_rate = (wins / len(closed) * 100) if closed else 0.0

        return {
            "initial_capital": self.data["initial_capital"],
            "cash_balance": round(cash, 2),
            "market_value": round(market_value, 2),
            "total_equity": round(total_equity, 2),
            "floating_pnl_rp": round(floating_pnl_rp, 2),
            "realized_pnl_rp": round(realized_pnl_rp, 2),
            "total_closed_trades": len(closed),
            "winning_trades": wins,
            "win_rate_pct": round(win_rate, 2),
            "open_positions_count": len(positions),
            "open_positions": positions,
            "closed_trades": closed[-10:] # 10 terakhir
        }

    def execute_buy(
        self,
        ticker: str,
        price: float,
        stop_loss: float,
        take_profit: float,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Mengeksekusi order BUY virtual jika memenuhi seluruh kriteria risk management.
        """
        positions = self.data.setdefault("open_positions", {})
        if ticker in positions:
            return None  # Sudah memiliki posisi di saham ini

        if len(positions) >= MAX_OPEN_POSITIONS:
            return None  # Portofolio penuh (maksimal 5 saham)

        cash = float(self.data["cash_balance"])
        equity = float(self.data["total_equity"])

        order = self.risk_manager.calculate_buy_order(
            ticker=ticker,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_cash=cash,
            current_equity=equity,
            active_positions_count=len(positions)
        )

        if not order or order.total_outlay > cash or order.shares < SHARES_PER_LOT:
            return None

        # Potong saldo kas
        self.data["cash_balance"] = round(cash - order.total_outlay, 2)

        # Catat posisi baru
        positions[ticker] = {
            "ticker": ticker,
            "entry_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "entry_price": price,
            "current_price": price,
            "highest_price": price,
            "lots": order.lots,
            "shares": order.shares,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "fee_buy": order.fee,
            "total_outlay": order.total_outlay,
            "entry_reason": reason,
            "floating_pnl_rp": 0.0,
            "floating_pnl_pct": 0.0,
            "trailing_active": False
        }

        self._save()
        return positions[ticker]

    def execute_sell(
        self,
        ticker: str,
        price: float,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Mengeksekusi order SELL / Exit virtual dan membukukan PnL serta fee.
        """
        positions = self.data.get("open_positions", {})
        if ticker not in positions:
            return None

        pos = positions.pop(ticker)
        shares = pos["shares"]
        entry_price = pos["entry_price"]

        sell_calc = self.risk_manager.calculate_sell_order(
            ticker=ticker,
            sell_price=price,
            shares=shares,
            entry_price=entry_price
        )

        # Tambahkan kembali proceeds ke kas
        self.data["cash_balance"] = round(float(self.data["cash_balance"]) + sell_calc["net_proceeds"], 2)

        # Catat histori closed trade
        closed_record = {
            "ticker": ticker,
            "entry_date": pos["entry_date"],
            "exit_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "entry_price": entry_price,
            "exit_price": price,
            "lots": pos["lots"],
            "shares": shares,
            "pnl_rp": sell_calc["pnl_rp"],
            "pnl_pct": sell_calc["pnl_pct"],
            "fee_buy": pos.get("fee_buy", 0.0),
            "fee_sell": sell_calc["sell_fee"],
            "entry_reason": pos.get("entry_reason", ""),
            "exit_reason": reason
        }

        self.data.setdefault("closed_trades", []).append(closed_record)
        self._save()
        return closed_record

    def update_prices(self, price_map: Dict[str, float]) -> list[Dict[str, Any]]:
        """
        Memperbarui harga pasar posisi terbuka, floating PnL, dan mengecek trailing stop / take profit.
        Mengembalikan daftar event exit jika ada posisi yang terkena Stop Loss / Take Profit.
        """
        positions = self.data.get("open_positions", {})
        triggered_exits = []

        for ticker, pos in list(positions.items()):
            curr_p = price_map.get(ticker)
            if not curr_p:
                continue

            pos["current_price"] = curr_p
            if curr_p > pos.get("highest_price", pos["entry_price"]):
                pos["highest_price"] = curr_p

            shares = pos["shares"]
            entry_p = pos["entry_price"]
            
            # Hitung estimasi net PnL jika dijual saat ini
            sell_res = self.risk_manager.calculate_sell_order(
                ticker=ticker,
                sell_price=curr_p,
                shares=shares,
                entry_price=entry_p
            )
            pos["floating_pnl_rp"] = sell_res["pnl_rp"]
            pos["floating_pnl_pct"] = sell_res["pnl_pct"]

            # Cek Trailing Stop ke Breakeven (+0.5% untuk cover fee) jika profit sudah >= +3.5%
            if curr_p >= entry_p * 1.035 and not pos.get("trailing_active", False):
                pos["stop_loss"] = round(entry_p * 1.005, 2)
                pos["trailing_active"] = True

            # Cek Trigger Stop Loss
            if curr_p <= pos["stop_loss"]:
                exit_record = self.execute_sell(ticker, curr_p, reason=f"STOP LOSS HIT @ Rp {curr_p:,.0f} (Target SL: Rp {pos['stop_loss']:,.0f})")
                if exit_record:
                    triggered_exits.append(exit_record)
            # Cek Trigger Take Profit
            elif curr_p >= pos["take_profit"]:
                exit_record = self.execute_sell(ticker, curr_p, reason=f"TAKE PROFIT HIT @ Rp {curr_p:,.0f} (Target TP: Rp {pos['take_profit']:,.0f})")
                if exit_record:
                    triggered_exits.append(exit_record)

        self._save()
        return triggered_exits
