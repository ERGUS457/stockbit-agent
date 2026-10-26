"""
Web Dashboard & Server Lokal AI Trading Agent IDX (Stockbit Assistant)
Mencakup Fase 1, 2, 3, dan 4:
- Fase 1: Live Market Scanner & Yahoo Finance Data Feed
- Fase 2: Strategi Indikator Kuantitatif (EMA, RSI, MACD, ATR) & Backtesting
- Fase 3: Portofolio Virtual Trading Stockbit (Rp 100jt, Lot BEI, Trailing Stop)
- Fase 4: Deteksi Support & Resistance (Pivot, Rebound, Breakout) & Alert Telegram
"""

import os
import sys
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime

from config import (
    DEFAULT_WATCHLIST, INITIAL_CAPITAL, USER_REAL_BUDGET, MAX_RISK_PER_TRADE,
    MAX_PORTFOLIO_ALLOCATION, CONGLOMERATE_GROUPS, TICKER_CONGLOMERATE_MAP
)
from data_feed import IDXDataFeed
from indicators import calculate_all_indicators
from strategy import StrategyEngine
from risk_manager import RiskManager
from scanner import StockScanner
from backtester import BacktestEngine
from sr_detector import SRDetector
from portfolio import VirtualPortfolio
from notifier import TelegramNotifier
from monitor import MarketMonitor

app = Flask(__name__)

