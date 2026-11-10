# 02 — Spesifikasi Strategi (BB + SMC/ICT)

> **v1.1** — diperkaya dengan referensi open-source (`GifariKemal/xaubot-ai`,
> `quantumalgo-official/smart-money-concepts-indicator`, `kxngHADES/SMC-Marking`,
> `yulz008/GOLD_ORB`). Lihat `10-referensi-opensource.md` untuk atribusi & lisensi.
> Perubahan utama: **Order Block + mitigation**, **internal vs major structure**,
> **Setup B (Session ORB)**, **Regime Layer**, **Filter Stack 12-poin**.

Dokumen ini adalah **sumber kebenaran** untuk logika sinyal. Setiap angka di sini harus
muncul di `config/settings.yaml`, tidak boleh hardcode di kode.

> Prinsip: BB menjawab **"kapan volatilitas akan ekspansi dan di mana harga ekstrem"**.
> SMC/ICT menjawab **"apakah pergerakan itu stop-run dan di mana entry presisi"**.
> Regime menjawab **"apakah strategi ini sedang berada di lingkungan yang tepat"**.

---

## 1. Timeframe & Peran

| TF | Peran | Yang dihitung |
|---|---|---|
| D1 | Bias makro struktural | struktur major (HH/HL vs LH/LL), lokasi dalam dealing range |
| H4 | **Bias trading** | BOS/CHoCH terakhir, premium/discount, BB regime |
| H1 | **Setup** | squeeze, liquidity pool, order block, lokasi band |
| M15 | **Trigger & entry** | sweep, displacement, CHoCH internal, FVG, OTE |

Aturan: entry selalu di M15, arah selalu dari H4. H1 menentukan *apakah* setup layak.

---

## 2. Modul A — Bollinger Bands

### 2.1 Perhitungan

```
middle = SMA(close, 20)
sd     = stdev(close, 20)              # populasi, ddof=0 (sama dengan TradingView)
upper  = middle + 2.0 * sd
lower  = middle - 2.0 * sd
width  = (upper - lower) / middle * 100        # BandWidth (%)
percent_b = (close - lower) / (upper - lower)  # %B
```

### 2.2 Label Regime BB (H1)

| Kondisi | Regime | Arti |
|---|---|---|
| `width <= P25(width, 100 bar)` selama ≥ 5 bar | **SQUEEZE** | kompresi → potensi ekspansi |
| `percent_b > 1.0` | **UPPER TAG** | harga di luar band atas (strength, bukan sell) |
| `percent_b < 0.0` | **LOWER TAG** | harga di luar band bawah (weakness, bukan buy) |
| `width >= P75(width, 100 bar)` | **EXPANSION** | jangan chase, tunggu pullback |

Sentuhan band = *tag*, **bukan sinyal reversal**. Band walk = konfirmasi tren.

### 2.3 Fungsi BB dalam Sistem

1. **Regime filter** — setup hanya dicari saat SQUEEZE atau transisi SQUEEZE → EXPANSION
   (maksimal 3 bar setelah width breakout).
2. **Lokasi likuiditas** — target TP2 di band berlawanan saat expansion.
3. **Konfluensi ekstrem** — sweep harus terjadi di/dekat band (jarak ≤ 0.25 × ATR14 H1).
4. **Konfirmasi ORB** — squeeze H1 sebelum session open = probabilitas breakout lebih tinggi
   (lihat §9 Setup B).

---

## 3. Modul B — SMC/ICT

### 3.1 Swing / Pivot

```
pivot_high(i) jika high[i] > high[i±1..i±k], k = 3
pivot_low(i)  jika low[i]  < low[i±1..i±k],  k = 3
```
Pivot baru dikonfirmasi 3 bar setelah terjadi (tidak repaint setelah itu).

### 3.2 Liquidity Pool (EQH / EQL)

Dua pivot sejenis dianggap **equal** jika selisih harga ≤ `0.10 × ATR14`.
Cluster dengan ≥ 2 pivot = EQH (buy-side liquidity) atau EQL (sell-side liquidity).
Level ini adalah **target** (TP) dan **magnet** (setup sweep).

