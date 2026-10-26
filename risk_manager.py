"""
Modul Manajemen Risiko & Kalkulasi Ukuran Posisi (Position Sizing)
"""

import math
from dataclasses import dataclass
from typing import Optional

from config import (
    INITIAL_CAPITAL,
    USER_REAL_BUDGET,
    MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_ALLOCATION,
    MAX_OPEN_POSITIONS,
    SHARES_PER_LOT,
    BUY_FEE_PCT,
    SELL_FEE_PCT
)

@dataclass
class PositionOrder:
    ticker: str
    action: str              # 'BUY' / 'SELL'
    price: float             # Harga beli / eksekusi
    shares: int              # Jumlah lembar saham
    lots: int                # Jumlah lot
    total_cost: float        # Total nilai transaksi sebelum fee
    fee: float               # Estimasi fee
    total_outlay: float      # Total pengeluaran (cost + fee)
    stop_loss: float
    take_profit: float
    risk_amount_rp: float    # Jumlah uang yang dirisikokan (Rp)
    risk_pct_portfolio: float


class RiskManager:
    """
    Mengontrol batas risiko modal, alokasi per emiten, dan ukuran lot.
    """
    def __init__(
        self,
        capital: float = INITIAL_CAPITAL,
        risk_per_trade: float = MAX_RISK_PER_TRADE,
        max_allocation: float = MAX_PORTFOLIO_ALLOCATION,
        max_positions: int = MAX_OPEN_POSITIONS
    ):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.max_allocation = max_allocation
        self.max_positions = max_positions

    def calculate_buy_order(
        self,
        ticker: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        current_cash: float,
        current_equity: float,
        active_positions_count: int
    ) -> Optional[PositionOrder]:
        """
        Menghitung apakah order beli boleh dieksekusi dan berapa lot yang tepat.
        """
        # Cek batasan jumlah posisi
        if active_positions_count >= self.max_positions:
            return None

        # Cek validitas harga
        if entry_price <= 0 or stop_loss >= entry_price or stop_loss <= 0:
            return None

        risk_per_share = entry_price - stop_loss
        max_risk_rp = current_equity * self.risk_per_trade

        # Hitung jumlah lembar saham berdasarkan batas risiko
        shares_by_risk = max_risk_rp / risk_per_share

        # Hitung batas maksimal alokasi modal per saham (misal 20% modal)
        max_capital_for_stock = min(current_equity * self.max_allocation, current_cash * 0.95)
        shares_by_allocation = max_capital_for_stock / entry_price

        # Ambil yang terkecil antara batas risiko dan batas modal
        shares_raw = min(shares_by_risk, shares_by_allocation)

        # Bulatkan ke bawah ke kelipatan lot (1 lot = 100 lembar)
        lots = math.floor(shares_raw / SHARES_PER_LOT)
        if lots < 1:
            return None  # Saldo/alokasi tidak mencukupi untuk beli minimal 1 lot

        shares = lots * SHARES_PER_LOT
        total_cost = shares * entry_price
        fee = total_cost * BUY_FEE_PCT
        total_outlay = total_cost + fee

        if total_outlay > current_cash:
            # Sesuaikan jika melebihi sisa cash riil
            lots = math.floor((current_cash / (1 + BUY_FEE_PCT)) / (entry_price * SHARES_PER_LOT))
            if lots < 1:
                return None
            shares = lots * SHARES_PER_LOT
            total_cost = shares * entry_price
            fee = total_cost * BUY_FEE_PCT
            total_outlay = total_cost + fee

        risk_amount_rp = shares * risk_per_share
        risk_pct = (risk_amount_rp / current_equity) * 100

        return PositionOrder(
            ticker=ticker,
            action="BUY",
            price=entry_price,
            shares=shares,
            lots=lots,
            total_cost=total_cost,
            fee=fee,
            total_outlay=total_outlay,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount_rp=risk_amount_rp,
            risk_pct_portfolio=round(risk_pct, 2)
        )

    def calculate_sell_order(
        self,
        ticker: str,
        sell_price: float,
        shares: int,
        entry_price: float
    ) -> dict:
        """
        Menghitung hasil penjualan posisi saham.
        """
        lots = shares // SHARES_PER_LOT
        gross_proceeds = shares * sell_price
        fee = gross_proceeds * SELL_FEE_PCT
        net_proceeds = gross_proceeds - fee

        cost_basis = shares * entry_price
        buy_fee = cost_basis * BUY_FEE_PCT
        total_investment = cost_basis + buy_fee

        pnl_rp = net_proceeds - total_investment
        pnl_pct = (pnl_rp / total_investment) * 100 if total_investment > 0 else 0.0

        return {
            "ticker": ticker,
            "lots": lots,
            "shares": shares,
            "sell_price": sell_price,
            "gross_proceeds": gross_proceeds,
            "sell_fee": fee,
            "net_proceeds": net_proceeds,
            "pnl_rp": pnl_rp,
            "pnl_pct": round(pnl_pct, 2),
            "is_win": pnl_rp > 0
        }

    def calculate_budget_order(
        self,
        ticker: str,
        entry_price: float,
        budget: float = USER_REAL_BUDGET
    ) -> dict:
        """
        Menghitung apakah saham terjangkau untuk modal riil pengguna (< Rp 500.000)
        dan berapa lot yang muat dibeli.
        """
        cost_per_lot = entry_price * SHARES_PER_LOT * (1 + BUY_FEE_PCT)
        affordable = cost_per_lot <= budget
        max_lots = math.floor(budget / cost_per_lot) if affordable else 0
        recommended_lots = max(1, min(max_lots, 10)) if affordable else 0
        recommended_outlay = recommended_lots * cost_per_lot if affordable else 0.0

        return {
            "ticker": ticker,
            "price_per_share": entry_price,
            "cost_per_lot": round(cost_per_lot, 0),
            "affordable": affordable,
            "max_lots": max_lots,
            "recommended_lots": recommended_lots,
            "recommended_outlay": round(recommended_outlay, 0),
            "budget": budget
        }
