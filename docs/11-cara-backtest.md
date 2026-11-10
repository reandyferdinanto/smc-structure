# 11 — Cara Backtest (Praktis)

Dua level: **quick** (Binance/PAXG, gratis, menit) dan **serius** (Dukascopy 2 tahun,
untuk gate go/no-go). Mulai dari quick.

---

## 1. Quick backtest (sudah tersedia di repo)

```bash
cd C:\reandy\smc-structure-project
python scripts/backtest.py --days 60 --every 4 --tag quick60
```

Yang terjadi:
1. Unduh OHLCV M15 PAXGUSDT 60 hari dari Binance Vision (dipaginasi 1000 bar/request).
2. Simpan cache di `data/history_15m_60d.csv` (run berikutnya pakai cache).
3. Resample ke H1 & H4.
4. Replay tiap 4 bar (≈1 jam) melalui **engine yang sama** dengan live (`src/strategy/engine.py`).
5. Simulasi hasil: entry di open bar berikutnya, spread $0.35/oz, SL dicek lebih dulu
   (asumsi terburuk), TP1 = 1×ATR(H1), max hold 96 bar M15 (24 jam).
6. Metrik + `reports/backtest_<tag>.csv`.

Contoh output:
```json
{"trades": 18, "wins": 7, "win_rate": 0.389, "expectancy_r": 0.12,
 "profit_factor": 1.19, "max_drawdown_r": 6.4, "avg_rr_win": 2.1, "total_r": 2.2}
```

### Opsi

| Flag | Default | Fungsi |
|---|---|---|
| `--days` | 60 | panjang data (Binance, maks wajar 180) |
| `--every` | 4 | evaluasi tiap N bar M15 (1 = paling akurat, paling lambat) |
| `--window` | 600 | bar konteks per evaluasi |
| `--max-hold` | 96 | batas waktu posisi (bar M15) |
| `--spread` | 0.35 | biaya spread USD/oz (kalibrasi ke broker Anda) |
| `--csv` | — | pakai file CSV sendiri (format: ts,open,high,low,close,volume) |
| `--tag` | quick | nama file output |

Akurasi vs kecepatan: `--every 1` = 4× lebih lambat, tapi tidak melewatkan bar. Untuk
data 60 hari, `--every 1` masih wajar; untuk 2 tahun pakai `--every 4` atau Dukascopy
runner terpisah.

---

## 2. Yang **belum** dimodelkan (penting)

| Item | Status | Dampak |
|---|---|---|
| Order entry sebagai limit (mid FVG/OB) | ❌ memakai open bar berikutnya | hasil cenderung lebih konservatif untuk Setup A |
| Partial TP (50% di TP1) | ❌ semua keluar di TP1 | expectancy sedikit understated |
| Swap/overnight | ❌ | posisi >1 hari terlihat lebih baik dari kenyataan |
| Blackout news & macro bias | ❌ (dipanggil `None`) | filter belum teruji |
| PAXG vs XAUUSD basis | ⚠️ ~0.1–0.5% | level absolut bergeser, struktur hampir sama |
| Slippage saat news | ❌ | hasil live bisa lebih buruk |
| Setup B ORB | ✅ ikut diuji | window London/NY |

Jadi angka quick backtest = **indikasi awal**, bukan bukti. Gate final tetap di `docs/08`.

---

## 3. Backtest serius (Dukascopy)

Untuk validasi 2 tahun (gate go/no-go):

```bash
pip install dukascopy-python
```

```python
# scripts/dukascopy_to_csv.py (buat sendiri sesuai docs/08 §1.1)
import dukascopy_python
from datetime import datetime, timezone
df = dukascopy_python.fetch(
    "XAUUSD", dukascopy_python.INTERVAL_MIN_1,
    datetime(2023, 1, 1, tzinfo=timezone.utc),
    datetime(2026, 1, 1, tzinfo=timezone.utc),
)
df = df.resample("15min").agg(
    {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
).dropna()
df.to_csv("data/xauusd_15m.csv")   # pastikan kolom index bernama ts
```

