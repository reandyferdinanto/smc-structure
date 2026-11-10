# 08 — Backtest & Validasi (Gate Go/No-Go)

**Aturan besi:** tidak ada alert live sebelum lulus gate di dokumen ini. Backtest bukan
formalitas — ini satu-satunya cara tahu apakah BB+SMC punya edge di gold setelah biaya.

---

## 1. Data Backtest

| Sumber | Periode | Kualitas | Cara |
|---|---|---|---|
| **Dukascopy** (rekomendasi) | 5+ tahun | tick→M1, terbaik | `dukascopy-python` / API bi5 |
| HistData.com | 2+ tahun | M1 CSV gratis | unduh manual per tahun |
| yfinance `GC=F` | maks 60 hari M15 | cepat, terbatas | prototype saja |

Minimal: **24 bulan** M15 dengan H1/H4 diturunkan dari M15 (bukan dari sumber lain, agar
konsisten).

### 1.1 Contoh unduh Dukascopy

```python
# pip install dukascopy-python
import dukascopy_python
from datetime import datetime, timezone
df = dukascopy_python.fetch(
    "XAUUSD", dukascopy_python.INTERVAL_MIN_1,
    datetime(2023, 1, 1, tzinfo=timezone.utc),
    datetime(2025, 1, 1, tzinfo=timezone.utc),
)
df = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
```

Bersihkan:
- Buang bar dengan `volume == 0` di jam pasar aktif.
- Buang weekend & daily break (Jum 21:00 UTC – Ming 22:00 UTC).
- Resample ulang setelah filter agar tidak ada bar kosong.

---

## 2. Metodologi Backtest

**Event-driven, bar-by-bar**, memakai *engine yang sama* dengan live (`src/strategy/engine.py`).

```
for bar in bars[M15]:
    engine.on_bar(bar, ctx={h1_df, h4_df, macro_bias_hist})
    if engine.signal:
        simulate_fill(signal, next_bar=None)  # isi di close bar sinyal
```

Aturan eksekusi (konservatif):

1. Sinyal dievaluasi pada **close bar** → entry pada **open bar berikutnya** (atau close
   bar sinyal + slippage). Jangan pakai harga tengah bar.
2. SL & TP dievaluasi intrabar dengan urutan: **SL dicek lebih dulu** jika dalam satu bar
   harga menyentuh keduanya (asumsi terburuk).
3. Gap antar bar: jika open melewati SL, isi di open (bukan di SL).
4. Tidak ada partial fill. Satu posisi pada satu waktu (atau sesuai aturan).
5. Tidak ada news filter yang "tahu masa depan" — pakai kalender yang tersedia saat itu
   (simulasikan fetch harian).

### 2.1 Biaya yang wajib dimodelkan

| Komponen | Nilai realistis | Catatan |
|---|---|---|
| Spread | $0.25–0.40 / oz | broker retail gold; kalibrasi ke akun Anda |
| Slippage | $0.05–0.15 / oz | terutama saat news |
| Komisi | $0 (spread-only) atau $3.5/lot | broker ECN |
| Swap/overnight | −$0.5 s/d −$5 /lot/malam | posisi swing |

Posisi yang ditahan melewati 21:00 UTC (rollover) wajib kena biaya swap.

---

## 3. Metrik Wajib

| Metrik | Definisi | Target gate |
|---|---|---|
| Total trades | jumlah posisi | ≥ 100 (2 tahun) |
| Win rate | TP1 hit / total | informatif, bukan target |
| **Expectancy (R)** | rata-rata hasil dalam R | **≥ 0.20R** |
| Profit factor | gross profit / gross loss | **≥ 1.30** |
| Max drawdown | peak-to-trough equity | **≤ 15R** |
| Longest losing streak | berturut-turut | ≤ 8 |
| Avg RR realized | (avg win) / (avg loss) | ≥ 1.4 |
| Sharpe (per trade) | mean/std return | ≥ 0.15 |
| Trades per bulan | frekuensi | 4–20 |
| Exposure | % waktu di pasar | < 30% |
| Max adverse excursion | rata-rata MAE | informatif untuk SL |

### 3.1 Breakdown wajib

- Per sesi (London vs NY vs out-of-session)
- Per arah (long vs short)
- Per regime BB (squeeze vs expansion)
- Per bias makro (searah vs netral)
- Per tahun (konsistensi, bukan hanya agregat)

