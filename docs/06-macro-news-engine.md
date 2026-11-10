# 06 — Macro & News Engine

Tujuan: mengubah data makro + berita menjadi **satu angka bias** (-100..+100) dan
**kalender blackout**, lalu dipakai sebagai gate pada sinyal teknikal.

Prinsip: **teknikal menentukan timing, makro menentukan izin.** Keduanya harus searah,
atau minimal makro tidak menolak.

---

## 1. Arsitektur Modul

```
macro/
├── calendar.py   # FF JSON → list[Event], blackout windows
├── fred.py       # DFII10, DTWEXBGS (atau yfinance DX-Y.NYB, ^TNX)
├── news.py       # GDELT + Google News → list[Headline]
├── bias.py       # skoring → BiasReport
└── digest.py     # render pesan harian
```

Keluaran:

```python
@dataclass
class BiasReport:
    score: int              # -100..100
    label: str              # BULLISH_STRONG | BULLISH | NEUTRAL | BEARISH | BEARISH_STRONG
    factors: dict[str, float]
    as_of: datetime
    stale: bool

@dataclass
class CalendarEvent:
    title: str
    currency: str           # USD
    impact: str             # High | Medium | Low
    ts_utc: datetime
    forecast: str
    previous: str
```

---

## 2. Faktor Makro & Bobot

Total bobot = 100. Skor tiap faktor ∈ [-1, +1], kontribusi = `bobot × skor`.

| # | Faktor | Bobot | Sumber | Logika |
|---|---|---|---|---|
| 1 | Real yield 10Y (DFII10) | 25 | FRED | turun → gold naik |
| 2 | US Dollar Index | 20 | yfinance `DX-Y.NYB` / FRED | turun → gold naik |
| 3 | Ekspektasi Fed (fed funds futures / DFF trend) | 15 | FRED `DFEDTARU` + berita | dovish → gold naik |
| 4 | Inflasi (breakeven T10YIE) | 10 | FRED | naik → gold naik (hedge) |
| 5 | Risiko geopolitik / risk-off | 15 | GDELT tone + headline | naik → gold naik |
| 6 | Central bank buying | 10 | berita WGC (manual/semi) | naik → gold naik |
| 7 | ETF flow (GLD holdings) | 5 | halaman SPDR | inflow → gold naik |

### 2.1 Cara hitung skor per faktor

**Real yield (bobot 25):**
```
delta5 = dfii10.today - dfii10.5_hari_lalu
skor = clip(-delta5 / 0.15, -1, 1)      # -15 bps dalam 5 hari = +1 penuh untuk gold
```

**Dollar index (bobot 20):**
```
ret5 = (dxy.today / dxy.5_hari_lalu - 1) * 100
skor = clip(-ret5 / 1.0, -1, 1)         # dolar turun 1% = +1
```

**Fed path (bobot 15):**
- Jika headline dominan = "rate cut / dovish / disinflation" → +1
- "rate hike / hawkish / sticky inflation" → -1
- Ambigu → 0
- Implementasi awal: keyword scoring (lihat §4), lalu upgrade ke manual override.

**Breakeven (bobot 10):**
```
delta = t10yie.today - t10yie.20_hari_lalu
skor = clip(delta / 0.20, -1, 1)
```

**Geopolitik (bobot 15):**
```
gdelt_tone = rata-rata tone artikel 24 jam (negatif = risk-off)
skor = clip(-gdelt_tone / 5, 0, 1)      # hanya sisi positif untuk gold
+ boost jika ada keyword perang/sanksi/krisis (maks +0.5)
```

**CB buying (bobot 10):** update manual mingguan dari berita WGC; bisa 0 jika tidak ada info.
**ETF flow (bobot 5):** `delta_ton_7d / 5`, clip -1..1.

### 2.2 Label

```
score >= +50  → BULLISH_STRONG
+20 .. +49    → BULLISH
-19 .. +19    → NEUTRAL
-49 .. -20    → BEARISH
<= -50        → BEARISH_STRONG
```

### 2.3 Efek pada sinyal

| Bias | Long | Short |
|---|---|---|
| BULLISH_STRONG | lolos, confidence +10 | suppress |
| BULLISH | lolos | suppress |
| NEUTRAL | lolos (confidence tanpa bonus) | lolos |
| BEARISH | suppress | lolos |
| BEARISH_STRONG | suppress | lolos, confidence +10 |
| `stale` (data > 48 jam) | confidence −20, kirim warning | idem |

---

## 3. Kalender Ekonomi (blackout)

### 3.1 Ingestion

