# 12 — Re-entry Command (sinyal terlewat)

## 1. Kenapa tidak ada signal lagi?

Sistem sengaja sangat selektif. Sinyal hanya keluar jika **semua** kondisi terpenuhi
sekaligus: bias H4 ≥ ±2, regime bukan VOLATILE, squeeze H1, sweep likuiditas, displacement,
konfirmasi mikro, zona FVG/OB, RR ≥ 1.5, di dalam killzone, dan tidak blackout news.

Contoh status saat dokumen ini dibuat:

```
bias_h4        : 0 (netral)      → tidak boleh entry
regime_h1      : TRENDING
squeeze H1     : false (bbw rank 57)
session        : asia            → di luar killzone
```

Jadi "tidak ada sinyal" adalah **perilaku yang benar**, bukan bug. Backtest 120 hari juga
hanya menghasilkan 2 trade — frekuensi memang perlu dikalibrasi lewat backtest, bukan
dengan memaksa sinyal keluar.

---

## 2. Re-entry setelah sinyal terlewat

Ide: sinyal awal terlewat, tapi harga belum jauh ke TP dan ada pullback sehat ke
**BB middle (SMA20)** di M5/M1 yang ditolak. Entry masih layak **jika** sisa RR bagus.

### 2.1 Syarat re-entry

| Syarat | Nilai default |
|---|---|
| Arah sama dengan sinyal terakhir | wajib |
| Harga belum melewati 70% jarak ke TP1 | `max_progress: 0.70` |
| Menyentuh BB middle (toleransi 0.15 ATR) | `tol_mult: 0.15` |
| Candle reject: close di sisi tren + body ≥ 0.3 ATR | `min_body_mult: 0.30` |
| SL = swing terakhir ± 0.1 ATR | `swing_lookback: 10` |
| RR sisa ke TP1 | `min_rr: 1.2` |
| Harga belum menembus level invalid sinyal asli | wajib |
| Timeframe | M5 (default) atau M1 |

### 2.2 Perintah

```bash
# cek saja (tidak kirim)
python scripts/reentry.py --tf m5

# cek + kirim ke Telegram jika valid (DRY_RUN=false)
python scripts/reentry.py --tf m5 --send

# pakai M1, RR minimum 1.5
python scripts/reentry.py --tf m1 --min-rr 1.5
```

Output JSON:

```json
{"valid": true, "reason": "valid", "side": "long", "entry": 4113.10,
 "sl": 4109.80, "tp1": 4125.20, "tp2": 4134.00, "rr": 3.63, "timeframe": "5m"}
```

Alasan penolakan: `no_signal_in_db`, `no_bb_mid_bounce`, `too_late`, `rr_too_low`,
`below_invalidation` / `above_invalidation`, `invalid_stop`.

### 2.3 Batasan penting

- Re-entry **bukan sinyal baru**. Referensinya selalu sinyal terakhir di `state/signals.db`;
  kalau DB kosong, perintah menolak (`no_signal_in_db`).
- Maksimal **satu** re-entry per sinyal secara operasional (disiplin manual; belum ada
  counter otomatis).
- Jangan gunakan re-entry untuk **averaging down**. Kalau harga sudah menembus SL asli,
  perintah menolak (`below_invalidation`).
- BB middle adalah filter, bukan alasan entry sendiri: tanpa sweep/struktur awal yang valid,
  bounce di mid hanya noise.
- Belum ada backtest khusus re-entry. Ukur dulu sebelum dipakai konsisten.

### 2.4 Kapan sebaiknya tidak dipakai

- Saat blackout news atau spike guard aktif.
- Saat regime VOLATILE.
- Saat sisa jarak ke TP1 < 30% (RR jelek) — perintah sudah menolak via `too_late`.
- Saat harga sudah lebih dari setengah jalan ke TP1 dan Anda belum punya posisi.