Jika edge hanya muncul di satu tahun / satu sesi → curigai overfit.

---

## 4. Walk-Forward & Robustness

1. **In-sample**: 2023-01 – 2024-06 (18 bulan) → optimasi parameter.
2. **Out-of-sample**: 2024-07 – 2025-12 (18 bulan) → **jalankan sekali, tanpa ubah parameter**.
3. **Parameter sensitivity**: geser tiap parameter ±20% (mis. bb_mult 1.8/2.0/2.2,
   ote 0.62/0.705/0.786). Edge harus tetap positif di mayoritas kombinasi.
   Jika hancur karena perubahan kecil → **tidak robust**.
4. **Monte Carlo**: acak urutan trade 10.000×, lihat distribusi max DD
   (persentil 95 harus masih dapat ditoleransi).
5. **Regime test**: pisahkan periode trending vs ranging (mis. 2023 = high real yield,
   2024–2025 = cutting cycle). Sistem harus punya aturan yang jelas kapan diam.

---

## 5. Gate Go/No-Go

Sistem **hanya boleh live alert** jika SEMUA terpenuhi pada data out-of-sample:

- [ ] Expectancy ≥ 0.20R setelah biaya
- [ ] Profit factor ≥ 1.30
- [ ] Max DD ≤ 15R
- [ ] ≥ 100 trades OOS
- [ ] Parameter ±20% tidak membalik tanda expectancy
- [ ] Tidak ada satu bulan yang menyumbang > 40% total profit
- [ ] Hasil tidak bergantung pada 3 trade terbaik (uji: buang top 3 → expectancy masih positif... jika tidak, sistem rapuh)

Jika gagal: kembali ke desain (bukan menambah parameter). Opsi:
- Naikkan `min_rr`
- Perketat squeeze percentile (25 → 10)
- Tambah filter sesi (khusus London)
- Kurangi frekuensi (hanya setup A+)

---

## 6. Forward Test (Paper)

Setelah lulus backtest: **4 minggu paper trading** (alert live, eksekusi simulasi manual).

Catat setiap sinyal:
```csv
ts_utc,side,entry,sl,tp1,tp2,rr,confidence,session,bias,outcome,mae,mfe,notes
```

Bandingkan dengan ekspektasi backtest:
- Frekuensi harus mirip (±50%)
- Win rate dalam rentang ±10 poin
- Jika menyimpang jauh → cari penyebab: data berbeda (PAXG vs OANDA), slippage, atau bug.

---

## 7. Pelaporan

Output `reports/backtest_<tag>.md`:

```markdown
# Backtest v0.1.0 — XAUUSD M15
Periode: 2023-01-01 → 2025-12-31 (OOS 2024-07 → 2025-12)
Trades: 214 | Expectancy: 0.27R | PF: 1.42 | MaxDD: 11.3R
Win: 47% | Avg RR: 1.62 | Sharpe/trade: 0.18

## Equity curve
(plot PNG)

## Breakdown
| Sesi | Trades | Exp(R) | PF |
...

## Robustness
- ±20% param: expectancy 0.19–0.31R ✅
- Monte Carlo 95p DD: 14.1R ✅
- Drop top-3 trades: expectancy 0.21R ✅

## Keputusan: GO / NO-GO
```

Simpan juga trade list CSV untuk audit.

---

## 8. Jebakan Backtest yang Harus Dihindari

| Jebakan | Mitigasi |
|---|---|
| Look-ahead bias (pakai data masa depan) | sinyal di close, eksekusi berikutnya |
| Repaint (indikator berubah setelah close) | semua kalkulasi pakai bar closed |
| Survivorship/periode cherry-pick | OOS period tidak boleh diintip |
| Overfitting (terlalu banyak parameter) | maksimal 6 parameter bebas |
| Abaikan spread & swap | wajib dimodelkan |
| Backtest di TF kecil tanpa biaya | M1 backtest sering ilusi |
| Equity curve hanya "bagus di atas kertas" | cek drawdown & streak |

---

## 9. Definition of Done untuk Fase Backtest

