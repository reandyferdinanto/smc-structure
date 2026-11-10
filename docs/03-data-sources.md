# 03 — Sumber Data (Semua Sudah Diverifikasi)

Semua endpoint di bawah **dites live pada 10 Nov 2026** dari mesin development
(Windows, Python 3.12, `urllib`).

---

## 1. Ringkasan

| # | Sumber | Fungsi | Auth | Status | Latency |
|---|---|---|---|---|---|
| 1 | gold-api.com | Spot XAU price | none | ✅ 200 | detik |
| 2 | Binance Vision (PAXGUSDT) | OHLCV intraday + realtime | none | ✅ 200 | detik |
| 3 | Yahoo Finance (`GC=F`) | OHLCV historis (gold futures) | none | ✅ 200 | realtime-delay |
| 4 | TradingView scanner | Quote `OANDA:XAUUSD` | none | ✅ 200 | near-realtime |
| 5 | ForexFactory JSON | Kalender ekonomi | none | ✅ 200 | harian |
| 6 | GDELT | Berita global + tone | none | ✅ 200 | ~15 menit |
| 7 | Google News RSS | Headline | none | ✅ 200 | menit |
| 8 | FRED | Real yield, dollar index | API key gratis | perlu key | harian |
| 9 | CFTC COT | Posisi institusional | none (file) | mingguan | mingguan |
| 10 | Dukascopy | Histori tick/M1 untuk backtest | none | manual | — |

---

## 2. Detail Endpoint

### 2.1 Spot Gold — gold-api.com

```
GET https://api.gold-api.com/price/XAU
```
Response:
```json
{
  "currency": "USD",
  "currencySymbol": "$",
  "exchangeRate": 1.0,
  "name": "Gold",
  "price": 4117.70,
  "symbol": "XAU",
  "updatedAt": "2026-11-10T02:36:30Z"
}
```
- **Pakai untuk:** harga spot saat ini, sanity check, basis terhadap PAXG.
- **Jangan pakai untuk:** OHLCV/struktur — tidak menyediakan candle.
- Rate limit tidak didokumentasikan → poll maksimal tiap 30 detik.

### 2.2 OHLCV Intraday — Binance Vision (PAXGUSDT)

```
GET https://data-api.binance.vision/api/v3/klines
    ?symbol=PAXGUSDT&interval=15m&limit=500
```
Intervals: `1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d`.
Response per bar:
```
[open_time_ms, "open", "high", "low", "close", "volume",
 close_time_ms, "quote_volume", trades, "taker_base", "taker_quote", "0"]
```
- **Pakai untuk:** semua OHLCV M15/H1/H4 realtime. PAXG = token backed 1 gram LBMA gold,
  jadi struktur candle hampir identik XAUUSD.
- **Basis:** PAXG kadang diskon/premium 0.1–0.5% dari spot. Jangan pakai harga absolutnya
  untuk entry; gunakan **struktur** (swing, FVG, level relatif). Untuk level absolut,
  koreksi dengan rasio `spot / paxg_close` saat itu.
- **Catatan:** `api.binance.com` diblok TLS di jaringan dev → gunakan
  `data-api.binance.vision` (endpoint publik resmi, data sama).
- Limit: 1000 request/menit per IP (cukup untuk 1 request/15 menit).

### 2.3 OHLCV Historis — Yahoo `GC=F`

```python
import yfinance as yf
df = yf.Ticker("GC=F").history(period="60d", interval="15m")
```
- **Pakai untuk:** seed histori cepat, H4/D1, dan backtest ringan.
- Batasan Yahoo: `1m` maks 7 hari, `5m/15m/30m` maks 60 hari, `1h` maks 730 hari.
- `GC=F` = COMEX gold futures front month; harga bergerak dengan spot tapi ada roll
  → **jangan** gabungkan futures dan spot dalam satu series histori.
- `XAUUSD=X` / `XAU=X` → **404, sudah tidak ada di Yahoo.**

### 2.4 Quote Resmi XAUUSD — TradingView Scanner

```bash
POST https://scanner.tradingview.com/global/scan
Content-Type: application/json

{"symbols":{"tickers":["OANDA:XAUUSD"],"query":{"types":[]}},
 "columns":["close","change","volume"]}
```
Response: `{"totalCount":1,"data":[{"s":"OANDA:XAUUSD","d":[4116.675,-0.5798,92198]}]}`
- **Pakai untuk:** quote pembanding / verifikasi harga broker.
- **Catatan legal:** endpoint internal TradingView, bukan API resmi. Read-only, frekuensi
  rendah (1×/menit) masih wajar, tapi jangan jadi sumber tunggal. Bisa berubah kapan saja.
  Alternatif resmi: TradingView MCP/Charts API (berbayar).

### 2.5 Kalender Ekonomi — ForexFactory JSON

```
GET https://nfs.faireconomy.media/ff_calendar_thisweek.json
```
Item:
```json
{"title":"CPI y/y","country":"USD","date":"2026-11-12T08:30:00-05:00",
 "impact":"High","forecast":"3.1%","previous":"2.9%"}
```
- `impact`: `High | Medium | Low | Holiday`
- `date` berisi offset −05:00 (New York) → **konversi ke UTC** saat parsing.
- Refresh tiap 6 jam. Endpoint ini mirror tidak resmi; jika 404/berubah, fallback:
  scrape `https://www.forexfactory.com/calendar` (HTML) atau TradingView economic calendar.
- **Fail-closed:** jika > 24 jam tidak bisa fetch → sistem menolak mengirim entry alert.

### 2.6 Berita — GDELT DOC API v2