# Inisialisasi engine
feed = IDXDataFeed()
strategy = StrategyEngine()
risk_mgr = RiskManager()
scanner = StockScanner(watchlist=DEFAULT_WATCHLIST, data_feed=feed, strategy_engine=strategy, risk_manager=risk_mgr)
backtest_engine = BacktestEngine(initial_capital=INITIAL_CAPITAL, strategy_engine=strategy, risk_manager=risk_mgr)
sr_detector = SRDetector()
portfolio = VirtualPortfolio()
notifier = TelegramNotifier()
market_monitor = MarketMonitor(watchlist=DEFAULT_WATCHLIST)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trading Agent IDX | Stockbit Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Plus Jakarta Sans', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    },
                    colors: {
                        navy: {
                            800: '#0f172a',
                            900: '#090d16',
                            950: '#040711',
                        },
                        brand: {
                            blue: '#1d4ed8',
                            blueHover: '#1e40af',
                            gold: '#f59e0b',
                            goldLight: '#fef3c7',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0b1120; color: #f8fafc; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .glass-card {
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .glass-card:hover {
            border-color: rgba(245, 158, 11, 0.3);
        }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
    </style>
</head>
<body class="min-h-screen antialiased text-slate-100 flex flex-col justify-between">

    <!-- Top Navigation -->
    <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-4">
        <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="flex items-center space-x-3 w-full md:w-auto">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-700 to-amber-500 flex items-center justify-center shadow-lg shadow-blue-500/20 font-bold text-white text-lg">
                    AI
                </div>
                <div>
                    <div class="flex items-center space-x-2">
                        <h1 class="font-bold text-lg text-white tracking-tight">Stockbit Agent IDX</h1>
                        <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-semibold border border-amber-500/20">👑 Konglomerat Watch</span>
                        <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20">💰 Budget &lt; 500rb</span>
                    </div>
                    <p class="text-xs text-slate-400">Konglomerat & Saham Terjangkau (&lt; Rp 500.000 / Lot) • S/R Radar & Virtual Portfolio</p>
                </div>
            </div>

            <div class="flex items-center space-x-3 w-full md:w-auto justify-end">
                <div class="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span class="text-slate-300 font-medium">Bot Telegram: Terhubung</span>
                </div>
                <button onclick="triggerMonitorCycle()" id="btnAlert" class="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 font-semibold text-xs text-slate-950 transition flex items-center space-x-2 shadow-lg shadow-amber-500/20 active:scale-95">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                    <span>Cek S/R & Kirim Alert</span>
                </button>
                <button onclick="refreshAll()" id="btnScan" class="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 font-semibold text-xs text-white transition flex items-center space-x-2 shadow-lg shadow-blue-600/30 active:scale-95">
                    <svg id="scanIcon" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                    <span>Refresh Data</span>
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="max-w-7xl mx-auto w-full px-6 py-6 space-y-6 flex-1">
        
        <!-- Metrics Bar (Fase 3: Virtual Portfolio Overview) -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="glass-card rounded-2xl p-4 transition-all">
                <div class="text-slate-400 text-xs font-medium">Total Ekuitas Virtual</div>
                <div class="text-xl font-bold font-mono text-white mt-1" id="metricTotalEquity">Rp 100.000.000</div>
                <div class="text-[11px] text-emerald-400 font-medium mt-1" id="metricFloatingPnL">
                    Floating PnL: Rp 0 (+0.0%)
                </div>
            </div>

            <div class="glass-card rounded-2xl p-4 transition-all">
                <div class="text-slate-400 text-xs font-medium">Saldo Kas Tersedia</div>
                <div class="text-xl font-bold font-mono text-amber-400 mt-1" id="metricCash">Rp 100.000.000</div>
                <div class="text-[11px] text-slate-400 mt-1">Siap untuk alokasi baru</div>
            </div>

            <div class="glass-card rounded-2xl p-4 transition-all">
                <div class="text-slate-400 text-xs font-medium">Posisi Aktif Saham</div>
                <div class="text-xl font-bold font-mono text-white mt-1" id="metricOpenPositions">0 / 5 Saham</div>
                <div class="text-[11px] text-slate-400 mt-1">Maks. 20% per emiten</div>
            </div>

            <div class="glass-card rounded-2xl p-4 transition-all">
                <div class="text-slate-400 text-xs font-medium">S/R Radar & Budget Watch</div>
                <div class="text-xl font-bold font-mono text-emerald-400 mt-1" id="metricSRCount">30+ Emiten</div>
                <div class="text-[11px] text-emerald-400/80 mt-1 font-sans">Ramah Modal &lt; Rp 500rb/Lot</div>
            </div>
        </div>

        <!-- Section Navigation Tabs -->
        <div class="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <button onclick="switchTab('sr')" id="tabBtnSR" class="px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 text-white shadow-lg shadow-blue-600/20">
                🛡️ Radar Support & Resistance (Fase 4)
            </button>
            <button onclick="switchTab('portfolio')" id="tabBtnPortfolio" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white">
                💼 Portofolio Virtual Stockbit (Fase 3)
            </button>
            <button onclick="switchTab('scanner')" id="tabBtnScanner" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white">
                📡 Sinyal Kuantitatif (Fase 1-2)
            </button>
            <button onclick="switchTab('backtest')" id="tabBtnBacktest" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white">
                🧪 Backtesting Historis
            </button>
        </div>

        <!-- TAB 1: SUPPORT & RESISTANCE RADAR (FASE 4) -->
        <div id="tabContentSR" class="glass-card rounded-2xl p-6 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800/80 gap-3">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center space-x-2">
                        <span>🛡️ Radar Interaksi Support & Resistance Real-Time</span>
                    </h2>
                    <p class="text-xs text-slate-400 mt-0.5">Memantau Pivot Point harian, Rebound Support, Breakout Resistance, Rejection, dan Breakdown.</p>
                </div>
                <div class="text-xs font-mono text-amber-400" id="srTimestamp">Memuat level S/R...</div>
            </div>

            <!-- S/R Table -->
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="text-slate-400 border-b border-slate-800/80 uppercase text-[10px] tracking-wider">
                            <th class="py-3 px-3">Saham</th>
                            <th class="py-3 px-3">Harga Terkini</th>
                            <th class="py-3 px-3">Status S/R</th>
                            <th class="py-3 px-3">Support (S1 / S2)</th>
                            <th class="py-3 px-3">Pivot Point</th>
                            <th class="py-3 px-3">Resistance (R1 / R2)</th>
                            <th class="py-3 px-3">Volume & RSI</th>
                            <th class="py-3 px-3">Catatan Analisis</th>
                        </tr>
                    </thead>
                    <tbody id="srTableBody" class="divide-y divide-slate-800/60 font-mono">
                        <tr>
                            <td colspan="8" class="py-8 text-center text-slate-400">
                                <div class="inline-block animate-spin rounded-full h-6 w-6 border-2 border-amber-500 border-t-transparent mr-2"></div>
                                Mengkalkulasi Pivot Point dan mendeteksi interaksi Support & Resistance...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 2: PORTOFOLIO VIRTUAL STOCKBIT (FASE 3) -->
        <div id="tabContentPortfolio" class="hidden space-y-6">
            <!-- Active Positions Table -->
            <div class="glass-card rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800/80">
                    <div>
                        <h3 class="text-base font-bold text-white">📈 Posisi Aktif Portofolio Virtual Stockbit</h3>
                        <p class="text-xs text-slate-400 mt-0.5">Simulasi modal Rp 100jt, batas risiko 2%, fee beli 0.15% & fee jual 0.25%.</p>
                    </div>
                    <span class="text-xs font-mono text-slate-400">State: portfolio.json</span>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800/80 uppercase text-[10px] tracking-wider">
                                <th class="py-3 px-3">Saham</th>
                                <th class="py-3 px-3">Jumlah Lot</th>
                                <th class="py-3 px-3">Harga Beli</th>
                                <th class="py-3 px-3">Harga Terkini</th>
                                <th class="py-3 px-3">Nilai Pasar</th>
                                <th class="py-3 px-3">Stop Loss</th>
                                <th class="py-3 px-3">Take Profit</th>
                                <th class="py-3 px-3">Floating PnL</th>
                            </tr>
                        </thead>
                        <tbody id="portfolioTableBody" class="divide-y divide-slate-800/60 font-mono">
                            <tr>
                                <td colspan="8" class="py-6 text-center text-slate-500 font-sans">Belum ada posisi terbuka.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Closed Trades History -->
            <div class="glass-card rounded-2xl p-6 space-y-4">
                <h4 class="text-sm font-bold text-white">📜 Histori Transaksi Selesai (Closed Trades)</h4>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800/80 uppercase text-[10px] tracking-wider">
                                <th class="py-2 px-3">Saham</th>
                                <th class="py-2 px-3">Lot</th>
                                <th class="py-2 px-3">Beli / Jual</th>
                                <th class="py-2 px-3">Net PnL (Rp)</th>
                                <th class="py-2 px-3">Net PnL (%)</th>
                                <th class="py-2 px-3">Total Fee</th>
                                <th class="py-2 px-3">Alasan Keluar</th>
                            </tr>
                        </thead>
                        <tbody id="historyTableBody" class="divide-y divide-slate-800/60 font-mono">
                            <tr>
                                <td colspan="7" class="py-4 text-center text-slate-500 font-sans">Belum ada histori transaksi selesai.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 3: SCANNER SINYAL KUANTITATIF (FASE 1-2) -->
        <div id="tabContentScanner" class="hidden glass-card rounded-2xl p-6 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800/80 gap-3">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center space-x-2">
                        <span>📡 Hasil Scanning Sinyal Pasar Hari Ini</span>
                    </h2>
                    <p class="text-xs text-slate-400 mt-0.5" id="scanTimestamp">Memuat data terbaru...</p>
                </div>

                <div class="flex items-center space-x-1.5 p-1 rounded-xl bg-slate-800/80 border border-slate-700/60 text-xs">
                    <button onclick="filterSignals('ALL')" id="filterAll" class="px-3 py-1 rounded-lg font-medium bg-blue-600 text-white">Semua (<span id="countAll">0</span>)</button>
                    <button onclick="filterSignals('BUY')" id="filterBuy" class="px-3 py-1 rounded-lg font-medium text-slate-400 hover:text-white">Buy Setup (<span id="countBuy">0</span>)</button>
                    <button onclick="filterSignals('SELL')" id="filterSell" class="px-3 py-1 rounded-lg font-medium text-slate-400 hover:text-white">Sell Signal (<span id="countSell">0</span>)</button>
                    <button onclick="filterSignals('HOLD')" id="filterHold" class="px-3 py-1 rounded-lg font-medium text-slate-400 hover:text-white">Hold (<span id="countHold">0</span>)</button>
                </div>
            </div>

            <!-- Scanner Table -->
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="text-slate-400 border-b border-slate-800/80 uppercase text-[10px] tracking-wider">
                            <th class="py-3 px-3">Saham</th>
                            <th class="py-3 px-3">Harga Terkini</th>
                            <th class="py-3 px-3">Sinyal / Aksi</th>
                            <th class="py-3 px-3">Stop Loss</th>
                            <th class="py-3 px-3">Take Profit</th>
                            <th class="py-3 px-3">Rekomendasi</th>
                            <th class="py-3 px-3">Alasan Teknis</th>
                        </tr>
                    </thead>
                    <tbody id="scannerTableBody" class="divide-y divide-slate-800/60 font-mono">
                        <tr>
                            <td colspan="7" class="py-8 text-center text-slate-400">Memuat sinyal teknikal...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 4: BACKTESTING EXPLORER (FASE 2) -->
        <div id="tabContentBacktest" class="hidden grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Left: Backtest Control & Summary -->
            <div class="glass-card rounded-2xl p-6 flex flex-col justify-between">
                <div>
                    <h3 class="text-base font-bold text-white">🧪 Simulasi Historis (Backtest)</h3>
                    <p class="text-xs text-slate-400 mt-1">Uji strategi 1 tahun tanpa bias look-ahead.</p>

                    <div class="mt-4 space-y-3">
                        <label class="block text-xs text-slate-400 font-medium">Pilih Emiten untuk Backtest:</label>
                        <select id="selectTicker" onchange="runTickerBacktest()" class="w-full px-3 py-2 rounded-xl bg-slate-800/90 border border-slate-700 text-white text-xs focus:outline-none focus:border-blue-500 font-mono">
                            <option value="BUMI.JK">BUMI (Bumi Resources / Salim-Bakrie) - Rp 137/lbr (1 Lot: Rp 13.700)</option>
                            <option value="BRMS.JK">BRMS (Bumi Res Minerals / Salim-Bakrie) - Rp 426/lbr (1 Lot: Rp 42.600)</option>
                            <option value="MBMA.JK">MBMA (Merdeka Battery / Saratoga) - Rp 354/lbr (1 Lot: Rp 35.400)</option>
                            <option value="TOWR.JK">TOWR (Menara Nusantara / Djarum) - Rp 404/lbr (1 Lot: Rp 40.400)</option>
                            <option value="CUAN.JK">CUAN (Petrindo / Prajogo Pangestu) - Rp 482/lbr (1 Lot: Rp 48.200)</option>
                            <option value="BSDE.JK">BSDE (Bumi Serpong Damai / Sinar Mas) - Rp 496/lbr (1 Lot: Rp 49.600)</option>
                            <option value="GOTO.JK">GOTO (Gojek Tokopedia) - Rp 25/lbr (1 Lot: Rp 2.500)</option>
                            <option value="ELSA.JK">ELSA (Elnusa Energi) - Rp 640/lbr (1 Lot: Rp 64.000)</option>
                            <option value="ADMR.JK">ADMR (Adaro Minerals / Boy Thohir) - Rp 1.275/lbr (1 Lot: Rp 127.500)</option>
                            <option value="BRPT.JK">BRPT (Barito Pacific / Prajogo Pangestu) - Rp 1.420/lbr (1 Lot: Rp 142.000)</option>
                            <option value="SRTG.JK">SRTG (Saratoga Investama / Boy Thohir) - Rp 1.670/lbr (1 Lot: Rp 167.000)</option>
                            <option value="BREN.JK">BREN (Barito Renewables / Prajogo Pangestu) - Rp 2.320/lbr</option>
                            <option value="ADRO.JK">ADRO (Adaro Energy / Boy Thohir) - Rp 2.450/lbr</option>
                        </select>
                    </div>

                    <div class="mt-6 space-y-3" id="backtestMetrics">
                        <div class="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center">
                            <span class="text-xs text-slate-400">Total Transaksi</span>
                            <span class="font-bold text-sm text-white font-mono" id="btTrades">-</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center">
                            <span class="text-xs text-slate-400">Win Rate (%)</span>
                            <span class="font-bold text-sm text-emerald-400 font-mono" id="btWinRate">-</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center">
                            <span class="text-xs text-slate-400">Profit Factor</span>
                            <span class="font-bold text-sm text-amber-400 font-mono" id="btProfitFactor">-</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center">
                            <span class="text-xs text-slate-400">Net Profit / PnL</span>
                            <span class="font-bold text-sm font-mono" id="btNetProfit">-</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center">
                            <span class="text-xs text-slate-400">Max Drawdown</span>
                            <span class="font-bold text-sm text-rose-400 font-mono" id="btMaxDD">-</span>
                        </div>
                    </div>
                </div>

                <div class="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300/90 leading-relaxed">
                    💡 <strong>Prinsip Kuantitatif:</strong> Win Rate tidak harus 90%. Dengan Risk-Reward minimal 1:2, Win Rate 50% saja sudah melipatgandakan portofolio secara konsisten.
                </div>
            </div>

            <!-- Right: Interactive Equity Curve Chart -->
            <div class="lg:col-span-2 glass-card rounded-2xl p-6 flex flex-col justify-between">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <div>
                        <h4 class="text-sm font-bold text-white" id="chartTitle">Kurva Pertumbuhan Ekuitas (Equity Curve)</h4>
                        <p class="text-xs text-slate-400">Perkembangan saldo kas & nilai portofolio per transaksi.</p>
                    </div>
                    <span class="text-xs font-mono text-slate-400" id="chartTickerLabel">PTBA.JK</span>
                </div>

                <div class="relative w-full h-64 mt-4">
                    <canvas id="equityChart"></canvas>
                </div>

                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400 font-mono">
                    <span>Awal: Rp 100.000.000</span>
                    <span id="finalEquityLabel">Akhir: -</span>
                </div>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 bg-slate-900/60 py-4 px-6 mt-6">
        <div class="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
            <div>
                © 2026 AI Trading Agent IDX • Hermes Intelligent Trading Suite
            </div>
            <div class="flex items-center space-x-3">
                <span class="text-slate-400">Kompatibel dengan ekosistem Stockbit & Pasar Modal Indonesia (BEI)</span>
            </div>
        </div>
    </footer>

    <script>
        let allScanData = [];
        let allSRData = [];
        let currentFilter = 'ALL';
        let equityChartInstance = null;

        function switchTab(tabId) {
            ['sr', 'portfolio', 'scanner', 'backtest'].forEach(t => {
                const content = document.getElementById('tabContent' + t.charAt(0).toUpperCase() + t.slice(1));
                const btn = document.getElementById('tabBtn' + t.charAt(0).toUpperCase() + t.slice(1));
                if (t === tabId) {
                    content.classList.remove('hidden');
                    btn.className = 'px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 text-white shadow-lg shadow-blue-600/20';
                } else {
                    content.classList.add('hidden');
                    btn.className = 'px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white';
                }
            });
        }

        async function triggerMonitorCycle() {
            const btn = document.getElementById('btnAlert');
            const originalHTML = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="inline-block animate-spin mr-1">🔄</span> Memindai S/R & Mengirim Alert...`;

            try {
                const res = await fetch('/api/trigger-cycle', { method: 'POST' });
                const data = await res.json();
                alert(`✅ ${data.message}`);
                refreshAll();
            } catch (err) {
                alert(`Gagal menjalankan siklus: ${err.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalHTML;
            }
        }

        async function refreshAll() {
            await Promise.all([
                loadSRRadar(),
                loadPortfolioData(),
                triggerScan(false)
            ]);
        }

        async function loadSRRadar() {
            const tbody = document.getElementById('srTableBody');
            try {
                const res = await fetch('/api/sr-radar');
                const data = await res.json();
                allSRData = data.radar || [];
                document.getElementById('srTimestamp').innerText = 'Pembaruan: ' + data.timestamp;
                renderSRTable(allSRData);
            } catch (err) {
                tbody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-rose-400">Gagal memuat radar S/R: ${err.message}</td></tr>`;
            }
        }

        function renderSRTable(items) {
            const tbody = document.getElementById('srTableBody');
            if (!items || items.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-slate-500">Tidak ada data S/R.</td></tr>`;
                return;
            }

            let html = '';
            for (const item of items) {
                let badge = '';
                if (item.event === 'SUPPORT_BOUNCE') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">🟢 REBOUND</span>`;
                } else if (item.event === 'RESISTANCE_BREAKOUT') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/30">🔥 BREAKOUT</span>`;
                } else if (item.event === 'RESISTANCE_REJECTION') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">⚠️ REJECTION</span>`;
                } else if (item.event === 'SUPPORT_BREAKDOWN') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">🚨 BREAKDOWN</span>`;
                } else {
                    badge = `<span class="px-2 py-0.5 rounded text-[10px] text-slate-500 bg-slate-800/60">⚪ IN-RANGE</span>`;
                }

                html += `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-3 px-3">
                        <div class="font-bold text-white">${item.ticker.replace('.JK','')}</div>
                        <div class="text-[10px] text-amber-400 font-sans font-medium">${item.conglomerate || 'Konglomerat'}</div>
                        ${item.affordable ? 
                            `<span class="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold font-mono">1 Lot: Rp ${Math.round(item.cost_per_lot).toLocaleString('id-ID')} (${item.max_lots} Lot)</span>` : 
                            `<span class="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 font-mono">1 Lot: Rp ${Math.round(item.cost_per_lot).toLocaleString('id-ID')}</span>`
                        }
                    </td>
                    <td class="py-3 px-3 font-semibold text-slate-200">Rp ${Math.round(item.price).toLocaleString('id-ID')}</td>
                    <td class="py-3 px-3">${badge}</td>
                    <td class="py-3 px-3 text-emerald-400">Rp ${Math.round(item.s1).toLocaleString('id-ID')} / ${Math.round(item.s2).toLocaleString('id-ID')}</td>
                    <td class="py-3 px-3 text-amber-400 font-bold">Rp ${Math.round(item.pivot).toLocaleString('id-ID')}</td>
                    <td class="py-3 px-3 text-rose-400">Rp ${Math.round(item.r1).toLocaleString('id-ID')} / ${Math.round(item.r2).toLocaleString('id-ID')}</td>
                    <td class="py-3 px-3 text-slate-300">${item.volume_ratio.toFixed(2)}x | RSI ${item.rsi.toFixed(1)}</td>
                    <td class="py-3 px-3 text-slate-400 font-sans text-xs max-w-xs truncate" title="${item.description}">${item.description}</td>
                </tr>
                `;
            }
            tbody.innerHTML = html;
        }

        async function loadPortfolioData() {
            try {
                const res = await fetch('/api/portfolio');
                const data = await res.json();

                document.getElementById('metricTotalEquity').innerText = `Rp ${Math.round(data.total_equity).toLocaleString('id-ID')}`;
                document.getElementById('metricCash').innerText = `Rp ${Math.round(data.cash_balance).toLocaleString('id-ID')}`;
                document.getElementById('metricOpenPositions').innerText = `${data.open_positions.length} / 5 Saham`;

                const pnlEl = document.getElementById('metricFloatingPnL');
                const isProfit = data.total_floating_pnl_rp >= 0;
                pnlEl.innerText = `Floating PnL: Rp ${Math.round(data.total_floating_pnl_rp).toLocaleString('id-ID')} (${data.total_floating_pnl_pct.toFixed(2)}%)`;
                pnlEl.className = `text-[11px] font-medium mt-1 ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`;

                // Render Open Positions
                const pBody = document.getElementById('portfolioTableBody');
                if (data.open_positions.length === 0) {
                    pBody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-slate-500 font-sans">Belum ada posisi terbuka.</td></tr>`;
                } else {
                    let html = '';
                    for (const pos of data.open_positions) {
                        const isPosProfit = pos.floating_pnl_rp >= 0;
                        html += `
                        <tr class="hover:bg-slate-800/40 transition">
                            <td class="py-3 px-3 font-bold text-white">${pos.ticker.replace('.JK','')}</td>
                            <td class="py-3 px-3 text-amber-400 font-bold">${pos.lots} Lot</td>
                            <td class="py-3 px-3 text-slate-300">Rp ${Math.round(pos.entry_price).toLocaleString('id-ID')}</td>
                            <td class="py-3 px-3 text-slate-100 font-bold">Rp ${Math.round(pos.current_price).toLocaleString('id-ID')}</td>
                            <td class="py-3 px-3 text-slate-300">Rp ${Math.round(pos.market_val).toLocaleString('id-ID')}</td>
                            <td class="py-3 px-3 text-rose-400">Rp ${Math.round(pos.stop_loss).toLocaleString('id-ID')}</td>
                            <td class="py-3 px-3 text-emerald-400">Rp ${Math.round(pos.take_profit).toLocaleString('id-ID')}</td>
                            <td class="py-3 px-3 font-bold ${isPosProfit ? 'text-emerald-400' : 'text-rose-400'}">
                                Rp ${Math.round(pos.floating_pnl_rp).toLocaleString('id-ID')} (${pos.floating_pnl_pct.toFixed(2)}%)
                            </td>
                        </tr>
                        `;
                    }
                    pBody.innerHTML = html;
                }

                // Render Closed Trades
                const hBody = document.getElementById('historyTableBody');
                if (data.closed_trades.length === 0) {
                    hBody.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-slate-500 font-sans">Belum ada histori transaksi selesai.</td></tr>`;
                } else {
                    let hHtml = '';
                    for (const tr of data.closed_trades) {
                        const isWin = tr.net_pnl_rp >= 0;
                        hHtml += `
                        <tr class="hover:bg-slate-800/40 transition">
                            <td class="py-2.5 px-3 font-bold text-white">${tr.ticker.replace('.JK','')}</td>
                            <td class="py-2.5 px-3 text-slate-300">${tr.lots} Lot</td>
                            <td class="py-2.5 px-3 text-slate-400">Rp ${Math.round(tr.entry_price)} ➔ ${Math.round(tr.exit_price)}</td>
                            <td class="py-2.5 px-3 font-bold ${isWin ? 'text-emerald-400':'text-rose-400'}">Rp ${Math.round(tr.net_pnl_rp).toLocaleString('id-ID')}</td>
                            <td class="py-2.5 px-3 font-bold ${isWin ? 'text-emerald-400':'text-rose-400'}">${tr.net_pnl_pct.toFixed(2)}%</td>
                            <td class="py-2.5 px-3 text-slate-400">Rp ${Math.round(tr.total_fees).toLocaleString('id-ID')}</td>
                            <td class="py-2.5 px-3 text-slate-400 font-sans text-xs">${tr.exit_reason}</td>
                        </tr>
                        `;
                    }
                    hBody.innerHTML = hHtml;
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function triggerScan(force = false) {
            const btn = document.getElementById('btnScan');
            const icon = document.getElementById('scanIcon');
            const tbody = document.getElementById('scannerTableBody');
            
            btn.disabled = true;
            btn.classList.add('opacity-75');
            icon.classList.add('animate-spin');

            try {
                const res = await fetch(`/api/scan?refresh=${force ? '1' : '0'}`);
                const data = await res.json();
                allScanData = data.results || [];
                
                document.getElementById('scanTimestamp').innerText = 'Pembaruan Terakhir: ' + data.timestamp;
                updateCounts(allScanData);
                renderTable(allScanData);
            } catch (err) {
                console.error(err);
                tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-rose-400 font-sans">Gagal memuat data scanner: ${err.message}</td></tr>`;
            } finally {
                btn.disabled = false;
                btn.classList.remove('opacity-75');
                icon.classList.remove('animate-spin');
            }
        }

        function updateCounts(items) {
            document.getElementById('countAll').innerText = items.length;
            document.getElementById('countBuy').innerText = items.filter(x => x.action === 'BUY').length;
            document.getElementById('countSell').innerText = items.filter(x => x.action === 'SELL').length;
            document.getElementById('countHold').innerText = items.filter(x => x.action === 'HOLD').length;
        }

        function filterSignals(action) {
            currentFilter = action;
            ['ALL', 'BUY', 'SELL', 'HOLD'].forEach(tab => {
                const btn = document.getElementById('filter' + tab.charAt(0) + tab.slice(1).toLowerCase());
                if (tab === action) {
                    btn.className = 'px-3 py-1 rounded-lg font-medium bg-blue-600 text-white';
                } else {
                    btn.className = 'px-3 py-1 rounded-lg font-medium text-slate-400 hover:text-white';
                }
            });

            if (action === 'ALL') {
                renderTable(allScanData);
            } else {
                renderTable(allScanData.filter(x => x.action === action));
            }
        }

        function renderTable(items) {
            const tbody = document.getElementById('scannerTableBody');
            if (!items || items.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-500 font-sans">Tidak ada saham yang sesuai dengan filter sinyal ini.</td></tr>`;
                return;
            }

            let html = '';
            for (const item of items) {
                let badge = '';
                if (item.action === 'BUY') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">🟢 BUY SETUP</span>`;
                } else if (item.action === 'SELL') {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">🔴 EXIT / SELL</span>`;
                } else {
                    badge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700/60">⚪ HOLD / WAIT</span>`;
                }

                const sl = item.stop_loss ? `Rp ${Math.round(item.stop_loss).toLocaleString('id-ID')}` : '-';
                const tp = item.take_profit ? `Rp ${Math.round(item.take_profit).toLocaleString('id-ID')}` : '-';
                const lot = item.lots ? `<strong>${item.lots} Lot</strong><br><span class="text-[10px] text-slate-400">~Rp ${(item.lots * item.price * 100).toLocaleString('id-ID')}</span>` : '-';

                html += `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="py-3.5 px-3">
                        <div class="font-bold text-white text-sm">${item.ticker.replace('.JK', '')}</div>
                        <div class="text-[10px] text-amber-400 font-sans font-medium">${item.conglomerate || 'Konglomerat'}</div>
                        ${item.affordable ? 
                            `<span class="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold font-mono">1 Lot: Rp ${Math.round(item.cost_per_lot).toLocaleString('id-ID')} (${item.max_lots} Lot)</span>` : 
                            `<span class="inline-block mt-0.5 text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 font-mono">1 Lot: Rp ${Math.round(item.cost_per_lot).toLocaleString('id-ID')}</span>`
                        }
                    </td>
                    <td class="py-3.5 px-3 font-semibold text-slate-200">
                        Rp ${item.price ? Math.round(item.price).toLocaleString('id-ID') : '-'}
                    </td>
                    <td class="py-3.5 px-3">${badge}</td>
                    <td class="py-3.5 px-3 text-rose-400">${sl}</td>
                    <td class="py-3.5 px-3 text-emerald-400">${tp}</td>
                    <td class="py-3.5 px-3 text-amber-400">${lot}</td>
                    <td class="py-3.5 px-3 text-slate-400 font-sans text-xs max-w-xs truncate" title="${item.reason}">
                        ${item.reason}
                    </td>
                </tr>
                `;
            }
            tbody.innerHTML = html;
        }

        async function runTickerBacktest() {
            const ticker = document.getElementById('selectTicker').value;
            document.getElementById('chartTickerLabel').innerText = ticker;
            
            try {
                const res = await fetch(`/api/backtest?ticker=${ticker}`);
                const data = await res.json();

                document.getElementById('btTrades').innerText = `${data.total_trades} Transaksi`;
                document.getElementById('btWinRate').innerText = `${data.win_rate_pct.toFixed(1)}% (${data.winning_trades} Menang)`;
                document.getElementById('btProfitFactor').innerText = `${data.profit_factor.toFixed(2)}`;
                
                const pnlEl = document.getElementById('btNetProfit');
                const isProfit = data.net_profit_rp >= 0;
                pnlEl.innerText = `Rp ${Math.round(data.net_profit_rp).toLocaleString('id-ID')} (${data.net_profit_pct.toFixed(2)}%)`;
                pnlEl.className = `font-bold text-sm font-mono ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`;

                document.getElementById('btMaxDD').innerText = `${data.max_drawdown_pct.toFixed(2)}%`;
                document.getElementById('finalEquityLabel').innerText = `Akhir: Rp ${Math.round(data.final_equity).toLocaleString('id-ID')}`;

                renderEquityChart(data.equity_curve || []);
            } catch (err) {
                console.error(err);
            }
        }

        function renderEquityChart(curve) {
            const ctx = document.getElementById('equityChart').getContext('2d');
            
            if (equityChartInstance) {
                equityChartInstance.destroy();
            }

            const labels = curve.map((c, i) => i === 0 ? 'Start' : `Trade #${i}`);
            const dataValues = curve.map(c => c);

            const gradient = ctx.createLinearGradient(0, 0, 0, 240);
            gradient.addColorStop(0, 'rgba(37, 99, 235, 0.4)');
            gradient.addColorStop(1, 'rgba(37, 99, 235, 0.0)');

            equityChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Nilai Portofolio (Rp)',
                        data: dataValues,
                        borderColor: '#2563eb',
                        borderWidth: 2,
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#f59e0b',
                        pointBorderColor: '#ffffff',
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Rp ' + Math.round(context.raw).toLocaleString('id-ID');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: {
                                color: '#64748b',
                                font: { family: 'JetBrains Mono', size: 10 },
                                callback: function(val) {
                                    return 'Rp ' + (val / 1000000).toFixed(1) + 'M';
                                }
                            }
                        }
                    }
                }
            });
        }

        window.addEventListener('DOMContentLoaded', () => {
            refreshAll();
            runTickerBacktest();
        });
    </script>
