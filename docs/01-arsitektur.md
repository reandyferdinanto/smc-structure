# 01 — Arsitektur Sistem

## 1. Diagram Komponen

```
┌──────────────────────────────────────────────────────────────────────┐
│                        SUMBER DATA EKSTERNAL                          │
│  gold-api  Binance(PAXG)  Yahoo(GC=F)  TradingView  ForexFactory     │
│  FRED      GDELT          Google News  CFTC COT                      │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP (requests, timeout 10s, retry 3x backoff)
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     DATA LAYER (src/data)                             │
│  adapter per sumber → normalizer → cache (parquet/sqlite)             │
│  output: DataFrame OHLCV[ts_utc, o,h,l,c,v] + SpotQuote               │
└───────────────┬──────────────────────────────────────────────────────┘
                │
      ┌─────────┴──────────┐
      ▼                    ▼
┌───────────────┐   ┌─────────────────────────┐
│ STRATEGY      │   │ MACRO & NEWS ENGINE     │
│ engine.py     │   │ calendar + fred + news  │
│ BB → swing →  │   │ → bias score (-100..100)│
│ liquidity →   │   │ → blackout window       │
│ CHoCH → FVG   │   │ → daily digest          │
│ → ALERT EVENT │   └──────────┬──────────────┘
└───────┬───────┘              │
        │  SignalEvent          │ BiasReport
        ▼                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DECISION GATE (src/strategy/engine)               │
│  sinyal hanya lolos jika:                                            │
│   ✓ bias makro tidak bertentangan (atau bias netral)                 │
│   ✓ tidak dalam blackout window high-impact news                     │
│   ✓ dalam killzone London/NY                                         │
│   ✓ RR >= 1.5 dan SL/TP valid                                        │
│   ✓ cooldown & dedupe lolos                                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ALERT LAYER (src/alerts)                          │
│  template pesan → Telegram Bot API → chat Anda                       │
│  (opsional) relay Cloudflare Worker untuk webhook TradingView        │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Dua Jalur Trigger (Hybrid)

Sistem mendukung **dua sumber sinyal** yang memakai logika identik:

| Jalur | Kapan dipakai | Cara kerja |
|---|---|---|
| **A. Python engine** | Fase 1–3, development, backtest | Loop tiap 60 detik, cek candle close, hitung ulang sinyal |
| **B. Pine Script** | Fase 4+, produksi utama | TradingView menghitung di server, kirim webhook JSON |

Keduanya harus menghasilkan **payload JSON identik** (lihat `04-pine-script.md §5`) sehingga
layer Telegram dan makro tidak peduli sinyal berasal dari mana.

## 3. Struktur Repo

```
xauusd-alerts/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── config/
│   ├── settings.yaml           # parameter strategi & sistem
│   └── symbols.yaml            # mapping simbol per sumber
├── src/
│   ├── main.py                 # entrypoint loop utama
│   ├── scheduler.py            # alignment ke close candle
│   ├── data/
│   │   ├── base.py             # interface DataAdapter
│   │   ├── gold_api.py         # spot price
│   │   ├── binance_paxg.py     # OHLCV intraday
│   │   ├── yahoo_gc.py         # OHLCV histori
│   │   ├── tv_scanner.py       # quote OANDA:XAUUSD
│   │   ├── cache.py            # parquet + sqlite meta
│   │   └── normalizer.py       # schema seragam + QC
│   ├── strategy/
│   │   ├── bollinger.py        # BB, %B, BandWidth, squeeze
│   │   ├── swings.py           # pivot fractal (major k=5, internal k=2)
│   │   ├── liquidity.py        # equal highs/lows, sweep
│   │   ├── structure.py        # BOS / CHoCH / iCHoCH / MBOS
│   │   ├── orderblock.py       # OB + fresh/mitigated state
│   │   ├── fvg.py              # FVG + partial fill tracking
│   │   ├── ote.py              # optimal trade entry
│   │   ├── regime.py           # rule-based regime (+ HMM opsional fase 6)
│   │   ├── orb.py              # Setup B: session opening range
│   │   ├── engine.py           # state machine + filter stack 12 poin
│   │   └── types.py            # dataclass SignalEvent, SetupState
│   ├── ml/                     # opsional, fase 7 — bukan generator sinyal
│   │   ├── features.py         # feature engineering (grup fitur di 02 §10.4)
│   │   └── regime_hmm.py       # HMM 3-state, refit bulanan
│   ├── macro/
│   │   ├── calendar.py         # FF JSON
│   │   ├── fred.py             # real yield, DXY
│   │   ├── news.py             # GDELT + Google News RSS
│   │   ├── bias.py             # skoring -100..+100
│   │   └── digest.py           # pesan harian
│   ├── alerts/
│   │   ├── telegram.py         # client + retry
│   │   ├── templates.py        # format HTML (entry/watchlist/update)
│   │   ├── tracker.py          # lifecycle sinyal: OPEN → TP1/SL/EXPIRED
│   │   └── dedupe.py           # sqlite anti-duplikat
│   ├── backtest/
│   │   ├── loader.py           # Dukascopy / HistData
│   │   ├── runner.py           # event-driven
│   │   └── metrics.py
│   └── utils/
│       ├── log.py              # JSON logs
│       ├── time.py             # UTC helpers, WIB display
│       └── health.py           # heartbeat
├── pine/
│   ├── xau_bb_smc_indicator.pine
│   └── xau_bb_smc_strategy.pine
├── scripts/
│   ├── fetch_history.py
│   ├── run_backtest.py
│   └── send_test_alert.py
├── tests/
│   ├── test_bollinger.py
│   ├── test_structure.py
│   ├── test_fvg.py
│   └── test_engine_state.py
└── deploy/
    ├── systemd/xauusd-alerts.service
    ├── cloudflare-worker/wrangler.toml
    └── cloudflare-worker/src/index.js
