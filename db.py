"""
Modul Database Adapter Neon PostgreSQL untuk Stockbit Agent
Mendukung persistensi Cloud Neon DB dengan fallback lokal JSON.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Konfigurasi Database URL dari Environment Variable atau file .env lokal
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        DATABASE_URL = line.split("DATABASE_URL=", 1)[1].strip("'\"")
                        break
        except Exception:
            pass

def get_connection():
    """Membuka koneksi ke Neon PostgreSQL."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Inisialisasi tabel di Neon PostgreSQL jika belum ada."""
    commands = [
        """
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id INT PRIMARY KEY DEFAULT 1,
            initial_capital NUMERIC(15,2) NOT NULL DEFAULT 100000000.00,
            cash_balance NUMERIC(15,2) NOT NULL DEFAULT 100000000.00,
            total_equity NUMERIC(15,2) NOT NULL DEFAULT 100000000.00,
            realized_pnl NUMERIC(15,2) NOT NULL DEFAULT 0.00,
            unrealized_pnl NUMERIC(15,2) NOT NULL DEFAULT 0.00,
            win_trades INT NOT NULL DEFAULT 0,
            loss_trades INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        INSERT INTO portfolio_state (id, initial_capital, cash_balance, total_equity)
        VALUES (1, 100000000.00, 100000000.00, 100000000.00)
        ON CONFLICT (id) DO NOTHING;
        """,
        """
        CREATE TABLE IF NOT EXISTS active_positions (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL UNIQUE,
            shares INT NOT NULL,
            lots INT NOT NULL,
            entry_price NUMERIC(15,2) NOT NULL,
            current_price NUMERIC(15,2) NOT NULL,
            stop_loss NUMERIC(15,2) NOT NULL,
            take_profit NUMERIC(15,2) NOT NULL,
            highest_price NUMERIC(15,2) NOT NULL,
            total_cost NUMERIC(15,2) NOT NULL,
            market_value NUMERIC(15,2) NOT NULL,
            unrealized_pnl NUMERIC(15,2) NOT NULL,
            pnl_pct NUMERIC(8,4) NOT NULL,
            entry_reason TEXT,
            entry_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS trades_history (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            lots INT NOT NULL,
            shares INT NOT NULL,
            buy_price NUMERIC(15,2) NOT NULL,
            sell_price NUMERIC(15,2) NOT NULL,
            net_pnl NUMERIC(15,2) NOT NULL,
            return_pct NUMERIC(8,4) NOT NULL,
            exit_reason TEXT,
            entry_date TIMESTAMP WITH TIME ZONE,
            exit_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS market_radar (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL UNIQUE,
            conglomerate VARCHAR(100) NOT NULL,
            price NUMERIC(15,2) NOT NULL,
            cost_per_lot NUMERIC(15,2) NOT NULL,
            affordable BOOLEAN NOT NULL DEFAULT FALSE,
            max_lots INT NOT NULL DEFAULT 0,
            pivot NUMERIC(15,2),
            r1 NUMERIC(15,2),
            r2 NUMERIC(15,2),
            s1 NUMERIC(15,2),
            s2 NUMERIC(15,2),
            event VARCHAR(50),
            description TEXT,
            volume_ratio NUMERIC(8,2),
            rsi NUMERIC(8,2),
            action_hint VARCHAR(20),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS market_scanner (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL UNIQUE,
            conglomerate VARCHAR(100) NOT NULL,
            price NUMERIC(15,2) NOT NULL,
            cost_per_lot NUMERIC(15,2) NOT NULL,
            affordable BOOLEAN NOT NULL DEFAULT FALSE,
            max_lots INT NOT NULL DEFAULT 0,
            action VARCHAR(20) NOT NULL,
            stop_loss NUMERIC(15,2),
            take_profit NUMERIC(15,2),
            lots INT,
            reason TEXT,
            rsi NUMERIC(8,2),
            macd NUMERIC(15,4),
            macd_signal NUMERIC(15,4),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for cmd in commands:
                cur.execute(cmd)
        conn.commit()
    logger.info("Database tables initialized successfully.")

def save_portfolio_to_db(portfolio_data: Dict[str, Any]):
    """Menyimpan data portofolio virtual ke database Neon."""
    summary = portfolio_data.get("summary", {})
    positions = portfolio_data.get("positions", {})
    trades = portfolio_data.get("trade_history", [])

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Update summary
            cur.execute("""
                UPDATE portfolio_state
                SET initial_capital = %(initial_capital)s,
                    cash_balance = %(cash_balance)s,
                    total_equity = %(total_equity)s,
                    realized_pnl = %(realized_pnl)s,
                    unrealized_pnl = %(unrealized_pnl)s,
                    win_trades = %(win_trades)s,
                    loss_trades = %(loss_trades)s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1;
            """, {
                "initial_capital": summary.get("initial_capital", 100_000_000.0),
                "cash_balance": summary.get("cash_balance", 100_000_000.0),
                "total_equity": summary.get("total_equity", 100_000_000.0),
                "realized_pnl": summary.get("realized_pnl", 0.0),
                "unrealized_pnl": summary.get("unrealized_pnl", 0.0),
                "win_trades": summary.get("win_trades", 0),
                "loss_trades": summary.get("loss_trades", 0),
            })

            # 2. Update active positions (Replace)
            cur.execute("DELETE FROM active_positions;")
            for ticker, pos in positions.items():
                cur.execute("""
                    INSERT INTO active_positions (
                        ticker, shares, lots, entry_price, current_price,
                        stop_loss, take_profit, highest_price, total_cost,
                        market_value, unrealized_pnl, pnl_pct, entry_reason
                    ) VALUES (
                        %(ticker)s, %(shares)s, %(lots)s, %(entry_price)s, %(current_price)s,
                        %(stop_loss)s, %(take_profit)s, %(highest_price)s, %(total_cost)s,
                        %(market_value)s, %(unrealized_pnl)s, %(pnl_pct)s, %(entry_reason)s
                    );
                """, {
                    "ticker": ticker,
                    "shares": pos.get("shares", 0),
                    "lots": pos.get("lots", 0),
                    "entry_price": pos.get("entry_price", 0.0),
                    "current_price": pos.get("current_price", 0.0),
                    "stop_loss": pos.get("stop_loss", 0.0),
                    "take_profit": pos.get("take_profit", 0.0),
                    "highest_price": pos.get("highest_price", 0.0),
                    "total_cost": pos.get("total_cost", 0.0),
                    "market_value": pos.get("market_value", 0.0),
                    "unrealized_pnl": pos.get("unrealized_pnl", 0.0),
                    "pnl_pct": pos.get("pnl_pct", 0.0),
                    "entry_reason": pos.get("entry_reason", "")
                })

            # 3. Update trades history
            cur.execute("DELETE FROM trades_history;")
            for trade in trades:
                cur.execute("""
                    INSERT INTO trades_history (
                        ticker, lots, shares, buy_price, sell_price,
                        net_pnl, return_pct, exit_reason
                    ) VALUES (
                        %(ticker)s, %(lots)s, %(shares)s, %(buy_price)s, %(sell_price)s,
                        %(net_pnl)s, %(return_pct)s, %(exit_reason)s
                    );
                """, trade)

        conn.commit()

def load_portfolio_from_db() -> Dict[str, Any]:
    """Memuat data portofolio dari Neon PostgreSQL."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM portfolio_state WHERE id = 1;")
            summary_row = cur.fetchone()
            
            cur.execute("SELECT * FROM active_positions;")
            pos_rows = cur.fetchall()

            cur.execute("SELECT * FROM trades_history ORDER BY id DESC LIMIT 50;")
            trade_rows = cur.fetchall()

    if not summary_row:
        return {}

    summary = {
        "initial_capital": float(summary_row["initial_capital"]),
        "cash_balance": float(summary_row["cash_balance"]),
        "total_equity": float(summary_row["total_equity"]),
        "realized_pnl": float(summary_row["realized_pnl"]),
        "unrealized_pnl": float(summary_row["unrealized_pnl"]),
        "win_trades": int(summary_row["win_trades"]),
        "loss_trades": int(summary_row["loss_trades"]),
        "total_trades": int(summary_row["win_trades"] + summary_row["loss_trades"]),
        "win_rate_pct": round(
            (summary_row["win_trades"] / (summary_row["win_trades"] + summary_row["loss_trades"]) * 100)
            if (summary_row["win_trades"] + summary_row["loss_trades"]) > 0 else 0.0, 1
        )
    }

    positions = {}
    for r in pos_rows:
        positions[r["ticker"]] = {
            "ticker": r["ticker"],
            "shares": int(r["shares"]),
            "lots": int(r["lots"]),
            "entry_price": float(r["entry_price"]),
            "current_price": float(r["current_price"]),
            "stop_loss": float(r["stop_loss"]),
            "take_profit": float(r["take_profit"]),
            "highest_price": float(r["highest_price"]),
            "total_cost": float(r["total_cost"]),
            "market_value": float(r["market_value"]),
            "unrealized_pnl": float(r["unrealized_pnl"]),
            "pnl_pct": float(r["pnl_pct"]),
            "entry_reason": r["entry_reason"] or ""
        }

    trades = []
    for t in trade_rows:
        trades.append({
            "ticker": t["ticker"],
            "lots": int(t["lots"]),
            "shares": int(t["shares"]),
            "buy_price": float(t["buy_price"]),
            "sell_price": float(t["sell_price"]),
            "net_pnl": float(t["net_pnl"]),
            "return_pct": float(t["return_pct"]),
            "exit_reason": t["exit_reason"] or ""
        })

    return {
        "summary": summary,
        "positions": positions,
        "trade_history": trades
    }

