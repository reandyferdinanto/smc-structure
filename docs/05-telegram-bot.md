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