```python
r = httpx.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=15)
events = [CalendarEvent(
    title=e["title"], currency=e["country"], impact=e["impact"],
    ts_utc=datetime.fromisoformat(e["date"]).astimezone(timezone.utc),
    forecast=e.get("forecast",""), previous=e.get("previous",""),
) for e in r.json()]
```

Penting: `date` dari FF memakai offset New York → **selalu** `.astimezone(UTC)`.

Refresh tiap 6 jam; simpan ke `data/calendar.parquet`.

### 3.2 Blackout Window

```
blackout_start = ts_utc - 30 menit
blackout_end   = ts_utc + 30 menit
```

Dipakai untuk:
- `High` + `USD` → **blokir semua entry alert**
- `Medium` + `USD` → confidence −10 jika event < 2 jam
- `High` + non-USD (mis. CNY) → confidence −5

### 3.3 Fail-closed rule

```python
if calendar_age_hours > 24:
    raise DataUnavailable("calendar stale")
    # engine masuk mode DEGRADED: tidak kirim entry alert, kirim alert sistem
```

### 3.4 Event gold-specific yang wajib dipantau

| Event | Jadwal | Dampak |
|---|---|---|
| CPI / Core CPI | bulanan | sangat tinggi |
| NFP (Non-Farm Payrolls) | Jumat pertama | sangat tinggi |
| FOMC + press conference | 8×/tahun | ekstrem |
| PCE Price Index | bulanan | tinggi |
| Jobless Claims | Kamis mingguan | medium |
| Fed officials speeches | acak | medium |
| US 10Y & 30Y bond auctions | mingguan | medium |
| GDP / Retail Sales / ISM | bulanan | medium |

---

## 4. News Engine (GDELT + Google News)

### 4.1 Query utama

```python
GDELT = ("https://api.gdeltproject.org/api/v2/doc/doc"
         "?query=(gold%20OR%20XAUUSD%20OR%20%22real%20yield%22%20OR%20FOMC)"
         "%20sourcelang:english"
         "&mode=artlist&maxrecords=50&format=json&timespan=24h")
```

Google News RSS (beberapa query paralel):

```
gold price fed
XAUUSD forecast
central bank gold buying
gold ETF flows
```

### 4.2 Keyword scoring (baseline, tanpa LLM)

```python
BULLISH = ["rate cut","dovish","inflation rises","safe haven","central bank buying",
           "etf inflow","war","sanctions","recession","stimulus","weak dollar",
           "growing concern","risk aversion"]
BEARISH = ["rate hike","hawkish","strong dollar","etf outflow","profit taking",
           "risk-on","yields rise","tapering","inflation cools","demand drops"]

def headline_score(title: str) -> int:
    t = title.lower()
    b = sum(1 for k in BULLISH if k in t)
    s = sum(1 for k in BEARISH if k in t)
    return max(-1, min(1, b - s))
```

Dedupe headline: `sha1(normalized_title)`; bobot turun bila domain sama muncul berulang
(cluster → satu suara).

### 4.3 Upgrade opsional (fase 6)

- Ganti keyword scoring dengan LLM lokal/remote: prompt → output JSON
  `{"sentiment": -1..1, "category": "...", "relevance": 0..1}`.
- Simpan hasil di `data/news_scored.parquet` untuk audit.
- Jangan pernah biarkan LLM mengubah arah sinyal secara langsung — hanya menggeser skor
  maksimal ±10 poin.

---

## 5. Digest Harian (07:00 WIB)

Isi wajib:
1. Bias + faktor breakdown (tabel miring/naik)
2. Harga spot + basis PAXG
3. H4 range & posisi harga (premium/discount)
4. Agenda hari ini (WIB) dengan penanda HIGH
5. Top 3–5 headline (dedupe, dari domain berbeda)
6. Catatan blackout window hari ini

Template lengkap: lihat `05-telegram-bot.md §3.3`.

Jadwal tambahan:
- **13:00 WIB** — pre-London briefing singkat (bias + 3 level kunci).
- **19:00 WIB** — pre-NY briefing (cek apakah bias berubah setelah data pagi).
- **05:00 WIB** — recap harian: sinyal dikirim, suppressed, hasil (jika ada).

---

## 6. Skema Penyimpanan

