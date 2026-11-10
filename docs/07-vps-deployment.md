# 07 — VPS Deployment

Target: Ubuntu 24.04 LTS, 2 vCPU / 2 GB RAM / 40 GB SSD. Estimasi €4–6/bulan
(Hetzner CX22, DigitalOcean Basic, Vultr, Contabo).

---

## 1. Spesifikasi & Pertimbangan

| Kebutuhan | Minimal | Rekomendasi |
|---|---|---|
| vCPU | 1 | 2 |
| RAM | 1 GB | 2 GB |
| Disk | 20 GB | 40 GB (backtest data ~2–5 GB) |
| Region | Singapore/Jakarta (latency ke Binance & Telegram) | Singapore |
| OS | Ubuntu 22.04 | Ubuntu 24.04 LTS |

Beban sistem sangat ringan: ±1 request HTTP tiap 15 menit + hitung pandas pada
500 bar. CPU < 5% rata-rata.

---

## 2. Provisioning Awal

```bash
# sebagai root
adduser trader
usermod -aG sudo trader

apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip git ufw fail2ban \
               chrony sqlite3 curl jq htop unzip

# timezone sistem UTC (WAJIB)
timedatectl set-timezone UTC
timedatectl set-ntp true

# firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw enable

# hardening SSH (opsional tapi disarankan)
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

> Sebelum mematikan password login, pastikan SSH key sudah terpasang dan diuji di sesi baru.

---

## 3. Aplikasi

```bash
su - trader
git clone <repo-anda> ~/xauusd-alerts
cd ~/xauusd-alerts

python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r deploy/requirements.txt

# konfigurasi
cp .env.example .env
chmod 600 .env
nano .env        # isi token Telegram, dsb.

# smoke test
python scripts/send_test_alert.py
DRY_RUN=true python -m src.main --once
```

`deploy/requirements.txt`:

```
httpx==0.27.*
pandas==2.2.*
numpy==1.26.*
pyarrow==16.*
pydantic-settings==2.*
pyyaml==6.*
yfinance==1.3.*
```

---

## 4. systemd Service

`/etc/systemd/system/xauusd-alerts.service`:

```ini
[Unit]
Description=XAUUSD BB+SMC Alert Engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=trader
Group=trader
WorkingDirectory=/home/trader/xauusd-alerts
EnvironmentFile=/home/trader/xauusd-alerts/.env
ExecStart=/home/trader/xauusd-alerts/.venv/bin/python -m src.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xau-alerts

# hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/trader/xauusd-alerts/data /home/trader/xauusd-alerts/state
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xauusd-alerts
sudo systemctl status xauusd-alerts
journalctl -u xauusd-alerts -f --output=cat
```

Alternatif: pakai `--user` service jika tidak mau sudo (perlu `loginctl enable-linger`).

---

## 5. Cloudflare Worker Relay (webhook TradingView)

Struktur `deploy/cloudflare-worker/`:

`wrangler.toml`:
```toml
name = "xau-relay"
main = "src/index.js"
compatibility_date = "2026-01-01"
```

`src/index.js`:
```js
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname !== "/hook") return new Response("not found", { status: 404 });
    if (url.searchParams.get("k") !== env.RELAY_SHARED_SECRET)
      return new Response("forbidden", { status: 403 });

    let j;
    try { j = JSON.parse(await req.text()); }
    catch { return new Response("bad json", { status: 400 }); }

    if (!["long", "short"].includes(j.side) || typeof j.entry !== "number")
      return new Response("bad schema", { status: 400 });

    // basic rate limit: 1 alert / 30 detik
    const k = `rl:${j.symbol}:${j.side}`;
    const last = Number(await env.KV.get(k) || 0);
    if (Date.now() - last < 30_000) return new Response("throttled", { status: 429 });
    await env.KV.put(k, String(Date.now()), { expirationTtl: 120 });

    const dir = j.side === "long" ? "🟢" : "🔴";
    const text =