- [ ] Dataset Dukascopy 24+ bulan tersimpan di `data/` (parquet)
- [ ] `python scripts/run_backtest.py --tag v0.1.0 --oos-start 2024-07-01` reproducible
- [ ] Laporan MD + equity PNG di `reports/`
- [ ] Trade list CSV
- [ ] Gate checklist di atas terisi dengan angka nyata
- [ ] Keputusan GO / NO-GO tertulis (tanggal + alasan)

---

## 10. Benchmark, Regime Stratification & Upgrade Path (v1.1)

### 10.1 Benchmark wajib (agar tidak menipu diri)

Setiap strategi harus dibandingkan dengan **baseline**, bukan hanya dievaluasi absolut:

| Baseline | Definisi | Kenapa penting |
|---|---|---|
| Random entry | entry acak, SL/TP sama, jumlah trade sama | jika sistem tidak mengalahkan random, edge = ilusi |
| Buy & hold gold | long kontinu periode yang sama | mengukur apakah timing menambah nilai |
| ORB polos | Setup B tanpa squeeze/regime filter | membuktikan filter benar-benar bekerja |
| Sweep polos | Setup A tanpa bias makro | mengukur kontribusi filter news |

Target minimal: expectancy sistem ≥ 1.5× baseline terbaik setelah biaya.

### 10.2 Stratifikasi hasil per regime

Runner backtest wajib menandai setiap trade dengan regime saat entry
(`regime_rule`, opsional `regime_hmm`) lalu melaporkan:

| Regime | Trades | Expectancy | PF | MaxDD | Catatan |
|---|---|---|---|---|---|
| RANGING | ... | ... | ... | ... | Setup A harus dominan di sini |
| TRENDING | ... | ... | ... | ... | Setup B harus dominan |
| VOLATILE | ... | ... | ... | ... | target: 0 trade (semua suppressed) |

Jika Setup A menghasilkan expectancy positif di TRENDING, curigai kebocoran look-ahead
atau filter regime tidak benar-benar aktif.

### 10.3 Verifikasi filter (ablation study)

Matikan satu filter pada satu waktu, jalankan ulang OOS, catat delta expectancy:

| Filter dimatikan | Δ expectancy | Kesimpulan |
|---|---|---|
| Bias H4 | ... | harus negatif besar (filter bekerja) |
| Regime | ... | harus negatif |
| Blackout news | ... | harus negatif |
| Squeeze | ... | harus negatif |
| OB fresh-only | ... | harus ≥ 0 |
| Partial-fill FVG | ... | harus ≥ 0 |

Filter yang **tidak** memberi delta positif wajib dihapus — kompleksitas tanpa manfaat
adalah sumber bug.

### 10.4 Backtest–live parity

Prinsip dari `EA_SCALPER_XAUUSD`: backtest dan live memakai **engine yang sama persis**.
Cara membuktikan:

1. Rekam 1 minggu data live (`data/live_capture/*.parquet`).
2. Feed ulang file yang sama ke `runner.py` mode replay.
3. Sinyal yang dihasilkan harus **identik** (ts, side, entry, sl, tp).
   Jika beda → ada state yang tidak deterministik (waktu sistem, random, cache).
4. Jalankan otomatis di CI setiap PR yang menyentuh `strategy/`.

### 10.5 Upgrade path: NautilusTrader

Migrasi hanya jika salah satu terpenuhi:
- butuh multi-instrument (XAU + DXY + yields dalam satu event loop),
- butuh order book/eksekusi MT5 native,
- engine sendiri sudah > 5k baris dan sulit dites.

Langkah migrasi:
1. Bungkus `strategy/*` sebagai `Strategy` subclass (fungsi murni tetap dipakai).
2. Ganti `data/` adapter dengan `ParquetDataCatalog`.
3. Bandingkan hasil backtest Nautilus vs engine lama pada periode & parameter sama;
   deviasi expectancy harus < 10% sebelum lanjut.
4. Live/paper via adapter broker (MT5/IB) — tetap alert-only sampai lolos gate.

Catatan lisensi: NautilusTrader berlisensi **Apache-2.0** — aman untuk penggunaan komersial
dengan notice.

### 10.6 Definition of Done tambahan (v1.1)

- [ ] Laporan benchmark 4 baseline
- [ ] Tabel stratifikasi 3 regime
- [ ] Tabel ablation 6 filter
- [ ] Test parity live-capture hijau di CI
- [ ] Keputusan: tetap di engine sendiri / migrasi Nautilus (dengan alasan)