Tambahan dari konvensi `SMC-Marking`:
- Simpan `count` (jumlah pivot dalam cluster) — makin banyak, makin kuat.
- Tandai level yang sudah "swept" (wick menembus lalu close balik) dan hapus setelah 1× swept
  atau setelah 100 bar.

### 3.3 Sweep (stop run / liquidity grab)

Bullish sweep (untuk long):
```
low[t]   < level_low  - 0.05 * ATR14
close[t] > level_low
volume[t] >= 1.0 * SMA(volume, 20)          # opsional, menambah confidence
```
Ini inti ICT "judas swing": wick menembus likuiditas lalu ditolak dalam satu candle.

### 3.4 Struktur: Major vs Internal

Penting (diambil dari terminologi `SMC-Marking`): pisahkan **major** dan **internal**.

| Tipe | Pivot | Fungsi |
|---|---|---|
| **Major** (swing) | k = 5 | menentukan bias, BOS/CHoCH major |
| **Internal** | k = 2 | menentukan trigger entry M15 (iCHoCH / MBOS) |

- **BOS** — close melewati swing terakhir *searah* tren → kontinuitas.
- **CHoCH** — close melewati swing terakhir *berlawanan* tren → potensi pembalikan.
- **iCHoCH** (internal CHoCH) — CHoCH pada struktur internal, dipakai sebagai **trigger**.
- **MBOS** (minor BOS) — BOS internal, dipakai untuk konfirmasi kelanjutan.

Aturan pakai:
```
bias     : CHoCH/BOS MAJOR pada H4
entry    : iCHoCH pada M15 setelah sweep  (bukan major)
invalidasi setup : close M15 menembus swing major berlawanan arah
```

### 3.5 Displacement

```
body = abs(close - open)
displacement = body >= 1.2 * ATR20
```
Tanpa displacement, CHoCH/iCHoCH diabaikan.

### 3.6 Fair Value Gap (FVG / imbalance)

Bullish FVG pada 3 candle (`c1, c2, c3`):
```
gap_low  = high[c1]
gap_high = low[c3]
valid jika gap_high > gap_low + 0.15 * ATR14
```
Zona FVG = `[gap_low, gap_high]`. Entry di 50% FVG (consequent encroachment).

**Partial fill tracking** (dari `SMC-Marking`):
```
filled_pct = (gap_high - min(low_sejak_terbentuk)) / (gap_high - gap_low)
- filled_pct < 0.5  → zona valid
- 0.5..1.0          → zona lemah, confidence -10
- >= 1.0            → hapus zona (gap filled)
```

### 3.7 OTE (Optimal Trade Entry)

```
leg      = impulse_high - impulse_low
ote_low  = impulse_high - 0.786 * leg
ote_high = impulse_high - 0.620 * leg
```
Entry ideal = irisan **FVG ∩ OTE ∩ discount** (untuk long).

### 3.8 Premium / Discount

```
dealing_range = last_major_swing_high - last_major_swing_low
eq            = 0.5 * dealing_range
long  hanya jika harga <= eq (discount)
short hanya jika harga >= eq (premium)
```

### 3.9 Order Block (OB) + Mitigation

Definisi (diambil dari `quantumalgo-official/smart-money-concepts-indicator`):
> *"the last opposing candle before a strong, structure-breaking move"*

```
Bullish OB:
  cari candle bearish terakhir sebelum displacement bullish
  yang menyebabkan BOS/CHoCH (close melewati swing)
  zona = [low(candle), max(open(candle), close(candle))]

Bearish OB: mirror
```

Aturan pemakaian:
- OB harus **fresh** (belum pernah disentuh harga setelah terbentuk).
- OB + FVG yang overlap = zona entry prioritas tertinggi.
- **Mitigation**: setelah harga masuk zona dan terjadi reaksi (close balik keluar searah),
  OB dianggap termitigasi → hapus (sesuai `SMC-Marking`).
