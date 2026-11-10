# 04 — Pine Script (Indicator + Strategy + Alert)

Pine **bukan** sistem lengkap: Pine tidak bisa mengakses kalender ekonomi atau berita.
Perannya di arsitektur ini: **trigger teknikal server-side** yang mengirim JSON ke relay,
lalu relay meneruskan ke Telegram.

---

## 1. Batasan TradingView yang Harus Diketahui Dulu

| Item | Fakta | Implikasi |
|---|---|---|
| Webhook | tersedia di plan **berbayar** (Essentials ke atas) | kalau tetap free → pakai jalur Python |
| 2FA | **wajib** aktif sebelum bisa membuat webhook | aktifkan di Account settings |
| Webhook target | hanya port **80/443**, IPv4, timeout **3 detik** | Telegram langsung (`api.telegram.org:443`) *bisa*, tapi token terekspos → pakai Worker |
| Alert limit | plan free: 1 alert aktif | berbayar: 20+ alert |
| `alert()` per bar | limit per plan (free ~1/bar/script) | desain sinyal harus jarang, jangan spam |
| Data | feed OANDA/FXCM `XAUUSD` resmi | tidak ada basis PAXG |
| IV/B-series | tidak tersedia di Pine | kalender berita hanya dari luar |

**Konsekuensi desain:** jangan kirim alert di setiap bar. Kirim hanya pada transisi
state (IDLE→ARMED tidak perlu, ARMED→TRIGGERED saja).

---

## 2. Deliverable Pine

1. `xau_bb_smc_indicator.pine` — overlay visual: BB, swing, sweep, FVG box, OTE zone,
   label CHoCH/BOS, panel info (regime, %B, BW percentile, bias H4).
2. `xau_bb_smc_strategy.pine` — versi `strategy()` dengan entry/SL/TP yang sama,
   untuk backtest dan optimasi parameter.
3. Alert JSON payload dari #1 (dan #2 untuk paper trading).

Keduanya **wajib** memakai fungsi logika yang sama (copy-paste fungsi, bukan ditulis ulang),
supaya angka backtest == angka live.

---

## 3. Struktur `xau_bb_smc_indicator.pine`

