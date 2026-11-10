# 05 — Telegram Bot & Format Notifikasi

Telegram dipilih karena gratis, API stabil, dan mendukung pesan HTML + inline keyboard.

---

## 1. Setup Bot (15 menit)

1. Buka Telegram → cari **@BotFather** → `/newbot`
2. Isi nama (mis. `XAU Alerts Bot`) dan username (`xau_alerts_<nama>_bot`)
3. Simpan **token**: `123456789:AAH...` → masukkan ke `.env` sebagai `TELEGRAM_BOT_TOKEN`
4. Kirim `/start` ke bot Anda
5. Ambil **chat_id**:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   # cari "chat":{"id":123456789,...}
   ```
6. Masukkan ke `.env` sebagai `TELEGRAM_CHAT_ID`
7. (Untuk grup) tambahkan bot ke grup, jadikan admin, ambil `chat_id` negatif (`-100...`)

**Keamanan:**
- Jangan pernah menaruh token di Pine alert message / repo publik.
- Rotasi token via `/revoke` di BotFather jika bocor.
- Bot hanya menerima dari `TELEGRAM_ALLOWED_CHAT_IDS` (whitelist).

---

## 2. Kirim Pesan (HTTP langsung, tanpa library)

```python
import httpx, os

def send(text: str, parse_mode="HTML"):
    r = httpx.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
        json={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"],
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()
```

Rate limit nyata: ~30 pesan/detik global, tapi **1 pesan/detik per chat** → tambahkan
throttle 1.1 detik antar pesan. Batas panjang pesan: **4096 karakter**.

---

## 3. Template Pesan

### 3.1 Entry Alert

```html
🟢 <b>XAUUSD LONG</b> · M15
━━━━━━━━━━━━━━━━
Entry   <code>4112.70</code>
SL      <code>4105.47</code>  (-7.23)
TP1     <code>4125.20</code>  (+12.50) · RR 1.73
TP2     <code>4134.00</code>  (+21.30) · RR 2.94

Confidence  <b>82%</b>
Session     London
Bias makro  <b>+35</b> (bullish)

<b>Alasan</b>
• H4 uptrend, harga discount
• H1 squeeze (BW persentil 12)
• Sweep low 4108.50 → close balik
• CHoCH + displacement 1.2×ATR
• FVG 1.40 poin, entry 50%

⚠️ NFP 20:30 WIB — jangan tahan posisi melewati rilis
<i>10 Nov 2026 15:42 WIB · source: pine</i>
```

### 3.2 Watchlist (confidence 50–69)

```html
🟡 <b>XAUUSD — WATCHLIST</b> (confidence 58%)
Sweep terdeteksi di 4108.50, CHoCH belum terkonfirmasi.
Tunggu close M15 berikutnya di atas 4112.60.
```

### 3.3 Digest Makro Harian (07:00 WIB)

```html
📊 <b>XAUUSD Daily Briefing</b> — 10 Nov 2026
━━━━━━━━━━━━━━━━
<b>Bias</b>  +35 / 100 → <b>BULLISH (lemah)</b>
 DXY            103.2  ▼ -0.18%
 Real yield 10y 1.84%  ▼ -0.03
 COT net-long   persentil 78
 ETF flow (GLD) +1.2 ton

<b>Harga</b>
 Spot 4117.70 · PAXG 4103.96 (basis -0.33%)
 H4 range 4088 – 4142 (harga di 42% = discount)

<b>Agenda hari ini (WIB)</b>
 15:30  USD  Initial Jobless Claims  (Medium)
 20:30  USD  CPI y/y                 (HIGH) ⚠️
 22:00  USD  Fed Chair Speaks        (High) ⚠️

<b>Headline</b>
• Gold steadies as traders weigh Fed path (Reuters)
• Central bank buying continues in Q4 (WGC)

<i>Sinyal entry akan di-suppress 20:00–21:00 WIB</i>
```

### 3.4 Red Zone Warning

```html
🔴 <b>RED ZONE</b>
CPI y/y (USD, High) dalam <b>30 menit</b> (20:30 WIB).
Entry alert dinonaktifkan 20:00–21:00 WIB.
Gunakan waktu ini untuk mengelola posisi yang sudah ada.
```

### 3.5 System Health

```html
⚙️ <b>System</b>
Uptime 4d 12h · Sinyal hari ini 2 · Suppressed 3
Data: paxg ok (lag 12s) · ff ok · fred ok
Basis PAXG -0.33% ✅
```

Format error (fail-closed):
```html
❌ <b>ENGINE DEGRADED</b>
Kalender FF gagal 3× berturut. Entry alert dinonaktifkan sampai pulih.
```

---

## 4. Formatting Rules

| Aturan | Alasan |
|---|---|
| Pakai `HTML`, bukan `MarkdownV2` | MarkdownV2 butuh escape 18 karakter, rawan rusak |
| Angka harga `<code>` | monospace, mudah dibaca & copy |
| Emoji hanya untuk status (🟢🟡🔴⚙️❌) | konsisten, tidak dekoratif |
| Waktu selalu WIB + label | user di Indonesia |
| Sertakan `source` | audit jalur pine vs python |
| Maks 1 pesan per sinyal | dedupe di server, bukan di Telegram |

---

## 5. Dedupe (wajib)

```sql
CREATE TABLE IF NOT EXISTS sent_alerts (
  dedupe_key TEXT PRIMARY KEY,     -- sha1(symbol|side|tf|trigger_ts)
  sent_at    TEXT NOT NULL,
  payload    TEXT NOT NULL
);
```
- Cek `INSERT OR IGNORE` → jika `rowcount == 0`, jangan kirim (duplikat).
- Ini membuat restart proses aman: sinyal yang sudah terkirim tidak dikirim ulang.

---

## 6. Antrian & Retry

```python
# jika Telegram 429: baca retry_after dan tunggu
# jika 5xx/timeout: simpan ke tabel outbox, coba lagi tiap 60 detik (maks 10x)
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT NOT NULL,
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. Perintah Bot (opsional, fase 5)

Implementasi via long-polling `getUpdates` di proses terpisah (ringan, tanpa webhook publik).

| Command | Aksi |
|---|---|
| `/status` | uptime, state engine, sumber data |
| `/bias` | skor makro terbaru + faktor |
| `/calendar` | agenda hari ini (WIB) |
| `/mute 2h` | hentikan alert entry selama 2 jam |
| `/unmute` | aktifkan kembali |
| `/last` | 3 sinyal terakhir + hasil (jika sudah closed) |
| `/help` | daftar perintah |

Semua command divalidasi terhadap `chat_id` whitelist.

---

## 8. Cloudflare Worker Relay (untuk jalur Pine)

Lihat file lengkap di `07-vps-deployment.md §5`. Ringkasnya:

```js
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.searchParams.get("k") !== env.RELAY_SHARED_SECRET)
      return new Response("forbidden", { status: 403 });
    const body = await req.text();
    const j = JSON.parse(body);                 // validasi JSON
    if (!["long","short"].includes(j.side)) return new Response("bad", {status:400});
    const text = render(j);                     // format HTML
    const tg = await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`, {
      method: "POST",
      headers: {"content-type":"application/json"},
      body: JSON.stringify({chat_id: env.TG_CHAT, text, parse_mode:"HTML"})
    });
    return new Response("ok", { status: tg.ok ? 200 : 502 });
  }
}
```

Secrets disimpan via `wrangler secret put TG_TOKEN` — bukan di kode.

---

## 9. Checklist Uji

- [ ] `sendMessage` manual sukses
- [ ] Format HTML tampil benar (bold, code, emoji)
- [ ] Pesan > 4000 karakter dipotong / dipecah
- [ ] Dedupe: kirim payload sama 2× → hanya 1 pesan
- [ ] Restart proses → tidak ada duplikat
- [ ] Telegram mati → masuk outbox, terkirim saat pulih
- [ ] Whitelist: chat tidak dikenal diabaikan

---

## 10. Trade Tracker — Update SL/TP (v1.3)

Bot tidak berhenti di entry: setiap sinyal yang terkirim dicatat di `state/signals.db`
dan dipantau sampai selesai.

### 10.1 Alur

```
entry alert terkirim
      ▼
