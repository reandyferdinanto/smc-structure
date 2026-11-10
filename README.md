# smc-structure

XAUUSD alert engine — Bollinger Bands volatility regime + SMC/ICT structure,
with Telegram notifications and an optional Pine Script/webhook path.

## Status

Fase 0–2 dari rencana (`docs/`): data layer, strategy primitives, engine,
Telegram. Backtest, Pine, dan deploy VPS menyusul.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env            # isi token Telegram jika ingin kirim alert
python -m src.main --once       # ambil data + evaluasi, tanpa kirim jika DRY_RUN=true
pytest
```

## Struktur

```
config/       settings.yaml
src/data/     adapter gold-api, Binance PAXG, normalizer
src/strategy/ BB, pivots, liquidity, structure, OB, FVG, OTE, regime, ORB, engine
src/alerts/   Telegram client, templates, dedupe (sqlite), trade tracker
src/macro/    ForexFactory calendar, bias scoring, news
docs/         rencana lengkap (00–10)
scripts/      utilitas manual
tests/        unit test primitif strategi
```

## Backtest

```bash
python scripts/backtest.py --days 60 --every 4 --tag quick60
```

## Re-entry (sinyal terlewat)

```bash
python scripts/reentry.py --tf m5
```

Panduan: `docs/12-reentry.md`.

Panduan lengkap: `docs/11-cara-backtest.md`.

## Dokumentasi

Baca `docs/00-README.md` lalu `docs/02-spesifikasi-strategi.md` sebelum mengubah
logika sinyal. Semua parameter ada di `config/settings.yaml`.

> Bukan nasihat keuangan. Sistem ini hanya mengirim alert; eksekusi manual.