```pinescript
//@version=6
indicator("XAU BB+SMC/ICT [alert]", overlay=true, max_boxes_count=200,
          max_lines_count=200, max_labels_count=500)

// ==== INPUTS =====================================================
grpBB   = "Bollinger"
bbLen   = input.int(20, "BB Length", 5, 200, group=grpBB)
bbMult  = input.float(2.0, "BB StdDev", 1.0, 4.0, 0.1, group=grpBB)
sqzLb   = input.int(100, "Squeeze lookback", 20, 300, group=grpBB)
sqzPct  = input.int(25, "Squeeze percentile", 5, 50, group=grpBB)

grpSMC  = "SMC / ICT"
pivK    = input.int(3, "Pivot strength (k)", 1, 10, group=grpSMC)
atrLen  = input.int(14, "ATR length", 5, 50, group=grpSMC)
dispMult= input.float(1.2, "Displacement ATR mult", 0.5, 3.0, 0.1, group=grpSMC)
fvgMult = input.float(0.15, "Min FVG size (ATR)", 0.05, 1.0, 0.05, group=grpSMC)
sweepM  = input.float(0.05, "Sweep pierce (ATR)", 0.01, 0.5, 0.01, group=grpSMC)
eqMult  = input.float(0.10, "Equal level tol (ATR)", 0.02, 0.5, 0.01, group=grpSMC)
minRR   = input.float(1.5, "Min RR", 1.0, 4.0, 0.1, group=grpSMC)

grpSess = "Session / News"
useSess = input.bool(true, "Only in killzone", group=grpSess)
sessNY  = input.session("1200-1500", "NY killzone (exchange tz)", group=grpSess)
sessLDN = input.session("0700-1000", "London killzone (exchange tz)", group=grpSess)

// ==== BOLLINGER ==================================================
[mid, up, lo] = ta.bb(close, bbLen, bbMult)
width   = (up - lo) / mid * 100
pctB    = (close - lo) / (up - lo)
wRank   = ta.percentrank(width, sqzLb)
sqz     = wRank <= sqzPct
expanded= wRank >= 75

// ==== ATR ========================================================
atr     = ta.atr(atrLen)
atr20   = ta.atr(20)
body    = math.abs(close - open)
disp    = body >= dispMult * atr20

// ==== PIVOTS =====================================================
ph = ta.pivothigh(high, pivK, pivK)
pl = ta.pivotlow(low, pivK, pivK)

// simpan pivot (array + var)
var array<float> phPx  = array.new_float()
var array<int>   phBar = array.new_int()
var array<float> plPx  = array.new_float()
var array<int>   plBar = array.new_int()

if not na(ph)
    array.push(phPx, ph);  array.push(phBar, bar_index - pivK)
if not na(pl)
    array.push(plPx, pl);  array.push(plBar, bar_index - pivK)
// batasi array (mis. keep 50 terakhir) supaya tidak kena limit

// ==== LIQUIDITY / EQUAL LEVELS ===================================
// gabungkan pivot yang selisihnya <= eqMult*atr menjadi satu level
// (fungsi helper: build_liquidity_levels(px_arr, tol) -> array<Level>)

// ==== STRUCTURE ==================================================
// BOS/CHoCH: close menembus pivot high/low terakhir
// bullish_choch = close > lastSwingHigh && disp && trendPrev == -1

// ==== FVG ========================================================
// bullish: high[2] < low[0]  → box [high[2], low[0]]
// syarat: (low[0]-high[2]) >= fvgMult * atr

// ==== OTE ========================================================
// leg = impulseHigh - impulseLow; zone = [0.618, 0.786] retrace

// ==== STATE MACHINE ==============================================
var int state = 0        // 0 IDLE, 1 ARMED, 2 TRIGGERED
var string side = ""

// ==== ALERT ======================================================
if triggerLong
    payload = '{"type":"entry","symbol":"' + syminfo.ticker + '",' +
              '"side":"long","tf":"' + timeframe.period + '",' +
              '"entry":' + str.tostring(entry, "#.##") + ',' +
              '"sl":'    + str.tostring(sl,    "#.##") + ',' +
              '"tp1":'   + str.tostring(tp1,   "#.##") + ',' +
              '"tp2":'   + str.tostring(tp2,   "#.##") + ',' +
              '"rr":'    + str.tostring(rr,    "#.##") + ',' +
              '"confidence":' + str.tostring(conf) + ',' +
              '"session":"' + sessName + '",' +
              '"trigger_candle_ts":' + str.tostring(time) + '}'
    alert(payload, alert.freq_once_per_bar_close)
```

### 3.1 Catatan implementasi Pine

- `alert.freq_once_per_bar_close` — jangan pakai `once_per_bar` untuk sinyal.
- Panel visual: `table.new(position.top_right, ...)` isi: H4 bias, regime, %B, BW rank,
  state, session.
- Simbol pivot array harus dipangkas (`array.shift`) agar aman di 20k bar.
- `max_bars_back` boleh dinaikkan (mis. 500) tapi hati-hati limit compile.
- Jangan pakai `request.security()` berlebihan — 1× H4 dan 1× H1 sudah cukup.

---

## 4. Struktur `xau_bb_smc_strategy.pine`

```pinescript
//@version=6
strategy("XAU BB+SMC/ICT [backtest]", overlay=true,
         initial_capital=10000, default_qty_type=strategy.percent_of_equity,
         default_qty_value=2, commission_type=strategy.commission.cash_per_contract,
         commission_value=0.35, slippage=1, process_orders_on_close=true)

// logika entry identik dengan indicator
// exit: TP1 50% (strategy.exit qty_percent=50), sisanya trailing / TP2
// SL wajib di setiap entry: strategy.exit(stop=...)
```

Aturan backtest yang benar:
- `process_orders_on_close=true` (sinyal & eksekusi di close bar yang sama, sesuai live).
- `commission_value` = spread gold retail (~$0.30–0.40/oz → kalibrasi ke broker Anda).
- `slippage=1` tick minimum; untuk gold realistis 2–5 tick.
- Jangan pakai `calc_on_every_tick=true` — backtest jadi tidak jujur.

---

## 5. Kontrak Alert JSON (sama dengan Python)

```json
{
  "type": "entry",
  "symbol": "XAUUSD",
  "side": "long",
  "tf": "15",
  "entry": 4112.7,
  "sl": 4105.47,
  "tp1": 4125.2,
  "tp2": 4134.0,
  "rr": 1.73,
  "confidence": 82,
  "session": "london",
  "trigger_candle_ts": 1794283800000,
  "source": "pine"
}
```

