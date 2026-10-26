"""
Konfigurasi Umum AI Trading Agent - IDX Stockbit Edition
"""

import os
from pathlib import Path

# Direktori Basis
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Parameter Akun & Trading (Sesuai Standar Akun Virtual Stockbit Rp 100.000.000 & Budget Riil Rp 500.000)
INITIAL_CAPITAL = 100_000_000.0  # Rp 100 Juta (Simulasi Virtual Stockbit)
USER_REAL_BUDGET = 500_000.0      # Rp 500 Ribu (Batas Keuangan Modal Riil Pengguna)
MAX_RISK_PER_TRADE = 0.02         # Maksimal 2% risiko modal per transaksi
MAX_PORTFOLIO_ALLOCATION = 0.20   # Maksimal 20% modal per saham (diversifikasi)
MAX_OPEN_POSITIONS = 5            # Maksimal 5 posisi aktif bersamaan

# Regulasi Saham Indonesia (IDX)
SHARES_PER_LOT = 100              # 1 Lot = 100 lembar saham
BUY_FEE_PCT = 0.0015              # Fee beli sekuritas rata-rata 0.15%
SELL_FEE_PCT = 0.0025             # Fee jual sekuritas + PPh final 0.25%

# Parameter Strategi Trend & Momentum
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 40                 # Ambang batas pullback pada trend naik
RSI_OVERBOUGHT = 70               # Ambang batas take profit / jenuh beli
VOLUME_FACTOR = 1.3               # Lonjakan volume >= 1.3x rata-rata 20 hari
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 2.0           # Stop loss berjarak 2x ATR dari entry
MIN_RISK_REWARD_RATIO = 2.0       # Minimal reward-to-risk ratio 1:2

# Mapping Konglomerat Indonesia & Emiten Afiliasi (Termasuk Saham Murah Ramah Modal < Rp 500rb)
CONGLOMERATE_GROUPS = {
    "Prajogo Pangestu (Barito Group)": ["BREN.JK", "BRPT.JK", "TPIA.JK", "CUAN.JK", "PTRO.JK"],
    "Keluarga Hartono (Djarum Group)": ["BBCA.JK", "TOWR.JK", "BELI.JK"],
    "Anthony Salim (Salim Group)": ["AMMN.JK", "ICBP.JK", "INDF.JK", "BRMS.JK", "BUMI.JK", "MEDC.JK"],
    "Boy Thohir & Saratoga (Adaro/MDKA)": ["ADRO.JK", "ADMR.JK", "MDKA.JK", "MBMA.JK", "SRTG.JK"],
    "Low Tuck Kwong (Bayan Group)": ["BYAN.JK"],
    "Sinar Mas Group (Keluarga Widjaja)": ["INKP.JK", "TKIM.JK", "BSDE.JK", "DMAS.JK"],
    "Bakrie Group (Energi)": ["ENRG.JK"],
    "Hary Tanoesoedibjo (MNC Group)": ["KPIG.JK"],
    "Tech & Ekosistem Likuid Murah": ["GOTO.JK", "BUKA.JK", "DOID.JK", "ELSA.JK"],
    "Astra International (Jardine/Astra)": ["ASII.JK", "UNTR.JK"]
}

TICKER_CONGLOMERATE_MAP = {}
for group_name, tickers in CONGLOMERATE_GROUPS.items():
    for t in tickers:
        TICKER_CONGLOMERATE_MAP[t] = group_name

# Watchlist Fokus Saham Konglomerat & Saham Murah Ramah Modal (< Rp 500.000 / Lot)
DEFAULT_WATCHLIST = [
    # Saham Super Murah (1 Lot < Rp 50.000)
    "GOTO.JK",  # ~Rp 25 -> 1 Lot = Rp 2.500
    "KPIG.JK",  # ~Rp 28 -> 1 Lot = Rp 2.800
    "BUKA.JK",  # ~Rp 102 -> 1 Lot = Rp 10.200
    "BUMI.JK",  # ~Rp 137 -> 1 Lot = Rp 13.700
    "DOID.JK",  # ~Rp 166 -> 1 Lot = Rp 16.600
    "DMAS.JK",  # ~Rp 210 -> 1 Lot = Rp 21.000
    "BELI.JK",  # ~Rp 266 -> 1 Lot = Rp 26.600
    "MBMA.JK",  # ~Rp 354 -> 1 Lot = Rp 35.400
    "TOWR.JK",  # ~Rp 404 -> 1 Lot = Rp 40.400
    "BRMS.JK",  # ~Rp 426 -> 1 Lot = Rp 42.600
    "CUAN.JK",  # ~Rp 482 -> 1 Lot = Rp 48.200
    "BSDE.JK",  # ~Rp 496 -> 1 Lot = Rp 49.600
    
    # Saham Terjangkau (1 Lot Rp 50.000 - Rp 300.000, Muat Budget Rp 500rb)
    "ELSA.JK",  # ~Rp 640 -> 1 Lot = Rp 64.000
    "ENRG.JK",  # ~Rp 820 -> 1 Lot = Rp 82.000
    "ADMR.JK",  # ~Rp 1.275 -> 1 Lot = Rp 127.500
    "BRPT.JK",  # ~Rp 1.420 -> 1 Lot = Rp 142.000
    "TPIA.JK",  # ~Rp 1.445 -> 1 Lot = Rp 144.500
    "MEDC.JK",  # ~Rp 1.450 -> 1 Lot = Rp 145.000
    "SRTG.JK",  # ~Rp 1.670 -> 1 Lot = Rp 167.000
    "MDKA.JK",  # ~Rp 2.060 -> 1 Lot = Rp 206.000
    "BREN.JK",  # ~Rp 2.320 -> 1 Lot = Rp 232.000
    "ADRO.JK",  # ~Rp 2.450 -> 1 Lot = Rp 245.000
    "PTRO.JK",  # ~Rp 3.050 -> 1 Lot = Rp 305.000
    "ASII.JK",  # ~Rp 4.560 -> 1 Lot = Rp 456.000
    "BBCA.JK",  # ~Rp 4.940 -> 1 Lot = Rp 494.000
    
    # Bluechip Referensi (1 Lot > Rp 500.000)
    "AMMN.JK",  # ~Rp 3.960
    "ICBP.JK",  # ~Rp 5.975
    "INDF.JK",  # ~Rp 6.675
    "INKP.JK",  # ~Rp 6.950
    "TKIM.JK",  # ~Rp 6.500
    "BYAN.JK",  # ~Rp 10.375
    "UNTR.JK"   # ~Rp 25.000
]