- OB yang sudah termitigasi **tidak boleh** dipakai dua kali.
- Entry di OB: 50% zona (mid), bukan di tepi.

### 3.10 Breaker Block (opsional, fase 6)

OB yang gagal (harga menembus zona) berubah menjadi *breaker* — supply menjadi demand
atau sebaliknya. Dipakai sebagai zona re-entry alternatif. **Jangan** implementasikan
sebelum backtest dasar stabil; ini menambah kompleksitas tanpa bukti edge tambahan.

---

## 4. Bias H4 (menentukan arah)

Hitung skor -3..+3:

| Faktor | +1 | -1 |
|---|---|---|
| Struktur H4 (major) | HH+HL (uptrend) | LH+LL (downtrend) |
| Posisi di range H4 | discount (<50%) | premium (>50%) |
| %B H4 | < 0.2 | > 0.8 |

- `score >= +2` → **BULLISH** (hanya cari long)
- `score <= -2` → **BEARISH** (hanya cari short)
- selain itu → **NEUTRAL** → **tidak ada trade**

---

## 5. Setup A — Sweep Reversal (state machine)

```
                 ┌──────────────────────────────┐
                 │            IDLE              │
                 └──────────────┬───────────────┘
   H1 SQUEEZE + harga di band ekstrem + liquidity pool dalam 0.2×ATR
                                ▼
                 ┌──────────────────────────────┐
                 │           ARMED              │
                 │  (simpan: side, level, ts)   │
                 └──────────────┬───────────────┘
   M15: sweep + iCHoCH + displacement + (FVG | fresh OB)
                                ▼
                 ┌──────────────────────────────┐
                 │         TRIGGERED            │
                 │  (hitung entry/SL/TP/RR)     │
                 └──────────────┬───────────────┘
   gate lolos (bias, regime, blackout, session, RR, dedupe)
                                ▼
                 ┌──────────────────────────────┐
                 │          ALERTED             │
                 └──────────────┬───────────────┘
   TP1/SL tersentuh, atau 32 bar M15 tanpa progres
                                ▼
                 ┌──────────────────────────────┐
                 │  CLOSED / EXPIRED            │
                 └──────────────────────────────┘
```

Invalidasi ARMED:
- 32 bar M15 tanpa trigger
- close menembus level sweep > 1.0×ATR berlawanan arah
- bias H4 berubah berlawanan
- masuk blackout news high-impact
- regime berubah menjadi `VOLATILE` (lihat §10)

### 5.1 Entry / SL / TP

```
long:
  sweep_low = low terendah candle sweep
  SL    = min(sweep_low, OB_low) - 0.15 * ATR14(M15)
  entry = 50% FVG (fallback: mid OB, fallback: midpoint OTE)
  risk  = entry - SL
  TP1   = entry + 1.0 * ATR14(H1)
  TP2   = liquidity pool berikutnya / band atas H1 (pilih terdekat)
  RR    = (TP1 - entry) / risk      → wajib >= 1.5
short: mirror
```

### 5.2 Filter Sesi (UTC)

| Sesi | UTC | WIB |
|---|---|---|
| London killzone | 07:00 – 10:00 | 14:00 – 17:00 |
| New York killzone | 12:00 – 15:00 | 19:00 – 22:00 |
| Gold daily break | 21:00 – 22:00 | 04:00 – 05:00 |
| Weekend | Jum 21:00 – Ming 22:00 | — |

### 5.3 Cooldown & Dedupe

```
cooldown: satu arah maksimal 1 alert per 4 jam (16 bar M15)
daily cap: maksimal 3 sinyal per hari (semua setup)
dedupe key: sha1(symbol|setup|side|tf|trigger_candle_ts)
```

---

## 6. Contoh Numerik (Setup A)

Asumsi ilustratif: H4 uptrend, harga discount, H1 squeeze, ATR14(M15)=4.20, ATR20=4.00.