Field `source` (`pine|python`) wajib ada supaya log bisa dibedakan.

---

## 6. Alur Webhook → Telegram

```
TradingView alert
   │  URL: https://xau-relay.<sub>.workers.dev/hook?k=RELAY_SHARED_SECRET
   │  Body: JSON di atas
   ▼
Cloudflare Worker (validasi secret + schema + rate limit)
   │  POST https://api.telegram.org/bot<TOKEN>/sendMessage
   ▼
Telegram
```

Kenapa Worker, bukan langsung ke Telegram:
1. Token bot tidak boleh ada di alert message TradingView (bisa dilihat siapa pun dengan akses akun).
2. Telegram membutuhkan format query/body spesifik; TV mengirim body apa adanya.
3. Worker bisa melakukan dedupe/format/forwarding ke banyak chat.

Kode Worker ada di `07-vps-deployment.md §5`.

---

## 7. Setup TradingView (checklist)

- [ ] Aktifkan 2FA
- [ ] Tambah indicator `xau_bb_smc_indicator` ke chart `OANDA:XAUUSD`
- [ ] TF M15 (trigger), plus chart H4 terpisah untuk bias
- [ ] Buat alert: Condition = **Any alert() function call**
- [ ] Expiration: *open-ended* (butuh plan berbayar) atau perpanjang manual
- [ ] Notification: **Webhook URL** = relay + secret
- [ ] Alert message: biarkan default (kita override via `alert()` payload)
- [ ] Test dengan `alert()` manual, cek Worker logs + Telegram
- [ ] Bar Replay 3–5 hari untuk verifikasi sinyal muncul di bar yang benar

### Alternatif tanpa plan berbayar

- Pakai jalur Python saja (rekomendasi fase awal).
- Atau alert TradingView → email → filter Gmail → IFTTT/Zapier → Telegram (rapuh, tidak disarankan).

---

## 8. Testing Pine

1. **Repaint test** — sinyal tidak boleh hilang setelah bar close. Jalankan Bar Replay.
2. **Cross-check** — ambil 10 sinyal historis Pine, hitung ulang manual/pandas; harus sama.
3. **Overlay comparison** — strategy vs indicator pada tanggal yang sama harus entry di bar sama.
4. **Performance** — compile < 20 detik, tidak ada "loop takes too long".

---

## 9. Adopsi Referensi Open-Source (v1.1)

### 9.1 Basis kode yang direkomendasikan