Lalu:
```bash
python scripts/backtest.py --csv data/xauusd_15m.csv --every 4 --spread 0.35 --tag dukascopy
```

Catatan: `load_csv` mengharapkan kolom index bernama `ts` dalam UTC. Ekspor Dukascopy
sudah UTC.

---

## 4. Membaca hasil (gate)

Gunakan aturan `docs/08-backtest-validasi.md §5`:

| Metrik | Lulus jika |
|---|---|
| Expectancy | ≥ 0.20R setelah biaya |
| Profit factor | ≥ 1.30 |
| Max drawdown | ≤ 15R |
| Jumlah trade | ≥ 100 (2 tahun) |
| Parameter ±20% | expectancy tidak berbalik tanda |
| Tanpa 3 trade terbaik | expectancy masih > 0 |

Jika tidak lulus: **jangan** tambah indikator. Perbaiki dengan:
1. Naikkan `min_rr` (config) → 1.8–2.0.
2. Perketat `squeeze_percentile` 25 → 10.
3. Kurangi frekuensi (hanya Setup A atau hanya London).
4. Perbaiki pemilihan FVG/OB (paling relevan, bukan terakhir).

---

## 5. Menjalankan ulang setelah ubah parameter

Parameter ada di `config/settings.yaml` (bukan di kode). Ubah → jalankan ulang dengan
tag berbeda → bandingkan:

```bash
python scripts/backtest.py --days 90 --every 4 --tag v2_rr18
```

Simpan hasil di `reports/` (di-gitignore) dan catat kesimpulan di commit message/ADR.

---

## 6. Unit test

```bash
python -m pytest
```

Test yang ada: BB, pivot, FVG, liquidity/sweep, session, bias, engine gate, metrik backtest.
Test untuk sinyal end-to-end belum ada — tambahkan fixture candle yang menghasilkan
Setup A dan B setelah engine distabilkan.

---

## 7. Hasil awal (10 Nov 2026) — pembacaan jujur

Run pertama:

```bash
python scripts/backtest.py --days 120 --every 4 --tag smoke120
# bars=11520  2026-07-13 → 2026-11-10
# {"trades": 2, "win_rate": 0.0, "expectancy_r": -1.0, "total_r": -2.0}
```

**Interpretasi:**
- Harness berfungsi (data, replay, simulasi, metrik, CSV).
- Tapi frekuensi sinyal **jauh di bawah rencana** (2 trade / 4 bulan vs target 4–20/bulan).
- Sampel 2 trade **tidak cukup** untuk menyimpulkan edge; jangan ambil keputusan apa pun.

**Penyebab yang paling mungkin** (berdasarkan tally intermediet):
1. Kombinasi `squeeze` + `sweep` pada level yang sama jarang terjadi bersamaan —
   squeeze membuat harga terkurung di tengah band, sedangkan sweep terjadi di ekstrem.
2. `sweep_lookback=5` masih sempit; sweep sering terjadi lebih awal dari konfirmasi.
3. `min_rr=1.5` dengan TP1 = 1×ATR(H1) memangkas banyak kandidat.
4. `--every 4` melewatkan bar trigger.

**Kalibrasi yang harus dicoba (satu per satu, catat hasilnya):**
```yaml
strategy:
  min_rr: 1.2                 # longgarkan
  sweep_lookback: 8
  squeeze_percentile: 35
  squeeze_recent: 10
```
lalu:
```bash
python scripts/backtest.py --days 120 --every 1 --tag every1
```
Bandingkan jumlah trade & expectancy. Baru setelah ≥ 100 trade (butuh Dukascopy 2 tahun)
gunakan gate `docs/08`.

**Jangan** menurunkan kualitas sampai sistem menghasilkan trade; lebih baik sistem jarang
trade dan lulus gate daripada sering trade tanpa edge.