```
Liquidity low terakhir          = 4108.50
Candle M15 sweep: low=4106.10, close=4109.80, body=4.60
  → low < 4108.50 - 0.05*4.20 = 4108.29 ✓
  → close > 4108.50 ✓
iCHoCH: close 4113.90 > internal swing high 4112.60, body=4.90 >= 1.2*4.00=4.80 ✓
FVG bullish: high[c1]=4112.00, low[c3]=4113.40 → gap 1.40 >= 0.15*4.20=0.63 ✓
Bullish OB overlap FVG → zona prioritas
Entry = 50% FVG = 4112.70
SL    = min(4106.10, OB_low 4110.90) - 0.63 = 4105.47
Risk  = 7.23
TP1   = 4112.70 + 1.0*ATR14(H1=12.50) = 4125.20      RR = 1.73 ✓
TP2   = 4134.00 (EQH H1)                             RR = 2.94
```

---

## 7. Confidence Score (0–100)

| Komponen | Poin |
|---|---|
| Bias H4 kuat (score ±3) | 20 |
| Bias H4 sedang (±2) | 12 |
| Squeeze persentil < 10 | 12 |
| Sweep + close rejection tegas (body > 50% range candle) | 12 |
| Displacement > 1.5×ATR | 12 |
| FVG size > 0.3×ATR | 8 |
| Fresh OB overlap FVG/OTE | 8 |
| Entry di irisan OTE ∩ FVG | 8 |
| Bias makro searah | 8 |
| Regime sesuai (TRENDING untuk ORB / RANGING untuk sweep) | 8 |
| Di luar killzone | −20 |
| Event medium-impact < 2 jam | −10 |
| FVG sudah >50% filled | −10 |

- `>= 70` → **ENTRY ALERT**
- `50–69` → **WATCHLIST**
- `< 50` → log saja

Threshold dinamis (dari `xaubot-ai`, *dynamic confidence*):
```
regime == VOLATILE  → threshold +10 (lebih ketat)
regime == TRENDING  → threshold -0 untuk setup searah
setelah 2 loss beruntun → threshold +5 sampai 1 win
```

---

## 8. Anti-Pattern

1. ❌ Sell hanya karena harga menyentuh band atas.
2. ❌ Entry tanpa sweep (untuk Setup A).
3. ❌ Entry melawan bias H4.
4. ❌ Trade saat NEUTRAL.
5. ❌ Menggeser SL setelah entry.
6. ❌ Averaging down.
7. ❌ Alert saat blackout news.
8. ❌ Memakai ulang OB yang sudah termitigasi.
9. ❌ Memakai CHoCH major sebagai trigger entry (terlalu lambat).
10. ❌ Trade ORB saat regime `VOLATILE` tanpa squeeze.

---

## 9. Setup B — Session Opening Range Breakout (ORB)

Diadaptasi dari `yulz008/GOLD_ORB`, tapi **tidak** memakai "jam server" — memakai UTC
dan **disaring BB squeeze** supaya tidak bertabrakan dengan Setup A.

### 9.1 Definisi Range

| Parameter | Nilai default |
|---|---|
| Window 1 (London) | 07:00 – 08:00 UTC |
| Window 2 (New York) | 12:00 – 13:00 UTC *(atau 13:30–14:30 saat DST)* |
| Min konsolidasi sebelum breakout | 3 candle M15 di dalam range |
| Valid until | akhir killzone (10:00 / 15:00 UTC) |

```
range_high = max(high) selama window
range_low  = min(low)  selama window
range_ok   = (count candle yang close di dalam range setelah window) >= 3
```

### 9.2 Kondisi Entry

```
Prasyarat:
  H1 SQUEEZE minimal 5 bar sebelum session open     # kompresi → ekspansi
  regime != VOLATILE
  tidak ada event high-impact dalam blackout

Long:
  close M15 > range_high + 0.10*ATR14
  retest ke range_high (toleransi 0.15*ATR14) atau OB/FVG di atas range
  close balik ke atas → entry
SL   = range_midpoint (bukan bawah range — lebih ketat) atau low retest - 0.15*ATR
TP1  = entry + range_size (1.0×R)
TP2  = EQH berikutnya / band atas H1
RR minimal 1.5

Short: mirror
```

