# 09 — Risk Management, Jurnal & Roadmap

---

## 1. Aturan Risiko (non-negotiable)

### 1.1 Position sizing

```
risk_$        = equity × risk_per_trade_pct        # 0.25% – 0.50%
sl_distance   = |entry - sl|                       # dalam USD/oz
lot_size      = risk_$ / (sl_distance × contract_size)
```

Contoh:
```
equity            = $10,000
risk_per_trade    = 0.5%  → $50
sl_distance       = $7.23/oz
contract_size     = 100 oz/lot (XAUUSD standard)
lot               = 50 / (7.23 × 100) = 0.069 lot ≈ 0.07 lot
```

Jika broker memakai satuan berbeda (0.01 lot = 1 oz), sesuaikan `contract_size` di config.

### 1.2 Batas keras

| Batas | Nilai | Aksi saat tercapai |
|---|---|---|
| Risk per trade | 0.5% equity | tolak sinyal jika lot < minimum broker |
| Risk harian | −1.5% equity | stop trading hari itu |
| Risk mingguan | −4% equity | stop sampai Senin berikutnya |
| Max posisi terbuka | 2 | sinyal baru diabaikan |
| Max sinyal/hari | 3 | engine sudah meng-cap |
| Max loss beruntun | 4 | pause 48 jam + review |
| Drawdown total | −10% equity | **kill switch**: matikan sistem, review penuh |

### 1.3 Aturan eksekusi manual

1. Entry hanya di harga yang di-alert atau lebih baik (jangan chase > 0.3×ATR).
2. SL dipasang **bersamaan** dengan entry, bukan setelahnya.
3. TP1 = tutup 50%, sisa ke TP2 dengan SL dipindah ke breakeven (opsional, harus konsisten).
4. Tidak ada averaging down.
5. Posisi yang belum hit TP1 sebelum 32 bar M15 → tutup manual atau sesuai rencana.
6. Jangan menahan posisi melewati high-impact news (kecuali strategi eksplisit).
7. Jumat: tutup posisi sebelum 21:00 UTC (04:00 WIB Sabtu) atau kurangi 50%.

### 1.4 Kill switch

Satu tombol (file `state/KILL` atau `/mute 24h` di bot) yang:
- menghentikan semua entry alert,
- tetap mengirim digest & warning news,
- mengirim notifikasi "SISTEM DIMATIKAN OLEH USER".

---

## 2. Jurnal Trading

### 2.1 Skema SQLite

```sql
CREATE TABLE trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id TEXT,                -- dedupe_key dari sistem
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  symbol TEXT DEFAULT 'XAUUSD',
  side TEXT NOT NULL,
  entry REAL NOT NULL,
  sl REAL NOT NULL,
  tp1 REAL NOT NULL,
  tp2 REAL NOT NULL,
  lot REAL NOT NULL,
  risk_usd REAL NOT NULL,
  outcome TEXT,                 -- tp1 | tp2 | sl | manual | timeout
  pnl_usd REAL,
  r_multiple REAL,
  mae REAL, mfe REAL,
  confidence INTEGER,
  session TEXT,
  bias_score INTEGER,
  followed_plan INTEGER,        -- 1/0
  notes TEXT
);
```

### 2.2 Review mingguan (30 menit, tiap Sabtu)

- Win rate, expectancy R, total R minggu ini
- Berapa trade yang **tidak** sesuai plan? (target: 0)
- Berapa alert yang di-suppress? Apakah filter terlalu ketat/longgar?
- Satu pelajaran, satu perbaikan konkret
- Update parameter hanya jika ada ≥ 30 trade baru (hindari reaktif)

### 2.3 Metrik pribadi (bulanan)

| Metrik | Target |
|---|---|
| Plan adherence | ≥ 95% |
| Expectancy | mengikuti backtest ±20% |
| Max DD | < 10R |
| Overtrading (trade/hari) | ≤ 3 |
| Revenge trades | 0 |

---

## 3. Roadmap Fase

Total estimasi: **7–10 minggu** part-time (10–15 jam/minggu). *(naik dari 6–9 minggu di v1.0 karena tambahan modul regime, OB, dan ORB)*

### Fase 0 — Fondasi (2–3 hari)
- [ ] Scaffold repo + `pyproject.toml` + `config/settings.yaml`
- [ ] `utils/time.py` (UTC↔WIB), `utils/log.py` (JSON)
- [ ] Adapter data + cache parquet + QC tests
- [ ] **Studi referensi** (`10-referensi-opensource.md`): baca quantumalgo SMC, xaubot-ai
      (regime/filter), GOLD_ORB (konsep ORB). Tulis catatan ADR: apa yang diadopsi,
      apa yang ditolak, dan lisensinya.
- **Selesai jika:** `python -m src.main --once` mengambil data & menulis parquet + ADR tertulis

### Fase 1 — Strategi & Unit Test (2 minggu)
- [ ] `bollinger.py`, `swings.py` (major k=5 / internal k=2), `liquidity.py`
- [ ] `structure.py` (BOS/CHoCH/iCHoCH/MBOS), `fvg.py` (+partial fill), `orderblock.py` (+mitigation), `ote.py`
- [ ] `regime.py` (rule-based: ADX/ATR rank/BW rank/EMA slope)
- [ ] `engine.py` state machine Setup A + **filter stack 12 poin**
- [ ] `orb.py` Setup B (window London/NY, konsolidasi, retest)
- [ ] `ml/` **belum** disentuh — HMM ditunda ke fase 6
- [ ] Unit test tiap modul + 14 skenario state machine (fixture candle manual)
- **Selesai jika:** `pytest -q` hijau, contoh numerik di `02 §6` cocok, dan setiap sinyal
  mencatat `setup` (A/B) + regime saat entry

