# 🤖 AI Trading Agent IDX (Stockbit Assistant)

Sistem agen cerdas kuantitatif untuk analisis, screening sinyal buy & sell presisi, manajemen risiko modal, dan backtesting portofolio saham Bursa Efek Indonesia (IDX / BEI).

---

## 🎯 Fitur Utama (Fase 1 & Fase 2)

### 1. Data Feed Engine (`data_feed.py`)
- Pengambilan data historis candlestick OHLCV real-time saham IDX (menggunakan format `.JK` Yahoo Finance v8 endpoint).
- Sistem caching lokal otomatis (`/cache`) dengan masa kedaluwarsa 12 jam untuk menghemat bandwidth dan mempercepat kalkulasi.
- Pembersihan data otomatis (handling missing values, split adjustments, zero volume).

### 2. Kalkulasi Indikator Kuantitatif (`indicators.py`)
- **Trend Filter**: Exponential Moving Average (EMA 20, EMA 50, EMA 200).
- **Momentum**: Relative Strength Index (RSI 14 Wilder's Smoothing) & MACD (12, 26, 9).
- **Volatilitas**: Average True Range (ATR 14).
- **Volume Flow**: Volume Moving Average (SMA 20) dan Volume Ratio.

### 3. Logika Algoritma Sinyal Buy & Sell Presisi (`strategy.py`)
- **Trend Pullback Setup**:
  - Konfirmasi tren naik: `Close > EMA50` dan `EMA20 >= EMA50`.
  - Pullback sehat: RSI berada di rentang 40 - 58 (bukan overbought).
  - Reversal konfirmasi: Rejection hijau di atas EMA20 + MACD membaik + Volume valid.
- **Breakout Momentum Setup**:
  - Penembusan harga tertinggi 20 hari (`Breakout 20-Day High`).
  - Lonjakan volume masif (`Volume >= 1.5x VOL_MA20`).
  - RSI momentum kuat (55 - 72).
- **Exit / Sell Logic**:
  - **Dynamic Stop Loss**: Berjarak 2x ATR (dibatasi maksimal 5% di bawah entry).
  - **Take Profit**: Risk to Reward Ratio minimal 1:2.
  - **Exit Overbought**: RSI >= 70 dengan bearish reversal candle.
  - **Trend Invalidation**: Breakdown di bawah EMA50.

### 4. Manajemen Risiko & Position Sizing (`risk_manager.py`)
- **Batas Risiko per Trade**: Maksimal 2% modal per transaksi (Rp 2.000.000 dari modal Rp 100 Juta).
- **Alokasi Emiten**: Maksimal 20% modal per saham (diversifikasi).
- **Kepatuhan Regulasi IDX**:
  - Otomatis menghitung dan membulatkan ke satuan **Lot** (1 Lot = 100 Lembar).
  - Menghitung estimasi fee beli (0.15%) dan fee jual + pajak (0.25%).

### 5. Mesin Backtesting Bar-by-Bar (`backtester.py`)
- Menjalankan simulasi perdagangan historis tanpa bias *look-ahead*.
- Evaluasi Stop Loss, Take Profit, dan Slippage handling.
- Metrik lengkap: Win Rate (%), Total Trades, Profit Factor, Net Profit (Rp & %), dan Max Drawdown (%).

### 6. Scanner & Notifikasi Telegram (`scanner.py` & `main.py`)
- Memindai saham LQ45 / Bluechip IDX secara otomatis.
- Menghasilkan format pesan Telegram yang siap dikirim via bot.

### 7. Cloud Serverless & Multi-User Architecture (Vercel + Neon DB)
- **Vercel Serverless Engine**: Web dashboard Flask interaktif yang aktif 24/7 dan dapat diakses bersama rekan-rekan via tautan publik Vercel tanpa perlu laptop menyala.
- **Neon PostgreSQL Cloud Persistence (`stockbit_db`)**: Menyimpan portofolio virtual, riwayat eksekusi perdagangan, dan snapshot Radar S/R secara terpusat dan aman.
- **GitHub Actions Scheduled Monitor**: Cron otomatis yang berjalan setiap 20 menit selama jam bursa IDX (Senin - Jumat 09:00 - 16:00 WIB) untuk memindai 32 saham konglomerat & ramah budget, melakukan virtual trading otomatis, dan mengirim sinyal instan ke Telegram.
- **Kalkulasi Modal Riil Pemula (Budget Rp 500rb)**: Setiap sinyal melampirkan biaya 1 lot riil dan kapasitas lot yang dapat dibeli dengan modal di bawah Rp 500.000.

---

## 🚀 Cara Menjalankan

### Menjalankan Unit Test Komprehensif
```bash
python3 test_engine.py && python3 test_phase3_4.py
```

### Menjalankan Dashboard Web Lokal
```bash
python3 app.py
# Buka di browser: http://localhost:5050
```

### Menjalankan Siklus Pemantauan Pasar & Sinkronisasi Cloud
```bash
python3 monitor.py --once
```