### 9.3 Perbedaan dengan Setup A

| Aspek | Setup A (Sweep Reversal) | Setup B (ORB) |
|---|---|---|
| Arah | melawan sweep (mean reversion) | searah breakout (momentum) |
| Regime ideal | RANGING / SQUEEZE | TRENDING setelah squeeze |
| Entry | FVG/OTE retrace | retest range / OB |
| Invalidasi | close tembus sweep level | close balik ke dalam range |
| Frekuensi | lebih sering | 1–2 per sesi maksimal |

### 9.4 Mengapa dua setup

Satu setup saja akan mati di regime yang salah. Sweep reversal unggul di range; ORB unggul
saat ekspansi tren. Dengan memisahkan keduanya dan menambahkan regime layer, sistem tidak
dipaksa "memaksa" satu logika di semua kondisi — ini penyebab utama kurva equity patah.

---

## 10. Regime Layer

Diambil dari gagasan `xaubot-ai` (HMM 3-state), tapi **dimulai rule-based** dulu.

### 10.1 Klasifikasi Rule-Based (v1)

Hitung pada H1, window 100 bar:

```
atr_pct      = ATR14 / close * 100
atr_rank     = percentrank(ATR14, 100)
bbw_rank     = percentrank(BandWidth, 100)
adx          = ADX(14)
slope_ema50  = (EMA50[-1] - EMA50[-10]) / ATR14

if atr_rank >= 80 and bbw_rank >= 70        → VOLATILE
elif adx >= 25 and abs(slope_ema50) >= 0.5  → TRENDING
else                                        → RANGING
```

### 10.2 Peta Regime → Setup

| Regime | Setup A (sweep) | Setup B (ORB) | Catatan |
|---|---|---|---|
| RANGING | ✅ prioritas | ⛔ suppress | paling umum di Asia/pre-London |
| TRENDING | ⚠️ hanya pullback ke OB | ✅ prioritas | jangan lawan tren |
| VOLATILE | ⛔ suppress | ⛔ suppress | spread melebar, news, gap |

`VOLATILE` juga memaksa `SL` lebih lebar? **Tidak** — lebih baik tidak trade.

### 10.3 Upgrade HMM (fase 6, opsional)

```
fitur HMM (2 fitur cukup): log_return, atr_pct   (window 500 bar H1)
states: 3, covariance: full, random_state=42
mapping state → {trending, ranging, volatile} berdasarkan mean atr_pct & mean return
refit: bulanan (bukan tiap hari)
```

Aturan: HMM **tidak boleh** menggantikan rule-based sampai terbukti lebih baik di
out-of-sample. Simpan kedua label di DB (`regime_rule`, `regime_hmm`) dan bandingkan
akurasi klasifikasi terhadap label manual 200 bar.

### 10.4 Feature Set untuk ML (fase 7, opsional)

Jika nanti mau meniru pendekatan `xaubot-ai` (37 fitur), kelompok fitur yang masuk akal:

| Grup | Contoh fitur |
|---|---|
| BB | %B, BandWidth, BW rank, jarak close ke band (ATR-normalized) |
| SMC | jumlah FVG aktif, jarak ke OB terdekat, arah struktur (major/internal), status sweep |
| Volatilitas | ATR, ATR rank, true range, gap |
| Sesi | jam UTC (cyclical), sesi aktif, menit sejak open |
| Makro | bias score, DXY 5d return, real yield 5d delta |
| Kalender | menit ke event high-impact berikutnya, ada event hari ini |

ML **hanya** dipakai sebagai *veto* (menurunkan confidence), bukan generator sinyal,
sampai ada bukti out-of-sample. Jangan biarkan model menjadi black box arah trade.

---

## 11. Filter Stack (12 Filter Wajib)