```sql
CREATE TABLE macro_scores (
  ts TEXT PRIMARY KEY,
  score INTEGER, label TEXT,
  dxy REAL, real_yield REAL, t10yie REAL,
  gdelt_tone REAL, factors_json TEXT
);

CREATE TABLE news_items (
  id TEXT PRIMARY KEY,        -- sha1(title)
  ts TEXT, title TEXT, url TEXT, domain TEXT,
  score INTEGER, category TEXT
);

CREATE TABLE calendar_events (
  id TEXT PRIMARY KEY,        -- sha1(title|date)
  ts_utc TEXT, title TEXT, currency TEXT,
  impact TEXT, forecast TEXT, previous TEXT
);
```

---

## 7. Contoh Perhitungan

```
DFII10      1.84%  (5 hari lalu 1.90%)  delta=-0.06 → skor -(-0.06/0.15)= +0.40 → 25×0.40 = +10.0
DXY         103.2  (5 hari lalu 104.0)  ret=-0.77%  → skor +0.77      → 20×0.77 = +15.4
Fed path    headline dovish dominan 3:1                                  → 15×+0.5 = +7.5
T10YIE      2.28%  (20 hari lalu 2.24%) propia +0.04                     → 10×0.20 = +2.0
GDELT tone  -1.8                                                          → 15×0.36 = +5.4
CB buying   WGC: +monthly record                                          → 10×+1.0 = +10.0
ETF flow    GLD +1.2 ton / 5 hari                                         → 5×0.24  = +1.2
──────────────────────────────────────────────────────────────────────
TOTAL                                                                     ≈ +51.5
→ BULLISH_STRONG (long diizinkan, short di-suppress)
```

---

## 8. Checklist Implementasi

- [ ] Parser FF dengan konversi timezone benar (uji dengan event 08:30 −05:00 → 13:30 UTC)
- [ ] Blackout window unit test (event tepat di batas ±30 menit)
- [ ] FRED/yfinance fallback saat API key tidak ada
- [ ] GDELT timeout tidak memblokir seluruh siklus (jalankan async, cache 15 menit)
- [ ] Keyword scoring punya test case minimal 20 headline
- [ ] Digest tidak pernah kosong (fallback "tidak ada berita signifikan")
- [ ] `stale` detection diuji dengan memalsukan timestamp

---

## 9. Perlindungan News Mendadak (v1.5)

Tiga lapis, dari yang pasti ke yang reaktif:

### 9.1 Blackout terjadwal (sudah ada)

- Sumber: ForexFactory JSON (`impact = High`, `currency = USD`)
- Jendela: **±30 menit** (`news.blackout_minutes`)
- Efek: entry baru **dan** konfirmasi armed diblokir. Setup yang sedang ARMED tetap
  menunggu (tidak cancel) sampai jendela lewat atau kedaluwarsa.

### 9.2 Peringatan pre-news (baru)

- `news.pre_news_warn_minutes: 15`
- Jika ada event High USD dalam 15 menit **dan** ada posisi terbuka/armed →
  kirim satu warning (dedupe per event) agar Anda bisa menutup/mengurangi posisi
  sebelum rilis. Tidak menutup posisi otomatis.

### 9.3 Spike guard untuk news tak terjadwal (baru)

Tidak ada kalender untuk geopolitik/tweet mendadak. Deteksinya dari harga:

```
median_range = median(high-low, 14 bar M1)
range_ratio  = range_bar_terakhir / median_range
body_ratio   = |close-open| / median_range
SPIKE jika range_ratio >= 3.0  atau body_ratio >= 2.5
```

Efek saat spike:
- entry baru **tidak** di-arm
- konfirmasi armed **ditahan** (cancel/expiry tetap jalan)
- warning dikirim maksimal 1× per 15 menit

### 9.4 Batasan yang harus dipahami

| Klaim | Kenyataan |
|---|---|
| "Menghindari news" | Hanya news **terjadwal** yang bisa dicegah; spike guard bereaksi **setelah** candle anomali terbentuk |
| "SL aman saat news" | Tidak. Spread gold bisa melebar 3–10× dan SL bisa slip jauh dari level |
| "Cegah margin call" | Bukan tugas alert. Yang mencegah: leverage rendah, risk 0.25–0.5%/trade, maks 1–2 posisi |
| Posisi terbuka saat spike | Hanya dikirim warning; **tidak** ditutup otomatis |

### 9.5 Checklist operasional

- [ ] Selalu cek digest 12:00 WIB untuk agenda hari ini
- [ ] Jangan menahan posisi melewati High-impact (CPI/NFP/FOMC)
- [ ] Gunakan leverage efektif ≤ 1:20 untuk gold
- [ ] Aktifkan notifikasi Telegram (jangan mute) saat ada posisi
- [ ] Jika spike guard berbunyi saat posisi terbuka: kurangi/tutup, jangan tambah
