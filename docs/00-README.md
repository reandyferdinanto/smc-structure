# XAUUSD BB + SMC/ICT Alert System — Master Plan

> Dokumen perencanaan lengkap untuk membangun sistem alert trading XAUUSD berbasis
> **Bollinger Bands + Smart Money Concepts/ICT** dengan **Telegram** sebagai kanal notifikasi,
> **Pine Script** sebagai sumber trigger teknikal, dan **Python** sebagai mesin makro/berita.
>
> Target eksekusi: coding dari VPS (Ubuntu), laptop hanya untuk development.

---

## 1. Ringkasan Proyek

| Item | Keputusan |
|---|---|
| Instrumen | XAUUSD (spot gold) |
| Strategi | BB volatility regime + SMC/ICT, 2 setup (Sweep Reversal & Session ORB) + Regime Layer |
| Timeframe | H4 bias → H1 setup → M15 trigger |
| Kanal alert | Telegram Bot (gratis) |
| Trigger teknikal | Pine Script di TradingView (server-side) **atau** Python lokal |
| Konteks makro | Python: kalender ForexFactory, FRED, GDELT, Google News |
| Data harga | gold-api.com (spot), Binance PAXG (OHLCV), Yahoo GC=F (histori), TradingView scanner (quote) |
| Hosting | VPS Ubuntu 24.04, 2 vCPU / 2 GB RAM |
| Auto-trading | **Tidak** — sistem ini hanya alert, eksekusi manual |

**Bukan tujuan proyek ini:** eksekusi order otomatis, menjual sinyal, menggantikan analisis
discretionary. Alert = *decision support*, bukan robot trading.

---

## 2. Indeks Dokumen

| File | Isi | Dipakai saat |
|---|---|---|
| [01-arsitektur.md](01-arsitektur.md) | Diagram sistem, struktur repo, env vars, alur data | Sebelum menulis kode |
| [02-spesifikasi-strategi.md](02-spesifikasi-strategi.md) | Aturan BB + SMC/ICT yang presisi (angka, bukan opini) | Saat implementasi engine |
| [03-data-sources.md](03-data-sources.md) | Semua endpoint terverifikasi + fallback + kualitas data | Saat membangun layer data |
| [04-pine-script.md](04-pine-script.md) | Spesifikasi indikator & strategy Pine, alert JSON, limit plan TV | Saat membuat Pine + webhook |
| [05-telegram-bot.md](05-telegram-bot.md) | Setup bot, template pesan, rate limit, relay Worker | Saat integrasi notifikasi |
| [06-macro-news-engine.md](06-macro-news-engine.md) | Model skoring makro & mesin berita | Saat membangun bias harian |
| [07-vps-deployment.md](07-vps-deployment.md) | Setup VPS, systemd, Cloudflare Worker, monitoring | Saat deploy produksi |
| [08-backtest-validasi.md](08-backtest-validasi.md) | Metodologi backtest, metrik, gate go/no-go | **Sebelum** live alert |
| [09-risk-dan-roadmap.md](09-risk-dan-roadmap.md) | Risk rules, jurnal, roadmap fase, checklist go-live | Selama eksekusi |
| [10-referensi-opensource.md](10-referensi-opensource.md) | Repo GitHub terkurasi + aturan lisensi/atribusi | Sebelum mengadopsi kode eksternal |

Urutan baca yang disarankan: `01 → 02 → 03 → 05 → 06 → 07`, lalu `04`, lalu `08`, terakhir `09` + `10`.

---

## 3. Status Verifikasi Data (10 Nov 2026)

Endpoint berikut **sudah dites live** dari mesin development:

| Endpoint | Hasil |
|---|---|
| `api.gold-api.com/price/XAU` | 200 — `4117.70` |
| `data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT` | 200 — OHLCV 5m |
| `scanner.tradingview.com/global/scan` (`OANDA:XAUUSD`) | 200 — `4116.675` |
| yfinance `GC=F` | 200 — 247 bar 5m |
| `nfs.faireconomy.media/ff_calendar_thisweek.json` | 200 — 14 KB |
| Google News RSS | 200 |
| GDELT DOC API v2 | 200 |
| Yahoo `XAUUSD=X` | 404 — **tidak tersedia** |
| `api.binance.com` (main) | TLS diblok di jaringan dev → pakai `data-api.binance.vision` |
| Stooq / TwelveData / exchangerate.host | butuh key / diblok JS |

---

## 4. Prinsip Desain

1. **Separation of concerns** — data, strategi, makro, notifikasi adalah modul terpisah yang
   hanya berkomunikasi lewat struktur data (dataclass/dict) yang jelas.
2. **Fail open untuk data, fail closed untuk sinyal** — jika data tidak lengkap, sistem
   *menolak* mengeluarkan sinyal (lebih baik tidak alert daripada alert salah).