### Fase 2 — Telegram (2–3 hari)
- [ ] Bot, template, dedupe sqlite, outbox retry
- [ ] `scripts/send_test_alert.py`
- **Selesai jika:** alert uji masuk HP, dedupe terbukti

### Fase 3 — Makro & Digest (1 minggu)
- [ ] `calendar.py`, `fred.py`, `news.py`, `bias.py`, `digest.py`
- [ ] Integrasi gate (bias/blackout) ke engine
- **Selesai jika:** digest 07:00 WIB terkirim, blackout men-suppress sinyal uji

### Fase 4 — Backtest & Validasi (1–2 minggu)
- [ ] Unduh Dukascopy 24–36 bulan
- [ ] `runner.py` + `metrics.py` + laporan
- [ ] Walk-forward, sensitivity, Monte Carlo
- **Selesai jika:** laporan lengkap + keputusan GO/NO-GO tertulis

### Fase 5 — Pine Script (1 minggu, boleh paralel)
- [ ] Indicator + strategy, alert JSON (termasuk `"setup":"A"|"B"`)
- [ ] Adaptasi OB/FVG dari quantumalgo (MIT) + header atribusi (`04 §9`)
- [ ] Cloudflare Worker relay
- [ ] Cross-check 10 sinyal Pine vs Python (per setup)
- **Selesai jika:** sinyal Pine == Python pada bar yang sama untuk Setup A dan B

### Fase 6 — Deploy VPS (2–3 hari)
- [ ] systemd, monitoring, backup
- [ ] Paper trading 4 minggu (alert live, eksekusi simulasi)
- **Selesai jika:** 4 minggu paper, deviasi vs backtest < 20%

### Fase 7 — Live kecil (berkelanjutan)
- [ ] Mulai 0.25% risk/trade, 1 posisi, maksimal 1 minggu pertama
- [ ] Evaluasi mingguan, naikkan risk hanya jika 4 minggu positif & sesuai plan
- **Selesai jika:** 8 minggu live konsisten → naikkan perlahan (maks 0.5%)

---

## 4. Checklist Go-Live (semua harus ✅)

**Teknis**
- [ ] systemd auto-restart terbukti (kill proses → hidup lagi < 15 detik)
- [ ] Dedupe & outbox terbukti
- [ ] Fail-closed kalender terbukti
- [ ] Healthcheck ping berjalan
- [ ] Backup harian + restore test
- [ ] DRY_RUN=false dan alert uji sampai

**Strategi**
- [ ] Backtest lulus gate `08`
- [ ] 4 minggu paper trading, deviasi < 20%
- [ ] Parameter di-lock (tidak diubah selama live)

**Operasional**
- [ ] Position sizing dihitung ulang untuk equity aktual
- [ ] Batas harian/mingguan ditulis & dipatuhi
- [ ] Kill switch diuji
- [ ] Jurnal siap pakai

**Mental**
- [ ] Menerima bahwa sistem akan kalah di sebagian trade
- [ ] Tidak akan "membantu" sinyal dengan discretionary override di 4 minggu pertama
- [ ] Tidak akan menaikkan risk setelah 3 win beruntun

---

## 5. Risiko Proyek (bukan risiko trading)

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Endpoint gratis berubah/mati | sistem buta | adapter + fallback matrix, cek mingguan |
| PAXG decouple dari spot | level meleset | basis monitor, alert jika > 1% |
| Overfitting | live tidak cocok backtest | walk-forward + OOS + paper 4 minggu |
| Terlalu banyak sinyal saat chop | overtrading | bias NEUTRAL + cooldown + daily cap |
| Ketergantungan TradingView plan | biaya | Python path tetap hidup sebagai fallback |
| Bug timezone (DST) | blackout salah | UTC internal, test konversi, hindari "WIB hardcode" |
| Adopsi kode tanpa lisensi jelas | risiko legal | clean-room: baca konsep, tulis ulang (aturan di `10 §2`) |
| Modul regime/ORB menambah kompleksitas | bug & overfit | ablation study `08 §10.3`; hapus filter yang tak berguna |
| Kelelahan mengerjakan | proyek mangkrak | fase kecil, tiap fase punya "definition of done" |

---

## 6. Yang Tidak Boleh Dilakukan

1. ❌ Menambah fitur sebelum gate backtest lulus.
2. ❌ Mengubah parameter setelah melihat drawdown live (kecuali lewat review terjadwal).
3. ❌ Menaikkan risk karena "yakin setup ini".
4. ❌ Menjalankan VPS dengan `DRY_RUN=false` sebelum paper trading selesai.
5. ❌ Menyimpan token bot / API key di repo atau di Pine alert.

---

## 7. Catatan Penutup

Sistem ini dibuat untuk **mengurangi keputusan emosional**, bukan menghilangkan risiko.
Keunggulan sebenarnya bukan pada indikatornya, tapi pada **disiplin menunggu konfluensi**
(bias makro + squeeze + sweep + CHoCH + entry di zona) dan **konsistensi eksekusi** setelah
sinyal muncul.

> Trading gold dengan leverage dapat menyebabkan kerugian melebihi modal.
> Dokumen ini bukan nasihat keuangan.