```

## 4. Tech Stack

| Layer | Pilihan | Alasan |
|---|---|---|
| Runtime | Python 3.12 | library data & HTTP matang |
| Data | pandas + numpy | standar de facto |
| HTTP | httpx (async) atau requests | timeout & retry mudah |
| Storage | Parquet (harga) + SQLite (state, dedupe, jurnal) | ringan, tak perlu DB server |
| Config | YAML + pydantic-settings | validasi env vars saat boot |
| Scheduler | loop internal (`asyncio.sleep` ke candle close) + systemd timer | lebih presisi dari cron |
| Logging | structlog/logging JSON ke stdout | mudah di-grep systemd |
| Notifikasi | python-telegram-bot **atau** HTTP langsung ke `api.telegram.org` | HTTP langsung cukup, tanpa dependency berat |
| Backtest | pandas + engine yang sama (replay) | menghindari "backtest beda dengan live" |
| Pine | Pine Script v6 | fitur terbaru, `alert()` JSON |

> **Keputusan penting:** modul strategi **tidak boleh** tahu apa-apa soal Telegram atau HTTP.
> Input: DataFrame. Output: `SignalEvent | None`. Ini yang membuat backtest dan live memakai
> kode yang sama.
>
> **Jalur upgrade (fase 6–7):** jika engine sendiri mulai terbatas (butuh multi-instrument,
> order book, atau eksekusi MT5), migrasikan `strategy/*` ke
> **NautilusTrader** — modul strategi sudah terpisah sehingga hanya adapter yang berubah.
> Jangan migrasi sebelum backtest + paper trading stabil.

## 5. Alur Eksekusi (Satu Siklus)

```
setiap 60 detik:
  1. tentukan candle terakhir yang CLOSED untuk TF M15 (dan H1/H4 jika ganti bar)
  2. jika candle baru: refresh data (cached, incremental)
  3. QC data: gap? harga anomali? spot vs PAXG basis > 1%?
  4. update state engine (IDLE/ARMED/TRIGGERED/ALERTED)
  5. jika state == TRIGGERED:
        a. macro bias = refresh (cache 30 menit)
        b. blackout? (event high-impact ±30 menit) → tunda/suppress
        c. killzone? (UTC 07-10 / 12-15) → jika tidak, tandai "out-of-session"
        d. RR >= 1.5?
        e. dedupe: hash(symbol,side,tf,candle_ts) belum pernah dikirim?
        f. kirim Telegram + simpan ke sqlite
  6. setiap 15 menit: heartbeat file
  7. 07:00 WIB: kirim digest makro harian
```

## 6. Environment Variables (`.env`)

```dotenv
# --- Telegram ---
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ALLOWED_CHAT_IDS=123456789

# --- Data ---
DATA_PRIMARY=paxg                 # paxg | gc_futures
BASIS_ALERT_PCT=1.0               # selisih spot vs PAXG yang dianggap anomali

# --- Makro ---
FRED_API_KEY=                     # opsional; tanpa key pakai yfinance DXY
NEWS_LOOKBACK_HOURS=12

# --- Relay webhook (TradingView → Worker) ---
RELAY_SHARED_SECRET=random-32-char
RELAY_URL=https://xau-relay.<subdomain>.workers.dev

# --- Sistem ---
TZ=UTC
LOG_LEVEL=INFO
CONFIG_PATH=config/settings.yaml
DRY_RUN=true                      # true = alert hanya ke log, tidak kirim
```

## 7. `config/settings.yaml` (cuplikan)

```yaml
strategy:
  bb_length: 20
  bb_mult: 2.0
  squeeze_lookback: 100
  squeeze_percentile: 25
  atr_length: 14
  displacement_atr_mult: 1.2
  fvg_min_atr_mult: 0.15
  sweep_atr_mult: 0.05
  equal_level_atr_mult: 0.10
  ote_min: 0.62
  ote_max: 0.786
  min_rr: 1.5
  max_signals_per_day: 3
  cooldown_bars: 16            # 16 × M15 = 4 jam
  pivot_k_major: 5
  pivot_k_internal: 2
  ob_require_fresh: true
  fvg_max_fill_pct: 0.5        # zona > 50% terisi = confidence -10
  setup_a_enabled: true
  setup_b_enabled: true

regime:
  method: rule                # rule | hmm | both
  adx_trend_threshold: 25
  atr_rank_volatile: 80
  bbw_rank_volatile: 70
  ema_length: 50
  hmm_refit_days: 30

orb:
  london_window: ["07:00", "08:00"]   # UTC
  newyork_window: ["12:00", "13:00"]  # UTC (geser saat DST)
  min_consolidation_candles: 3
  retest_tolerance_atr: 0.15
  require_h1_squeeze: true

confidence:
  threshold_entry: 70
  threshold_watchlist: 50
  volatile_penalty: 10
  after_two_losses_boost: 5

sessions:
  london: ["07:00", "10:00"]   # UTC
  newyork: ["12:00", "15:00"]

news:
  blackout_minutes: 30
  impacts: ["High"]
  currencies: ["USD"]

risk:
  account_equity_display: 10000   # hanya untuk display lot
  risk_per_trade_pct: 0.5
```

## 8. Failure Modes & Mitigasi

| Kegagalan | Deteksi | Mitigasi |
|---|---|---|
| Data source mati | HTTP error / timeout 3x | fallback ke sumber sekunder; jika semua gagal → mode `DEGRADED`, tidak kirim sinyal |
| PAXG decouple dari spot | basis > 1% | alert sistem + turunkan confidence |
| Candle gap / data stale | `last_ts` > 20 menit | refresh paksa, log warning |
| Telegram down | HTTP 429/5xx | retry exponential, simpan queue di sqlite |
| Proses crash | systemd | `Restart=always`, `RestartSec=10` |
| Jam VPS drift | chrony | `timedatectl` + NTP |
| Alert dobel pasca-restart | startup | dedupe dari sqlite (bukan memory) |
| News blackout terlewat | — | kalender di-cache tiap 6 jam, fail-closed jika gagal fetch |

## 9. Observability

- Log JSON ke journald: `{"ts","level","module","event","data"}`
- Heartbeat: `GET /health` internal atau file `state/heartbeat.json` → dicek healthchecks.io
  setiap 5 menit; jika 3x gagal → email/Telegram "SYSTEM DOWN".
- Metrics harian yang dikirim ke Telegram: uptime, jumlah sinyal, sinyal yang di-suppress
  (dan alasannya). Ini penting untuk audit apakah filter terlalu ketat.