</body>
</html>
"""

@app.route("/")
@app.route("/api/index")
def index():
    vpath = request.args.get("__vercel_path")
    if vpath:
        vpath = vpath.strip()
        if vpath in ("/api/sr-radar", "api/sr-radar"):
            return api_sr_radar()
        elif vpath in ("/api/portfolio", "api/portfolio"):
            return api_portfolio()
        elif vpath in ("/api/scan", "api/scan"):
            return api_scan()
        elif vpath in ("/api/backtest", "api/backtest"):
            return api_backtest()
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/sr-radar")
def api_sr_radar():
    force = request.args.get("force", "false").lower() == "true"
    if not force:
        try:
            import db
            cloud_radar = db.load_radar_from_db()
            if cloud_radar and len(cloud_radar) > 0:
                return jsonify({
                    "timestamp": datetime.now().strftime("%d %b %Y %H:%M WIB"),
                    "total": len(cloud_radar),
                    "radar": cloud_radar,
                    "source": "neon_cloud"
                })
        except Exception:
            pass

    radar_list = []
    for ticker in DEFAULT_WATCHLIST:
        try:
            df = feed.fetch_historical_data(ticker, period="1y", interval="1d")
            if df.empty or len(df) < 30:
                continue
            df_calc = calculate_all_indicators(df)
            levels = sr_detector.calculate_levels(df)
            event = sr_detector.detect_event(df_calc, ticker)
            cur_price = float(df["Close"].iloc[-1])
            cost_per_lot = round(cur_price * 100 * (1 + 0.0015), 0)
            affordable = cost_per_lot <= USER_REAL_BUDGET
            max_lots = int(USER_REAL_BUDGET // cost_per_lot) if affordable else 0
            
            radar_list.append({
                "ticker": ticker,
                "conglomerate": TICKER_CONGLOMERATE_MAP.get(ticker, "Konglomerat"),
                "price": cur_price,
                "cost_per_lot": cost_per_lot,
                "affordable": affordable,
                "max_lots": max_lots,
                "pivot": levels["pivot"],
                "r1": levels["r1"],
                "r2": levels["r2"],
                "s1": levels["s1"],
                "s2": levels["s2"],
                "event": event.event_type if event else "IN_RANGE",
                "description": event.description if event else "Harga bergerak dalam rentang normal.",
                "volume_ratio": event.volume_ratio if event else 1.0,
                "rsi": event.rsi if event else float(df_calc["RSI14"].iloc[-1])
            })
        except Exception:
            continue

    return jsonify({
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M WIB"),
        "total": len(radar_list),
        "radar": radar_list
    })

@app.route("/api/portfolio")
def api_portfolio():
    pf = VirtualPortfolio()
    summary = pf.get_summary()
    open_pos = summary.get("open_positions", {})
    detailed_positions = []
    total_market_val = 0.0

    for ticker, pos in open_pos.items():
        cur_price = pos.get("entry_price", 0.0)
        try:
            df = feed.fetch_historical_data(ticker, period="5d", interval="1d")
            if not df.empty:
                cur_price = float(df["Close"].iloc[-1])
        except Exception:
            pass

        val = pos["shares"] * cur_price
        cost = pos["shares"] * pos["entry_price"]
        floating_pnl_rp = val - cost
        floating_pnl_pct = (floating_pnl_rp / cost * 100) if cost > 0 else 0.0
        total_market_val += val

        detailed_positions.append({
            "ticker": ticker,
            "entry_date": pos.get("entry_date", "-"),
            "lots": pos.get("lots", 0),
            "shares": pos.get("shares", 0),
            "entry_price": pos.get("entry_price", 0.0),
            "current_price": cur_price,
            "stop_loss": pos.get("stop_loss", 0.0),
            "take_profit": pos.get("take_profit", 0.0),
            "market_val": val,
            "floating_pnl_rp": floating_pnl_rp,
            "floating_pnl_pct": floating_pnl_pct
        })

    total_equity = summary["cash_balance"] + total_market_val
    total_floating_pnl_rp = total_equity - summary["initial_capital"]
    total_floating_pnl_pct = (total_floating_pnl_rp / summary["initial_capital"] * 100)

    return jsonify({
        "initial_capital": summary["initial_capital"],
        "cash_balance": summary["cash_balance"],
        "total_equity": total_equity,
        "total_floating_pnl_rp": total_floating_pnl_rp,
        "total_floating_pnl_pct": total_floating_pnl_pct,
        "open_positions": detailed_positions,
        "closed_trades": summary.get("closed_trades", [])
    })

@app.route("/api/trigger-cycle", methods=["POST"])
def api_trigger_cycle():
    monitor = MarketMonitor()
    res = monitor.run_cycle(force_refresh=True, auto_trade=True)
    return jsonify({
        "success": True,
        "alerts_sent": res.get("alerts_sent", 0),
        "events_count": res.get("events_count", 0),
        "message": f"Siklus selesai: {res.get('events_count', 0)} event S/R dideteksi, {res.get('alerts_sent', 0)} alert dikirim ke Telegram Gus."
    })

@app.route("/api/scan")
def api_scan():
    force = request.args.get("refresh", "0") == "1"
    formatted_results = []
    
    for ticker in DEFAULT_WATCHLIST:
        try:
            df = feed.fetch_historical_data(ticker, period="1y", interval="1d", force_refresh=force)
            if df.empty or len(df) < 50:
                continue
            df_calc = calculate_all_indicators(df)
            sig = strategy.evaluate_bar(df_calc, ticker, idx=-1)
            
            lots = None
            if sig.action == "BUY" and sig.stop_loss and sig.take_profit:
                order = risk_mgr.calculate_buy_order(
                    ticker=ticker,
                    entry_price=sig.price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    current_cash=INITIAL_CAPITAL,
                    current_equity=INITIAL_CAPITAL,
                    active_positions_count=0
                )
                lots = order.lots if order else None
            
            cost_per_lot = round(sig.price * 100 * (1 + 0.0015), 0) if sig.price else 0
            affordable = cost_per_lot <= USER_REAL_BUDGET and cost_per_lot > 0
            max_lots = int(USER_REAL_BUDGET // cost_per_lot) if affordable else 0

            formatted_results.append({
                "ticker": ticker,
                "conglomerate": TICKER_CONGLOMERATE_MAP.get(ticker, "Konglomerat"),
                "price": sig.price,
                "cost_per_lot": cost_per_lot,
                "affordable": affordable,
                "max_lots": max_lots,
                "action": sig.action,
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit,
                "risk_reward": sig.risk_reward_ratio,
                "lots": lots,
                "reason": sig.reason,
                "timestamp": sig.timestamp.strftime("%Y-%m-%d %H:%M")
            })
        except Exception:
            continue
            
    return jsonify({
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M WIB"),
        "total": len(formatted_results),
        "results": formatted_results
    })

@app.route("/api/backtest")
def api_backtest():
    ticker = request.args.get("ticker", "PTBA.JK")
    df = feed.fetch_historical_data(ticker, period="1y", interval="1d")
    if df.empty:
        return jsonify({"error": "Data tidak ditemukan"}), 404
        
    res = backtest_engine.run_single(df, ticker)
    return jsonify({
        "ticker": res.ticker,
        "initial_capital": res.initial_capital,
        "final_equity": res.final_equity,
        "net_profit_rp": res.net_profit_rp,
        "net_profit_pct": res.net_profit_pct,
        "total_trades": res.total_trades,
        "winning_trades": res.winning_trades,
        "losing_trades": res.losing_trades,
        "win_rate_pct": res.win_rate_pct,
        "profit_factor": res.profit_factor,
        "max_drawdown_pct": res.max_drawdown_pct,
        "equity_curve": res.equity_curve
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 AI Trading Agent Web Dashboard berjalan di: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
