"""
Modul Mesin Backtesting Transaksi Saham IDX
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np

from config import (
    INITIAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_ALLOCATION,
    MAX_OPEN_POSITIONS,
    SHARES_PER_LOT
)
from indicators import calculate_all_indicators
from strategy import StrategyEngine, TradeSignal
from risk_manager import RiskManager, PositionOrder

@dataclass
class TradeRecord:
    ticker: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    lots: int
    shares: int
    pnl_rp: float
    pnl_pct: float
    exit_reason: str
    holding_days: int


@dataclass
class BacktestResult:
    ticker: str
    initial_capital: float
    final_equity: float
    net_profit_rp: float
    net_profit_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    avg_trade_pnl_pct: float
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


class BacktestEngine:
    """
    Simulasi eksekusi strategi bar-by-bar pada data historis IDX.
    """
    def __init__(
        self,
        initial_capital: float = INITIAL_CAPITAL,
        risk_manager: Optional[RiskManager] = None,
        strategy_engine: Optional[StrategyEngine] = None
    ):
        self.initial_capital = initial_capital
        self.risk_manager = risk_manager or RiskManager(capital=initial_capital)
        self.strategy_engine = strategy_engine or StrategyEngine()

    def run_single(self, df_raw: pd.DataFrame, ticker: str) -> BacktestResult:
        """
        Menjalankan backtest untuk satu emiten saham.
        """
        if df_raw.empty or len(df_raw) < 55:
            return BacktestResult(
                ticker=ticker,
                initial_capital=self.initial_capital,
                final_equity=self.initial_capital,
                net_profit_rp=0.0,
                net_profit_pct=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                max_drawdown_pct=0.0,
                avg_trade_pnl_pct=0.0
            )

        df = calculate_all_indicators(df_raw)

        cash = self.initial_capital
        current_equity = cash
        peak_equity = cash
        max_drawdown_pct = 0.0

        open_position: Optional[PositionOrder] = None
        entry_date: Optional[datetime] = None
        trade_records: list[TradeRecord] = []
        equity_curve: list[float] = [round(self.initial_capital, 2)]

        # Loop bar-by-bar mulai dari bar ke-50 (setelah indikator stabil)
        for i in range(50, len(df)):
            curr_date = df.index[i]
            row = df.iloc[i]
            open_p = float(row["Open"])
            high_p = float(row["High"])
            low_p = float(row["Low"])
            close_p = float(row["Close"])

            # 1. Evaluasi jika ada posisi aktif
            if open_position is not None:
                pos = open_position
                closed = False
                exit_price = 0.0
                exit_reason = ""

                # Cek Stop Loss
                if low_p <= pos.stop_loss:
                    exit_price = min(pos.stop_loss, open_p)  # Gap down handling
                    exit_reason = "STOP_LOSS"
                    closed = True
                # Cek Take Profit
                elif high_p >= pos.take_profit:
                    exit_price = max(pos.take_profit, open_p) # Gap up handling
                    exit_reason = "TAKE_PROFIT"
                    closed = True
                else:
                    # Evaluasi sinyal exit dari strategi
                    sig = self.strategy_engine.evaluate_bar(df.iloc[:i+1], ticker, idx=-1)
                    if sig.action == "SELL":
                        exit_price = close_p
                        exit_reason = sig.reason
                        closed = True

                if closed:
                    sell_res = self.risk_manager.calculate_sell_order(
                        ticker=ticker,
                        sell_price=exit_price,
                        shares=pos.shares,
                        entry_price=pos.price
                    )
                    cash += sell_res["net_proceeds"]
                    holding_days = (curr_date - entry_date).days if entry_date else 0

                    trade_records.append(TradeRecord(
                        ticker=ticker,
                        entry_date=entry_date,
                        exit_date=curr_date,
                        entry_price=pos.price,
                        exit_price=exit_price,
                        lots=pos.lots,
                        shares=pos.shares,
                        pnl_rp=sell_res["pnl_rp"],
                        pnl_pct=sell_res["pnl_pct"],
                        exit_reason=exit_reason,
                        holding_days=holding_days
                    ))
                    open_position = None
                    entry_date = None
                    equity_curve.append(round(cash, 2))

            # 2. Hitung Equity saat ini & Drawdown
            pos_value = (open_position.shares * close_p) if open_position else 0.0
            current_equity = cash + pos_value

            if current_equity > peak_equity:
                peak_equity = current_equity
            dd = ((peak_equity - current_equity) / peak_equity) * 100 if peak_equity > 0 else 0.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

            # 3. Evaluasi Sinyal BUY jika belum ada posisi
            if open_position is None:
                # Subset data sampai bar saat ini agar tidak look-ahead bias
                sig = self.strategy_engine.evaluate_bar(df.iloc[:i+1], ticker, idx=-1)
                if sig.action == "BUY" and sig.stop_loss and sig.take_profit:
                    order = self.risk_manager.calculate_buy_order(
                        ticker=ticker,
                        entry_price=close_p,
                        stop_loss=sig.stop_loss,
                        take_profit=sig.take_profit,
                        current_cash=cash,
                        current_equity=current_equity,
                        active_positions_count=0
                    )
                    if order and order.total_outlay <= cash:
                        cash -= order.total_outlay
                        open_position = order
                        entry_date = curr_date

        # Tutup posisi terakhir di akhir periode jika masih terbuka (Mark to Market)
        if open_position is not None:
            last_date = df.index[-1]
            last_close = float(df.iloc[-1]["Close"])
            sell_res = self.risk_manager.calculate_sell_order(
                ticker=ticker,
                sell_price=last_close,
                shares=open_position.shares,
                entry_price=open_position.price
            )
            cash += sell_res["net_proceeds"]
            trade_records.append(TradeRecord(
                ticker=ticker,
                entry_date=entry_date,
                exit_date=last_date,
                entry_price=open_position.price,
                exit_price=last_close,
                lots=open_position.lots,
                shares=open_position.shares,
                pnl_rp=sell_res["pnl_rp"],
                pnl_pct=sell_res["pnl_pct"],
                exit_reason="END_OF_DATA",
                holding_days=(last_date - entry_date).days if entry_date else 0
            ))
            equity_curve.append(round(cash, 2))

        final_equity = cash
        net_profit_rp = final_equity - self.initial_capital
        net_profit_pct = (net_profit_rp / self.initial_capital) * 100

        total_trades = len(trade_records)
        wins = [t for t in trade_records if t.pnl_rp > 0]
        losses = [t for t in trade_records if t.pnl_rp <= 0]
        winning_trades = len(wins)
        losing_trades = len(losses)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl_rp for t in wins)
        gross_loss = abs(sum(t.pnl_rp for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        avg_pnl_pct = float(np.mean([t.pnl_pct for t in trade_records])) if trade_records else 0.0

        if len(equity_curve) == 1:
            equity_curve.append(round(final_equity, 2))

        return BacktestResult(
            ticker=ticker,
            initial_capital=self.initial_capital,
            final_equity=round(final_equity, 2),
            net_profit_rp=round(net_profit_rp, 2),
            net_profit_pct=round(net_profit_pct, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            avg_trade_pnl_pct=round(avg_pnl_pct, 2),
            trades=trade_records,
            equity_curve=equity_curve
        )