3. **Idempotent & dedupe** — satu event pasar = satu pesan Telegram, walau proses restart.
4. **UTC di mana-mana** — konversi ke WIB hanya di layer tampilan.
5. **Backtest dulu, baru live** — tidak ada alert live sebelum lulus gate di `08`.
6. **Secrets tidak pernah masuk repo** — `.env` di VPS, `chmod 600`, token bot tidak
   ditaruh di alert message TradingView.

---

## 5. Estimasi Biaya

| Komponen | Biaya |
|---|---|
| VPS 2 vCPU / 2 GB (Hetzner CX22 / DO basic) | €3.8–6 / bulan |
| Telegram Bot API | gratis |
| Cloudflare Workers (relay webhook) | gratis (100k req/hari) |
| TradingView plan berbayar (webhook) | ~$14–30 / bulan *(opsional, fase 4+)* |
| Data gratis (gold-api, Binance, Yahoo, FF, GDELT, FRED) | gratis |
| **Total fase 1–3 (Python-only)** | **~€4–6 / bulan** |

---

## 6. Deliverable Akhir

- [ ] `xauusd-alerts` running di VPS sebagai systemd service
- [ ] Alert entry (long/short) dengan entry/SL/TP + alasan
- [ ] Digest makro harian 07:00 WIB + reminder high-impact news
- [ ] Pine indicator + strategy tervalidasi di TradingView
- [ ] Laporan backtest 2 tahun dengan metrik lengkap
- [ ] Jurnal trade + review mingguan

## 7. Changelog

### v1.6 — 10 Nov 2026
Re-entry untuk sinyal terlewat:
- `scripts/reentry.py` (`--tf m5|m1`, `--send`) → `12-reentry.md`
- Syarat: progress < 70% ke TP1, bounce BB middle, RR sisa ≥ 1.2, belum lewat invalid
- `TradeTracker.last_signal()` membaca sinyal terakhir dari DB

### v1.5 — 10 Nov 2026
Perlindungan news mendadak:
- Pre-news warning 15 menit (jika ada posisi/armed) → `06 §9.2`
- Spike guard M1 (range/body vs median) menahan entry baru → `06 §9.3`
- Konfirmasi armed ditahan saat blackout/spike, cancel & expiry tetap jalan

### v1.4 — 10 Nov 2026
Two-stage alert (setup → konfirmasi M5 → OPEN NOW):
- `src/strategy/trigger.py` (konfirmasi zona + micro sweep + micro BOS) → `02 §14`
- `armed_signals` di `state/signals.db`, pesan SETUP/OPEN/CANCEL → `05 §11`
- `main.py`: fetch M5, proses armed sebelum sinyal baru
- Backtest masih single-stage (data M5 belum) — dicatat sebagai keterbatasan

### v1.3 — 10 Nov 2026
Trade tracker: update TP1/SL/EXPIRED otomatis.

### v1.2 — 10 Nov 2026
Session layer untuk pengguna WIB:
- Tabel sesi UTC ↔ WIB (summer/winter) + jam terbaik trading → `02 §13`
- Asian range sebagai liquidity pool (ICT judas swing) → `02 §13.3`
- `session_label()` + `session_score` untuk confidence → `02 §13.4`
- Penyesuaian jadwal digest ke WIB (12:00 / 13:30 / 18:30 / 05:30) → `02 §13.5`
- Pine session marker + pergeseran DST → `04 §10`

### v1.1 — 10 Nov 2026
Referensi open-source diadopsi (lihat `10-referensi-opensource.md`):
- **Order Block + mitigation** dan **internal vs major structure** (iCHoCH/MBOS) → `02 §3.4, §3.9`
- **Setup B: Session ORB** (konsep GOLD_ORB) → `02 §9`
- **Regime Layer** rule-based + peta regime→setup (ide HMM dari xaubot-ai) → `02 §10`
- **Filter Stack 12 poin** + dynamic confidence threshold → `02 §11`
- Modul baru `strategy/orderblock.py`, `strategy/orb.py`, `strategy/regime.py` → `01 §3`
- Pine: adaptasi MIT `quantumalgo SMC` + konvensi penamaan `SMC-Marking` → `04 §9`
- Backtest: benchmark vs baseline, stratifikasi per regime, jalur NautilusTrader → `08 §10`
- Roadmap: tugas studi referensi + modul regime/ORB → `09 §3`

### v1.0 — 10 Nov 2026
Rilis awal 10 dokumen.

---

> **Disclaimer:** dokumen ini adalah rencana rekayasa perangkat lunak. Bukan nasihat
> keuangan. Trading gold dengan leverage dapat menghabiskan seluruh modal.