tracked_signals(status=OPEN)
      ▼  setiap siklus (60 dtk, bar M15 tertutup)
cek bar setelah opened_at:
  long : low <= SL  → SL (r=-1)   | high >= TP1 → TP1 (r=+RR)
  short: high >= SL → SL          | low  <= TP1 → TP1
  tidak ada & umur > 24 jam → EXPIRED (exit = close terakhir)
      ▼
satu pesan update per transisi (terminal, tidak berulang)
```

### 10.2 Pesan

```
✅ XAUUSD LONG — TP1 HIT
━━━━━━━━━━━━
Entry  4112.70
Exit   4125.20
Result +1.73R
SL 4105.47 · TP1 4125.20
Setup A · opened 10 Nov 2026 19:00 WIB
```

```
❌ XAUUSD LONG — SL HIT
...
Result -1.00R
```

```
⏳ XAUUSD LONG — EXPIRED (24 jam tanpa hit)
Exit 4109.10 · Result -0.50R
```

### 10.3 Aturan

| Aturan | Alasan |
|---|---|
| SL dicek sebelum TP dalam bar yang sama | asumsi terburuk (konservatif) |
| Satu update per status (terminal) | hindari spam & duplikat |
| `EXPIRED` setelah 1440 menit | posisi menggantung tidak dibiarkan |
| Hanya sinyal yang benar-benar terkirim yang dilacak | `open_signal` dipanggil setelah `telegram.send` sukses |
| `commit=False` saat DRY_RUN | tidak mengotori state saat testing |

### 10.4 Keterbatasan (penting)

- Level SL/TP dihitung dari **PAXG**, bukan feed broker Anda. Selisih 0.1–0.5% bisa
  membuat bot melaporkan TP1 padahal broker belum tersentuh.
- Belum ada partial close otomatis atau trailing SL; pesan TP1 hanya **saran**.
- TP2 belum dilacak terpisah (status terminal di TP1/SL/EXPIRED).
- Untuk akurasi eksekusi, tracker idealnya membaca harga dari MT5 broker (fase berikutnya).

### 10.5 Pengujian

```bash
python -m pytest tests/test_tracker.py
```
Kasus diuji: TP1, SL priority saat satu bar menyentuh keduanya, EXPIRED, dan tidak ada
update ganda.

---

## 11. Two-Stage Alert — SETUP lalu OPEN (v1.4)

Entry **tidak** dikirim saat setup muncul. Ada dua tahap terpisah:

```
SETUP ARMED (M15)
  ├─ invalidasi: close M5 melewati level invalid → CANCELLED
  ├─ kedaluwarsa: 120 menit tanpa konfirmasi → EXPIRED
  └─ konfirmasi M5: harga di zona + micro sweep + micro BOS + body
        ▼