Terinspirasi "14 entry filters" di `xaubot-ai`; versi kita:

| # | Filter | Tipe | Efek jika gagal |
|---|---|---|---|
| 1 | Bias H4 tidak berlawanan | blocking | suppress |
| 2 | Regime cocok dengan setup | blocking | suppress |
| 3 | Killzone aktif (kecuali mode 24/7) | soft | confidence −20 |
| 4 | Bukan blackout news high-impact | blocking | suppress |
| 5 | RR ≥ 1.5 | blocking | suppress |
| 6 | Sweep valid (Setup A) / range valid (Setup B) | blocking | suppress |
| 7 | Displacement ≥ 1.2×ATR | blocking | suppress |
| 8 | FVG/OB belum termitigasi | blocking | suppress |
| 9 | Fresh OB atau FVG ≥ 0.15×ATR | blocking | suppress |
| 10 | Cooldown 4 jam & daily cap 3 | blocking | suppress |
| 11 | Basis PAXG vs spot < 1% | soft | confidence −10 |
| 12 | Data segar (< 3 bar) | blocking | suppress + alert sistem |

Semua `suppress` **wajib** dicatat alasannya (`reason`) untuk audit mingguan.

---

## 12. Alignment dengan Referensi Open-Source

| Konsep di dokumen ini | Sumber ide | Lisensi | Cara pakai |
|---|---|---|---|
| Definisi Order Block + mitigation | `quantumalgo-official/smart-money-concepts-indicator` | MIT | boleh adaptasi kode, sertakan atribusi |
| Terminologi BMS/iCHoCH/EQH/EQL, partial fill FVG | `kxngHADES/SMC-Marking` | no license | **konsep saja**, jangan salin kode |
| HMM regime + dynamic confidence + filter stack | `GifariKemal/xaubot-ai` | MIT | adaptasi ide, tulis ulang implementasi |
| ORB window + konsolidasi 3 candle | `yulz008/GOLD_ORB` | no license | **konsep saja**, jangan salin kode |
| Backtest-live parity (engine sama) | `francomascareloai/EA_SCALPER_XAUUSD` | NOASSERTION | ide arsitektur |
| Pine v6 SMC suite | `Ahmed-GoCode/Quant-Edge-Indicators` | MPL-2.0 | boleh pakai dengan kewajiban file-level copyleft |

Detail lengkap + aturan atribusi: `10-referensi-opensource.md`.

---

## 14. Two-Stage Entry (v1.4)

Setup M15 **bukan** perintah entry. Ia adalah *armed state* yang menunggu konfirmasi M5.

```
ARMED (setup terkirim, belum entry)
  konfirmasi M5:
    1. close berada di zona [zone_low - 0.10 ATR, zone_high + 0.10 ATR]
    2. body candle >= 0.40 ATR(M5)
    3. micro sweep: low <= min(low[-6:-1]) dan close kembali di atasnya (long)
       (short: mirror pada high)
    4. micro BOS: close > high[-2] (long) / < low[-2] (short)
    5. entry = close, SL = min(armed.sl, low - 0.10 ATR)
    6. RR dihitung ulang terhadap TP1; wajib >= 1.2
  tolak jika close > zone_high + 0.15 ATR (chase)
  cancel jika close menembus armed.sl
  expire setelah 120 menit
```

Tujuan: entry lebih dekat ke invalidasi sehingga loss per trade lebih kecil, **tanpa**
mengejar harga. Trade-off: sebagian setup tidak terisi (missed), dan M5 bisa whipsaw.
Keduanya harus diukur di backtest M5 sebelum dipercaya (lihat `08`).

---

## 13. Session Layer (v1.2)

Semua kalkulasi internal **UTC**; WIB hanya untuk tampilan. Indonesia tidak memakai DST,
tetapi London/New York memakai — jadwal WIB bergeser 1 jam saat DST.

### 13.1 Tabel Sesi