`${dir} <b>${j.symbol} ${j.side.toUpperCase()}</b> · ${j.tf}m
Entry <code>${j.entry}</code>
SL <code>${j.sl}</code>
TP1 <code>${j.tp1}</code> · TP2 <code>${j.tp2}</code>
RR <b>${j.rr}</b> · Conf ${j.confidence}%
<i>${new Date(j.trigger_candle_ts).toISOString()} · pine</i>`;

    const r = await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: env.TG_CHAT, text, parse_mode: "HTML" }),
    });
    return new Response(r.ok ? "ok" : "tg error", { status: r.ok ? 200 : 502 });
  },
};
```

Deploy:
```bash
npm i -g wrangler
wrangler login
cd deploy/cloudflare-worker
wrangler kv:namespace create RL
# masukkan id ke wrangler.toml → [[kv_namespaces]]
wrangler secret put TG_TOKEN
wrangler secret put TG_CHAT
wrangler secret put RELAY_SHARED_SECRET
wrangler deploy
```

URL webhook TradingView:
```
https://xau-relay.<subdomain>.workers.dev/hook?k=<RELAY_SHARED_SECRET>
```

Biaya: gratis (limit 100k request/hari, jauh lebih dari cukup).

---

## 6. Monitoring & Alerting

| Alat | Fungsi | Setup |
|---|---|---|
| healthchecks.io | ping jika proses hidup | curl URL tiap 5 menit dari heartbeat loop |
| uptime-kuma (opsional) | dashboard | Docker di VPS yang sama |
| journalctl | log | `journalctl -u xauusd-alerts --since "1 hour ago"` |
| logrotate | batasi ukuran log | config di `/etc/logrotate.d/xau-alerts` |

Healthcheck heartbeat dari dalam aplikasi:

```python
# utils/health.py
async def ping_healthcheck(url: str):
    if url:
        await httpx.AsyncClient().get(url, timeout=5)
```

Jika 3 ping berturut gagal → healthchecks.io kirim email/Telegram "service down".

---

## 7. Backup

```bash
# /home/trader/backup.sh
#!/bin/bash
set -e
D=$(date +%F)
tar czf /home/trader/backups/xau-$D.tar.gz \
    -C /home/trader/xauusd-alerts data state .env
find /home/trader/backups -name 'xau-*.tar.gz' -mtime +14 -delete
```

Cron: `0 3 * * * /home/trader/backup.sh`
Opsional: sinkron ke object storage (rclone ke Backblaze B2/S3).

---

## 8. Update & Rollback

```bash
cd ~/xauusd-alerts
git pull
source .venv/bin/activate && pip install -r deploy/requirements.txt
sudo systemctl restart xauusd-alerts
# rollback:
git checkout <previous-tag>
sudo systemctl restart xauusd-alerts
```

Gunakan tag rilis (`v0.1.0`, `v0.2.0`) dan jalankan `pytest` sebelum restart:

```bash
source .venv/bin/activate && pytest -q
```

---

## 9. Security Checklist

- [ ] Root login SSH dimatikan, password auth dimatikan
- [ ] `ufw` aktif, hanya port 22 (atau custom) yang terbuka
- [ ] `.env` chmod 600, tidak masuk git
- [ ] Token bot bisa di-revoke kapan saja (BotFather → `/revoke`)
- [ ] Worker secret tidak ada di kode
- [ ] `fail2ban` aktif untuk SSH
- [ ] Update keamanan otomatis: `unattended-upgrades`
- [ ] Tidak ada port aplikasi yang listen publik (sistem outbound-only)

---

## 10. Biaya Bulanan (estimasi)

| Item | USD |
|---|---|
| VPS 2 vCPU/2GB Singapore | 4–6 |
| Cloudflare Worker | 0 |
| healthchecks.io free tier | 0 |
| Data API | 0 |
| **Total fase 1–3** | **~5** |
| + TradingView plan (fase 4) | +14–30 |