| Kebutuhan Pine | Sumber | Lisensi | Cara pakai |
|---|---|---|---|
| Order block, FVG, liquidity, BOS/CHoCH | [quantumalgo-official/smart-money-concepts-indicator](https://github.com/quantumalgo-official/smart-money-concepts-indicator) | **MIT** | adaptasi fungsi, tambahkan atribusi di header |
| Suite 16 strategi Pine v6 (pola struktur file) | [Ahmed-GoCode/Quant-Edge-Indicators](https://github.com/Ahmed-GoCode/Quant-Edge-Indicators) | **MPL-2.0** | boleh dipakai; file yang dimodifikasi tetap MPL-2.0 |
| Konvensi label (HH/HL/LH/LL, iCHoCH, MBOS, EQH/EQL) | [kxngHADES/SMC-Marking](https://github.com/kxngHADES/SMC-Marking) | none | **konsep saja**, tulis sendiri |

### 9.2 Input tambahan di indicator (v1.1)

```pinescript
grpReg  = "Regime"
regimeMode = input.string("rule", "Regime method", options=["rule","off"], group=grpReg)
adxMin     = input.int(25, "ADX trend min", 10, 50, group=grpReg)
atrRankVol = input.int(80, "ATR rank volatile", 50, 100, group=grpReg)

grpORB  = "Setup B — ORB"
useORB     = input.bool(true, "Enable ORB setup", group=grpORB)
orbLondon  = input.session("0700-0800", "London ORB window (UTC)", group=grpORB)
orbNY      = input.session("1200-1300", "NY ORB window (UTC)", group=grpORB)
orbConsol  = input.int(3, "Min consolidation candles", 1, 10, group=grpORB)
orbSqueeze = input.bool(true, "Require H1 squeeze", group=grpORB)

grpOB   = "Order Block"
useOB      = input.bool(true, "Use fresh OB", group=grpOB)
obFreshOnly= input.bool(true, "Skip mitigated OB", group=grpOB)
```

### 9.3 Perubahan state machine di Pine

Tambahkan `setup` pada payload dan dua jalur transisi:

```
IDLE --(squeeze + liquidity)--> ARMED_A --(sweep+iCHoCH+FVG/OB)--> TRIGGERED_A
IDLE --(squeeze + session open)--> ARMED_B --(breakout+retest)--> TRIGGERED_B
```

Payload wajib memuat `"setup":"A"|"B"` agar dedupe dan statistik terpisah.

### 9.4 Atribusi di header file Pine

```pinescript
// Portions adapted from:
//   Smart Money Concepts — Quantum Algo (MIT)
//   https://github.com/quantumalgo-official/smart-money-concepts-indicator
// Strategy patterns reference:
//   Quant Edge Indicators — Ahmed-GoCode (MPL-2.0)
// Concepts (no code reused): SMC-Marking (kxngHADES), GOLD_ORB (yulz008)
```

### 9.5 Checklist tambahan sebelum publish

- [ ] Header atribusi terpasang untuk setiap kode MIT yang diadaptasi
- [ ] Jika mengambil file MPL-2.0: file tetap MPL + source tersedia
- [ ] Tidak ada kode dari repo tanpa lisensi (clean-room)
- [ ] Sinyal Setup A dan B memiliki label berbeda di payload
- [ ] Uji ulang 10 sinyal setelah refactor (cross-check dengan Python)

---

## 10. Session Marker di Pine (WIB-friendly)

TradingView tidak punya indikator sesi bawaan yang menampilkan Asia/London/NY sekaligus
dengan jam WIB. Pakai ini:

```pinescript
//@version=6
indicator("Sessions [UTC labels → WIB]", overlay=true)

tz         = "UTC"                       // eksplisit, jangan ikut timezone chart
sessAsia   = "0000-0900"
sessLondon = "0700-1600"                 // geser ke 0800-1700 saat Eropa winter
sessNY     = "1200-2100"                 // geser ke 1300-2200 saat US winter

inAsia    = not na(time(timeframe.period, sessAsia,   tz))
inLondon  = not na(time(timeframe.period, sessLondon, tz))
inNY      = not na(time(timeframe.period, sessNY,     tz))
inOverlap = inLondon and inNY

bgcolor(inOverlap ? color.new(color.orange, 86) :
        inLondon  ? color.new(color.blue,   90) :
        inNY      ? color.new(color.green,  90) :
        inAsia    ? color.new(color.gray,   93) : na, title="Session")

plotshape(inLondon  and not inLondon[1],  "London open", shape.triangleup,   location.bottom, color.blue,   size=size.tiny)
plotshape(inNY      and not inNY[1],      "NY open",     shape.triangleup,   location.bottom, color.green,  size=size.tiny)
plotshape(inOverlap and not inOverlap[1], "Overlap",     shape.diamond,      location.bottom, color.orange, size=size.tiny)

// label WIB (UTC+7) di bar terakhir
if barstate.islast
    wib = hour(time, tz) + 7
    label.new(bar_index, high, "WIB " + str.format("{0,number,00}", wib % 24) + ":00",
              style=label.style_label_down, color=color.new(color.black, 20),
              textcolor=color.white, size=size.small)
```

Catatan:
- Argumen ketiga `time()` adalah **timezone**, bukan string WIB. Karena WIB = UTC+7 tanpa
  DST, cukup tampilkan `UTC+7` di label; jangan mengubah session string ke WIB.
- Saat Eropa/US winter, session string bergeser +1 jam — paling aman simpan dua set string
  di config dan pilih berdasarkan bulan (Mar–Okt vs Nov–Mar).
- Untuk grafik `OANDA:XAUUSD`, sesi di atas adalah sesi *pasar*, bukan jam exchange.

### 10.1 Alternatif bawaan

- Chart settings → **Session breaks** → tampilkan batas sesi (hanya visual, tanpa label Asia/London/NY).
- Indikator publik "Session Highlighter"/"Sessions" di TradingView — cepat, tapi umumnya
  memakai timezone chart sehingga label tidak WIB.

### 10.2 Padanan di engine Python

Fungsi `session_label()` di `02 §13.4` harus menghasilkan label yang sama dengan
`inAsia/inLondon/inNY/inOverlap` di Pine. Tambahkan test sinkronisasi: untuk 24 jam sampel,
label Pine dan Python harus identik (kecuali pergeseran DST yang disengaja).