OPEN LONG/SHORT NOW  ← baru boleh eksekusi
        ▼
tracker OPEN → TP1 / SL / EXPIRED
```

### 11.1 Pesan tahap 1 (belum entry)

```
🟡 XAUUSD SETUP LONG · A
━━━━━━━━━━━━
Zona    4109.50 – 4114.00
Invalid 4105.47
TP1 4125.20 · TP2 4134.00

Belum entry. Tunggu pesan OPEN … NOW setelah konfirmasi M5.
Confidence 82% · LDN/NY overlap
```

### 11.2 Pesan tahap 2 (eksekusi)

```
🟢 OPEN LONG NOW — XAUUSD
━━━━━━━━━━━━
Entry 4113.10
SL    4105.10
TP1   4125.20  RR 1.52
TP2   4134.00

Konfirmasi M5 valid. Eksekusi sekarang, jangan chase >0.15 ATR.
```

RR dihitung ulang dari entry aktual; SL mengikuti sweep low terbaru.

### 11.3 Aturan konfirmasi M5 (`src/strategy/trigger.py`)

| Syarat | Parameter |
|---|---|
| Timeframe konfirmasi | `trigger.timeframe: 5m` (bisa `1m`, lebih noisy) |
| Harga masuk zona | `zone_tolerance_atr: 0.10` |
| Body candle ≥ | `min_body_atr: 0.40` |
| Micro sweep + reclaim (lookback) | `sweep_lookback: 6` |
| Micro BOS (close melewati high/low bar sebelumnya) | — |
| Jangan chase | `max_chase_atr: 0.15` |
| RR minimum setelah entry aktual | `min_rr: 1.2` |
| Kedaluwarsa setup | `arm_expiry_minutes: 120` |

### 11.4 Konsekuensi yang harus diterima

- **Sebagian setup tidak jadi entry** karena harga langsung menjauh (missed trade).
  Ini disengaja: mengejar harga adalah sumber loss besar.
- Konfirmasi M5 bisa **whipsaw** (false trigger). Karena itu RR dihitung ulang dan
  SL mengikuti sweep terbaru, bukan level lama.
- **Backtest saat ini masih single-stage** (entry di open bar berikutnya). Backtest
  two-stage membutuhkan data M5 — belum diimplementasikan. Jangan mengklaim hasil
  two-stage sebelum ada backtest M5.
- Setup yang di-cancel/expired tetap dicatat di `state/signals.db` (`armed_signals`).

---

## 12. Bot Commands (v1.7)

Bot membaca perintah via `getUpdates` setiap siklus (tanpa webhook publik).
Hanya `chat_id` di `TELEGRAM_ALLOWED_CHAT_IDS`/`TELEGRAM_CHAT_ID` yang dilayani.

| Perintah | Fungsi |
|---|---|
| `/help` | panduan lengkap (alur, perintah, aturan) |
| `/status` | bias H4, regime, squeeze, spot+basis, jumlah armed/posisi, status mute |
| `/last` | sinyal terakhir dari DB (zona, SL, TP, status) |
| `/reentry` | cek re-entry BB middle M5 untuk sinyal terakhir |
| `/calendar` | event High USD hari ini (WIB + UTC) |
| `/mute 60` | matikan seluruh alert trading 60 menit |
| `/unmute` | aktifkan kembali |

Catatan:
- `/status` dan `/calendar` melakukan fetch data (bisa 3–8 detik).
- `/mute` menulis `state/mute_until`; `run_once` melewati semua pengiriman selama aktif.
  Command tetap dibalas (karena dikirim oleh handler, bukan alert).
- Offset update disimpan di `state/tg_offset`; pada start pertama, backlog lama dilewati
  agar bot tidak membalas pesan historis.