| Sesi | UTC (musim panas) | UTC (musim dingin) | WIB (musim panas) | WIB (musim dingin) | Kualitas untuk gold |
|---|---|---|---|---|---|
| Sydney | 21:00–06:00 | 22:00–07:00 | 04:00–13:00 | 05:00–14:00 | ❌ tipis, skip |
| **Asia / Tokyo** | 00:00–09:00 | 00:00–09:00 | **07:00–16:00** | 07:00–16:00 | ⚠️ range forming, bukan entry |
| **London** | 07:00–16:00 | 08:00–17:00 | **14:00–23:00** | 15:00–00:00 | ✅ prioritas |
| **New York** | 12:00–21:00 | 13:00–22:00 | **19:00–04:00** | 20:00–05:00 | ✅ prioritas |
| **Overlap LDN+NY** | 12:00–16:00 | 13:00–17:00 | **19:00–23:00** | 20:00–00:00 | ⭐ likuiditas tertinggi |
| Daily break | 21:00–22:00 | 22:00–23:00 | 04:00–05:00 | 05:00–06:00 | ❌ hard block |
| Weekend | Jum 21:00 → Ming 22:00 | Jum 22:00 → Ming 23:00 | Sab 04:00 → Sen 05:00 | Sab 05:00 → Sen 06:00 | ❌ tutup |

### 13.2 Jam Terbaik untuk Anda (WIB)

| Slot WIB | Sesi | Aksi |
|---|---|---|
| 07:00–12:00 | Asia | **Observasi**: catat Asian range, tidak entry |
| 12:00–14:00 | Pre-London | Siapkan level, cek digest |
| **14:00–17:00** | London open | Entry Setup A / ORB London |
| 17:00–19:00 | London mid | Entry Setup A (selektif) |
| **19:00–23:00** | Overlap + NY open | ⭐ **prime time** — prioritas tertinggi |
| 23:00–01:00 | NY mid | Selektif, kurangi size (menjelang penutupan) |
| 01:00–04:00 | NY late | Hindari entry baru |
| 04:00–05:00 | Daily break | ❌ matikan |
| Sab 04:00 – Sen 05:00 | Weekend | ❌ matikan |

**Rekomendasi praktis:** jadwal trading utama **19:00–23:00 WIB** (overlap), sekunder
**14:00–17:00 WIB** (London open). Sistem tetap berjalan 24/5, tapi alert entry
di-suppress di luar dua slot itu.

### 13.3 Asian Range sebagai Likuiditas (ICT)

Range Asia (00:00–07:00 UTC / 07:00–14:00 WIB) dipakai London sebagai target stop-run:

```
asian_high = max(high) 00:00–07:00 UTC
asian_low  = min(low)  00:00–07:00 UTC
```
- Tambahkan `asian_high/low` ke daftar liquidity pool (bobot sama dengan EQH/EQL).
- Sweep Asian high/low pada jam London = setup prioritas (judas swing klasik).
- Jika London sudah sweep Asian range dan gagal reclaim dalam 2 bar M15 → bias harian
  mengikuti arah sweep.

### 13.4 Penanda Sesi di Engine

```python
def session_label(ts_utc: datetime) -> str:
    h = ts_utc.hour
    if h < 7:   return "asia_late"      # 00-07 UTC
    if h < 10:  return "london_open"    # 07-10 (killzone)
    if h < 12:  return "london_mid"
    if h < 15:  return "overlap"        # 12-15 (killzone)
    if h < 16:  return "ny_open"        # 15-16
    if h < 21:  return "ny"
    return "break"                      # 21-22 hard block
```

`overlap` mendapat `session_score = 3`, `london_open`/`ny_open` = 2, lainnya = 1.
`session_score` masuk ke confidence (+5 untuk 3).

### 13.5 Penyesuaian jadwal digest (WIB)

| Digest | Waktu lama | Waktu baru |
|---|---|---|
| Daily briefing | 07:00 | **12:00** (sebelum London open) |
| Pre-London | 13:00 | **13:30** |
| Pre-NY | 19:00 | **18:30** |
| Recap | 05:00 | 05:30 |
