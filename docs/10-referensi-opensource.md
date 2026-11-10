# 10 — Referensi Open-Source & Aturan Reuse

Semua repo di bawah dicek via GitHub API pada **10 Nov 2026** (stars, lisensi,
`pushed_at`). Stars ≠ profitabilitas; yang dinilai adalah **lisensi, aktivitas, dan
keterbacaan**.

---

## 1. Tabel Referensi Utama

| Repo | Stats | Lisensi | Isi | Yang diambil | Boleh salin kode? |
|---|---|---|---|---|---|
| [quantumalgo-official/smart-money-concepts-indicator](https://github.com/quantumalgo-official/smart-money-concepts-indicator) | 23★, Pine v6, Okt 2026 | **MIT** | OB, FVG, liquidity, BOS/CHoCH | definisi OB, struktur FVG, konvensi liquidity | ✅ ya + atribusi |
| [Ahmed-GoCode/Quant-Edge-Indicators](https://github.com/Ahmed-GoCode/Quant-Edge-Indicators) | 55★, MPL-2.0, Agu 2026 | **MPL-2.0** | 16 strategi Pine v6 termasuk SMC | pola strategi, referensi struktur file | ⚠️ ya, file yang dimodifikasi wajib tetap MPL |
| [kxngHADES/SMC-Marking](https://github.com/kxngHADES/SMC-Marking) | 42★, Pine v6, Sep 2026 | **none** | HH/HL/LH/LL, BMS/BOS, CHoCH, EQH/EQL, premium/discount, session levels | terminologi & UX (dashboard, glossary) | ❌ **tidak** — konsep saja |
| [GifariKemal/xaubot-ai](https://github.com/GifariKemal/xaubot-ai) | 111★, Python, MIT, Feb 2026 | **MIT** | SMC + XGBoost 37 fitur + HMM 3-state + risk engine | ide regime layer, dynamic confidence, filter stack, news agent | ✅ ya + atribusi |
| [yulz008/GOLD_ORB](https://github.com/yulz008/GOLD_ORB) | 329★, MQL5, 2023 | **none** | Opening Range Breakout EA | konsep ORB + "minimum 3 candle konsolidasi" | ❌ tidak — konsep saja |
| [francomascareloai/EA_SCALPER_XAUUSD](https://github.com/francomascareloai/EA_SCALPER_XAUUSD) | 285★, MQL5, Jun 2026 | **NOASSERTION** | riset scalper terbuka (WIP) | prinsip backtest-live parity | ❌ tidak jelas → hindari menyalin |
| [zero-was-here/tradingbot](https://github.com/zero-was-here/tradingbot) | 218★, Python, MIT, aktif | **MIT** | DRL (PPO/Dreamer) gold | referensi riset saja | ✅ (tapi tidak dipakai di v1) |
| [3aLaee/xauusd-trading-bot](https://github.com/3aLaee/xauusd-trading-bot) | 212★, Python, MIT, Jan 2025 | **MIT** | scalper XAUUSD sederhana | struktur bot minimal | ✅ |
| [triqbit/mt5-ai-xauusd-trader](https://github.com/triqbit/mt5-ai-xauusd-trader) | 201★, Python | MIT | ML bot MT5 | referensi integrasi MT5 | ✅ (kualitas campur) |

---

## 2. Aturan Reuse (wajib dipatuhi)

### 2.1 Lisensi

| Lisensi | Boleh dipakai? | Kewajiban |
|---|---|---|
| **MIT** | ✅ | sertakan copyright notice + license text di file/README |
| **MPL-2.0** | ✅ | file yang dimodifikasi **tetap** MPL-2.0 dan source-nya harus tersedia |
| **Apache-2.0** | ✅ | notice + changelog |
| **NOASSERTION / none** | ❌ | hanya boleh **membaca konsep**, menulis ulang dari nol (clean-room) |
| Tanpa file LICENSE jelas | ❌ | anggap proprietary |

Atribusi minimal yang harus ada di repo Anda:

```markdown
## Third-party references

- Smart Money Concepts indicator — Quantum Algo (MIT)
  https://github.com/quantumalgo-official/smart-money-concepts-indicator
- XAUBot AI — Gifari Kemal (MIT)
  https://github.com/GifariKemal/xaubot-ai
- Pine Script strategy patterns — Ahmed-GoCode (MPL-2.0)
  https://github.com/Ahmed-GoCode/Quant-Edge-Indicators

Konsep ORB diadaptasi dari GOLD_ORB (yulz008) — tanpa reuse kode.
Konsep terminologi BMS/iCHoCH dari SMC-Marking (kxngHADES) — tanpa reuse kode.
```

### 2.2 Clean-room rule

Untuk repo tanpa lisensi:
1. Baca untuk memahami **ide** (mis. "ORB butuh 3 candle konsolidasi").
2. Tutup repo tersebut.
3. Tulis implementasi sendiri dari spesifikasi di `02-spesifikasi-strategi.md`.
4. Jangan copy-paste variabel, nama fungsi, atau struktur blok yang identik.

### 2.3 Apa yang TIDAK boleh diambil

- ❌ Logika martingale/grid dari EA gold mana pun.
- ❌ Klaim win rate di README tanpa dataset & kode backtest.
- ❌ Model ML terlatih (file `.pkl/.joblib`) dari repo orang — tidak bisa diverifikasi dan
  berpotensi menimbun bias data.
- ❌ Kode yang memanggil endpoint sinyal berbayar / Telegram grup.

---

## 3. Pemetaan Referensi → Modul Proyek

| Modul proyek | Referensi | Tingkat adopsi |
|---|---|---|
| `strategy/orderblock.py` | quantumalgo SMC (MIT) | definisi + adaptasi kode |
| `strategy/structure.py` | SMC-Marking (konsep) + quantumalgo | tulis sendiri |
| `strategy/fvg.py` | quantumalgo + SMC-Marking (partial fill) | adaptasi kode MIT |
| `strategy/regime.py` | xaubot-ai (HMM idea) | tulis sendiri (rule-based dulu) |
| `strategy/orb.py` | GOLD_ORB (konsep) | tulis sendiri |
| `strategy/engine.py` (filter stack) | xaubot-ai | tulis sendiri |
| `pine/*.pine` | quantumalgo (MIT) + Ahmed-GoCode (MPL) | adaptasi dengan atribusi |
| `backtest/*` | EA_SCALPER (prinsip) | tulis sendiri |

---

## 4. Repo Lain yang Layak Dipantau (bukan untuk v1)

| Repo/Tool | Fungsi | Kenapa belum dipakai |
|---|---|---|
| `nautechsystems/nautilus_trader` | framework event-driven backtest==live | migrasi fase 6–7 jika engine sendiri mulai terbatas |
| `kernc/backtesting.py` | backtest ringan | cukup untuk validasi awal; tidak real-time |
| `polakowo/vectorbt` | vectorized backtest | bagus untuk eksperimen parameter massal |
| `mql5/MetaTrader5` (python package) | akses MT5 | hanya jika nanti eksekusi via MT5 |
| `mrjbq7/ta-lib` / `twopirllc/pandas-ta` | indikator | TA-Lib butuh kompilasi; pandas-ta cukup |

---

## 5. Checklist Sebelum Mengadopsi Kode Eksternal

- [ ] File `LICENSE` ada dan jelas (bukan NOASSERTION)
- [ ] `pushed_at` < 12 bulan
- [ ] Tidak ada dependency ke layanan berbayar/sinyal
- [ ] Tidak ada logika martingale/grid/averaging
- [ ] Bisa dijalankan/dibaca lokal tanpa akun
- [ ] Ada test atau contoh data
- [ ] Atribusi ditambahkan ke README proyek
- [ ] Jika MPL: file hasil modifikasi tetap MPL dan dipublikasikan
- [ ] Kode di-port ke gaya & config proyek (bukan ditempel mentah)
- [ ] Ditambahkan test unit sendiri (preferensi: minimal 3 kasus)

---

## 6. Catatan Kualitas (jujur)

- **Tidak ada** repo dari daftar ini yang bisa dijadikan sistem live langsung. Semua adalah
  bahan belajar atau komponen.
- `xaubot-ai` paling relevan secara konsep (SMC + regime + Telegram + risk), tapi
  klaim performanya tidak dapat diverifikasi tanpa data MT5 Anda.
- `SMC-Marking` paling rapi secara presentasi, tapi tanpa lisensi → hanya untuk memahami
  bagaimana indikator SMC disusun dan dijelaskan ke user.
- `quantumalgo` adalah satu-satunya Pine SMC berlisensi MIT yang bisa dipakai langsung.
- `GOLD_ORB` mengilustrasikan ide ORB dengan baik, tapi kode MQL5-nya tidak bisa diuji
  di luar MetaTrader dan tidak ada lisensi.