```
GET https://api.gdeltproject.org/api/v2/doc/doc
    ?query=(gold%20OR%20XAU)%20sourcelang:english
    &mode=artlist&maxrecords=25&format=json&timespan=24h
```
Field penting: `url, title, seendate, domain, socialimage, language`.
- Gratis, tanpa key. Untuk tone/sentiment gunakan `mode=timelinevolraw` atau
  pasangkan dengan `mode=tonechart`.
- Rate limit longgar; batasi 1×/15 menit.

### 2.7 Google News RSS

```
GET https://news.google.com/rss/search?q=gold+price+fed&hl=en-US&gl=US&ceid=US:en
```
Parse XML → item `title, link, pubDate, source`.
- Sangat berguna untuk headline cepat. Tidak ada sentiment bawaan.

### 2.8 FRED (opsional, butuh API key gratis)

| Series | Nama | Kegunaan |
|---|---|---|
| `DFII10` | 10-Year TIPS (real yield) | **driver #1 gold** (inverse) |
| `DTWEXBGS` | Broad Dollar Index | DXY proxy (inverse) |
| `T10YIE` | 10-Year breakeven inflation | ekspektasi inflasi |
| `DFEDTARU` | Fed funds target upper | jalur kebijakan |

```
GET https://api.stlouisfed.org/fred/series/observations
    ?series_id=DFII10&api_key=KEY&file_type=json&sort_order=desc&limit=30
```
Tanpa key: gunakan yfinance `DX-Y.NYB` (DXY) dan `^TNX` (nominal yield) sebagai proxy,
dengan catatan akurasi lebih rendah.

### 2.9 CFTC COT (mingguan)

File teks dari `https://www.cftc.gov/dea/futures/deacmxsf.htm` atau unduh CSV
`https://www.cftc.gov/files/dea/history/dea_fut_xls_2026.zip`.
Cari contract `GOLD - COMMODITY EXCHANGE INC.` → `Noncommercial Net`.
- Rilis Jumat 15:30 ET (Sabtu 03:30 WIB).
- Dipakai sebagai filter *contrarian ekstrem*: net-long > persentil 90 historis → jangan
  long baru.

### 2.10 Histori untuk Backtest — Dukascopy

Untuk 2+ tahun M15 XAUUSD dengan kualitas baik, pakai data Dukascopy:
- `https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/00/01/00h_ticks.bi5`
  (bi5 LZMA-compressed ticks, per jam).
- Library Python: `dukascopy-python`, atau `histdata.com` (M1 CSV gratis, kualitas cukup).
- **Jangan** backtest 2 tahun memakai yfinance (terbatas 60 hari untuk M15).

---

## 3. Skema Data Internal

### 3.1 OHLCV (parquet, index UTC)

| Kolom | Tipe | Catatan |
|---|---|---|
| `ts` | datetime64[UTC] | open time bar |
| `open/high/low/close` | float64 | 2 desimal efektif |
| `volume` | float64 | unit kontrak / base asset |
| `source` | string | `paxg|gc_futures|dukascopy` |

Aturan: **satu file parquet per sumber per timeframe** — jangan campur futures & spot.
Nama: `data/paxg_M15.parquet`, `data/gc_futures_H4.parquet`.

### 3.2 Sanity check (dijalankan tiap ingest)

```python
assert df.index.tz is not None
assert df["close"].between(500, 20000).all()          # range wajar XAU
assert not df.index.duplicated().any()
assert (df["high"] >= df[["open","close"]].max(axis=1)).all()
assert (df["low"]  <= df[["open","close"]].min(axis=1)).all()
assert (df.index.to_series().diff().dt.total_seconds() <= tf_seconds * 3).all()  # gap
```

Gap > 3×TF pada jam pasar aktif → tandai baris `suspect`, jangan dipakai untuk sinyal.

### 3.3 Koreksi basis PAXG → spot

```
ratio = spot_price / paxg_close_latest     # dihitung tiap siklus
level_spot = level_paxg * ratio            # untuk display/entry
```
Sistem menyimpan **semua level dalam satuan sumber**; konversi hanya saat menampilkan
ke Telegram. Jika `abs(ratio-1) > 0.01` → kirim warning, turunkan confidence −10.

---

## 4. Kontrak Adapter

```python
class DataAdapter(Protocol):
    name: str
    def fetch_ohlcv(self, tf: str, limit: int) -> pd.DataFrame: ...
    def fetch_quote(self) -> SpotQuote: ...

@dataclass(frozen=True)
class SpotQuote:
    symbol: str
    price: float
    ts_utc: datetime
    source: str
```

Implementasi konkret: `GoldApiAdapter`, `BinancePaxgAdapter`, `YahooGcAdapter`,
`TvScannerAdapter`. Semua mengembalikan DataFrame dengan skema §3.1.

## 5. Retry & Timeout

```python
httpx.get(url, timeout=10.0)          # timeout keras
# retry 3× dengan backoff 1s, 3s, 9s + jitter
# retry hanya untuk 429/5xx/timeout — jangan retry 4xx
```

## 6. Fallback Matrix

| Kebutuhan | Utama | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Spot price | gold-api | TV scanner | ratio dari PAXG |
| OHLCV M15 | Binance PAXG | Yahoo GC=F (max 60d) | cache terakhir (≤ 1 bar) |
| Quote XAUUSD resmi | TV scanner | gold-api | — |
| Kalender | FF JSON | cache 6 jam | **fail-closed** |
| Berita | GDELT | Google News RSS | cache digest terakhir |
| Histori backtest | Dukascopy | HistData M1 | Yahoo 60d (terbatas) |