def save_radar_to_db(radar_list: List[Dict[str, Any]]):
    """Menyimpan snapshot Radar S/R ke Neon DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in radar_list:
                cur.execute("""
                    INSERT INTO market_radar (
                        ticker, conglomerate, price, cost_per_lot, affordable, max_lots,
                        pivot, r1, r2, s1, s2, event, description, volume_ratio, rsi, updated_at
                    ) VALUES (
                        %(ticker)s, %(conglomerate)s, %(price)s, %(cost_per_lot)s, %(affordable)s, %(max_lots)s,
                        %(pivot)s, %(r1)s, %(r2)s, %(s1)s, %(s2)s, %(event)s, %(description)s, %(volume_ratio)s, %(rsi)s, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (ticker) DO UPDATE SET
                        conglomerate = EXCLUDED.conglomerate,
                        price = EXCLUDED.price,
                        cost_per_lot = EXCLUDED.cost_per_lot,
                        affordable = EXCLUDED.affordable,
                        max_lots = EXCLUDED.max_lots,
                        pivot = EXCLUDED.pivot,
                        r1 = EXCLUDED.r1,
                        r2 = EXCLUDED.r2,
                        s1 = EXCLUDED.s1,
                        s2 = EXCLUDED.s2,
                        event = EXCLUDED.event,
                        description = EXCLUDED.description,
                        volume_ratio = EXCLUDED.volume_ratio,
                        rsi = EXCLUDED.rsi,
                        updated_at = CURRENT_TIMESTAMP;
                """, item)
        conn.commit()

def load_radar_from_db() -> List[Dict[str, Any]]:
    """Memuat snapshot Radar S/R dari Neon DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ticker, conglomerate, price, cost_per_lot, affordable, max_lots,
                       pivot, r1, r2, s1, s2, event, description, volume_ratio, rsi, updated_at
                FROM market_radar
                ORDER BY affordable DESC, ticker ASC;
            """)
            rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "ticker": r["ticker"],
            "conglomerate": r["conglomerate"],
            "price": float(r["price"]),
            "cost_per_lot": float(r["cost_per_lot"]),
            "affordable": bool(r["affordable"]),
            "max_lots": int(r["max_lots"]),
            "pivot": float(r["pivot"]) if r["pivot"] is not None else 0.0,
            "r1": float(r["r1"]) if r["r1"] is not None else 0.0,
            "r2": float(r["r2"]) if r["r2"] is not None else 0.0,
            "s1": float(r["s1"]) if r["s1"] is not None else 0.0,
            "s2": float(r["s2"]) if r["s2"] is not None else 0.0,
            "event": r["event"] or "IN_RANGE",
            "description": r["description"] or "",
            "volume_ratio": float(r["volume_ratio"]) if r["volume_ratio"] is not None else 1.0,
            "rsi": float(r["rsi"]) if r["rsi"] is not None else 50.0,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S WIB") if r["updated_at"] else ""
        })
    return results

def save_scanner_to_db(scan_list: List[Dict[str, Any]]):
    """Menyimpan snapshot Scanner ke Neon DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in scan_list:
                cur.execute("""
                    INSERT INTO market_scanner (
                        ticker, conglomerate, price, cost_per_lot, affordable, max_lots,
                        action, stop_loss, take_profit, lots, reason, rsi, macd, macd_signal, updated_at
                    ) VALUES (
                        %(ticker)s, %(conglomerate)s, %(price)s, %(cost_per_lot)s, %(affordable)s, %(max_lots)s,
                        %(action)s, %(stop_loss)s, %(take_profit)s, %(lots)s, %(reason)s, %(rsi)s, %(macd)s, %(macd_signal)s, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (ticker) DO UPDATE SET
                        conglomerate = EXCLUDED.conglomerate,
                        price = EXCLUDED.price,
                        cost_per_lot = EXCLUDED.cost_per_lot,
                        affordable = EXCLUDED.affordable,
                        max_lots = EXCLUDED.max_lots,
                        action = EXCLUDED.action,
                        stop_loss = EXCLUDED.stop_loss,
                        take_profit = EXCLUDED.take_profit,
                        lots = EXCLUDED.lots,
                        reason = EXCLUDED.reason,
                        rsi = EXCLUDED.rsi,
                        macd = EXCLUDED.macd,
                        macd_signal = EXCLUDED.macd_signal,
                        updated_at = CURRENT_TIMESTAMP;
                """, item)
        conn.commit()

def load_scanner_from_db() -> List[Dict[str, Any]]:
    """Memuat snapshot Scanner dari Neon DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ticker, conglomerate, price, cost_per_lot, affordable, max_lots,
                       action, stop_loss, take_profit, lots, reason, rsi, macd, macd_signal, updated_at
                FROM market_scanner
                ORDER BY affordable DESC, ticker ASC;
            """)
            rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "ticker": r["ticker"],
            "conglomerate": r["conglomerate"],
            "price": float(r["price"]),
            "cost_per_lot": float(r["cost_per_lot"]),
            "affordable": bool(r["affordable"]),
            "max_lots": int(r["max_lots"]),
            "action": r["action"],
            "stop_loss": float(r["stop_loss"]) if r["stop_loss"] is not None else None,
            "take_profit": float(r["take_profit"]) if r["take_profit"] is not None else None,
            "lots": int(r["lots"]) if r["lots"] is not None else None,
            "reason": r["reason"] or "",
            "rsi": float(r["rsi"]) if r["rsi"] is not None else None,
            "macd": float(r["macd"]) if r["macd"] is not None else None,
            "macd_signal": float(r["macd_signal"]) if r["macd_signal"] is not None else None,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S WIB") if r["updated_at"] else ""
        })
    return results
