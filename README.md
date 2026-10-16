# ⛏️ MRG Farmer

Bot farmer otomatis untuk **MRG Token** — Telegram Mini App dengan reward token **MRG**. Multi-akun, auto get pass, auto mining, auto check-in, auto task, auto squad, dengan dashboard Rich Live.

---

## ✨ Fitur

- 🔐 **Auto Login Telegram** — Login via Telethon, session disimpan di `sessions/acc_XXX.session`
- 📥 **Auto Fetch initData** — Ambil `tgWebAppData` dari WebView bot, cached 50 menit
- 🛡️ **Auto Turnstile Solver** — Buka Chromium, intercept token Turnstile dari header/iframe
- ✅ **Auto Check-in** — Klaim check-in harian dengan retry + refresh Turnstile
- ⛏️ **Auto Mining** — Klaim MRG otomatis saat pending ≥ minimum threshold
- 🎯 **Auto Task** — Join channel Telegram, dwell 15 detik, lalu claim task
- 👥 **Auto Squad** — Klaim one-time bonus & team commission
- 🔄 **Dynamic Loop** — Bangun saat task reset / mining window freeze, bukan interval tetap
- 🖥️ **Dashboard Rich Live** — 6 slot per akun (ACCOUNT, AUTH, MINING, TASK, SQUAD, BALANCE)
- 📝 **Logger** — Semua error & traceback ke `error.log` (rotating)
- 🖥️ **Window Mode** — `offscreen` / `minimize` / `headless` (fleksibel)
- 🔁 **State Persistence** — Cache initData, task claim, human check validity disimpan ke disk

---

## 📋 Requirement

- **Python** 3.10+ (rekomendasi 3.11+)
- **Windows / Linux / macOS**
- **Chrome / Chromium** (untuk Turnstile — Playwright/Patchright bundled)
- **Telegram API ID & Hash** — dari https://my.telegram.org
- **Akun Telegram** yang sudah join MRG Token

---

## 🚀 Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/erwindobp98/mrg.git
cd mrg
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Isi `requirements.txt`:**

```txt
httpx>=0.27.0
rich>=13.7.0
telethon>=1.36.0
patchright>=1.0.0
```

### 3. Install Chromium untuk Patchright

```bash
python -m patchright install chromium
```

**Kalau gagal**, pakai fallback playwright:

```bash
python -m playwright install chromium
```

### 4. Setup `config.json`

Jalankan script — `config.json` akan dibuat otomatis:

```bash
python mrg.py
```

Setelah dibuat, edit `config.json` dan isi:

```json
{
  "telegram": {
    "api_id": 123456,
    "api_hash": "your_api_hash_here"
  }
}
```

**Cara dapat `api_id` & `api_hash`:**

1. Buka https://my.telegram.org
2. Login dengan nomor Telegram
3. Klik **API development tools**
4. Isi form (App title, Short name, dll)
5. Copy **App api_id** dan **App api_hash** ke `config.json`

---

## 📖 Cara Pakai

### ➕ Tambah Akun Baru

```bash
python mrg.py --add
```

Akan prompt:

```
Nomor Telegram untuk acc_001: +62812xxxxxxx
Kode OTP: 12345
Password 2FA: (kalau ada)
```

Ulangi untuk akun berikutnya (`acc_002`, `acc_003`, ...).

### 🚀 Jalankan Farmer

```bash
python mrg.py
```

Yang terjadi otomatis:
1. Cek semua akun di `sessions/`
2. Cek cache `.initdata` tiap akun — skip kalau masih valid (< 50 menit)
3. Fetch initData baru untuk akun yang expired
4. Start dashboard
5. Login + ping + check-in + mining + task + squad paralel per akun
6. Loop dynamic — bangun saat task reset / mining freeze

### 🔑 Fetch initData Manual (1 Akun)

```bash
python mrg.py pass acc_001
```

### 🔑 Fetch initData Manual (Semua Akun)

```bash
python mrg.py pass-all
```

### ❓ Bantuan

```bash
python mrg.py help
```

---

## 🖥️ Contoh Dashboard

```
╭──────────────────── ⛏️  MRG Farmer ────────────────────╮
│ ACCOUNT  │ SLOT      │ DETAIL                          │
├──────────┼───────────┼─────────────────────────────────┤
│ acc_001  │ ACCOUNT   │ READY · Lv=49 | Speed=9.72 TH/s │
│          │ AUTH      │ OK · @username | ID=12345678    │
│          │ MINING    │ SUCCESS · +1.0142 MRG           │
│          │ TASK      │ SUCCESS · 3 task | +15.00 MRG   │
│          │ SQUAD     │ SUCCESS · Bonus +25 MRG         │
│          │ BALANCE   │ In-App 1,254.30 | Lv49          │
├──────────┼───────────┼─────────────────────────────────┤
│ acc_002  │ ACCOUNT   │ READY · Lv=1 | Speed=0.20 TH/s  │
│          │ AUTH      │ OK · @username | ID=87654321    │
│          │ MINING    │ SUCCESS · +0.1822 MRG           │
│          │ TASK      │ WAIT · React on Latest…         │
│          │ SQUAD     │ SKIP · Tidak ada bonus          │
│          │ BALANCE   │ In-App 12.50 | Lv1              │
╰──────────┴───────────┴─────────────────────────────────╯
```

**Status warna:**
- 🟢 `SUCCESS` / `READY` / `OK` — hijau
- 🟡 `WAIT` / `RUNNING` / `CLAIM` / `DWELL` — kuning
- 🔴 `FAILED` / `ERROR` — merah
- 🔵 `CACHE` / `FETCH` / `REFRESH` — cyan
- 🟣 `RETRY` / `BUSY` — magenta

---

## ⚙️ Konfigurasi (`config.json`)

### Ringkasan

| Section | Fungsi |
|---------|--------|
| `telegram` | `api_id`, `api_hash` dari my.telegram.org |
| `bot` | Username bot, short name, URL app, URL API, referral |
| `turnstile` | Pengaturan Chromium & Cloudflare |
| `human_check` | Kode error human check, expiry margin |
| `mining` | Minimum claimable, window, retry, refresh Turnstile |
| `checkin` | Retry, delay, pre-solve Turnstile |
| `tasks` | Dwell seconds, cooldown per task type, hold task types |
| `cycle` | Interval min/max, timeout, retry, stagger |
| `initdata` | TTL cache initData (default 50 menit) |
| `checkin_rewards` | Array reward per hari streak |

### Contoh Lengkap `config.json`

```json
{
  "telegram": {
    "api_id": 224069,
    "api_hash": "f2ddfd53867f28a3b6b98e80fa010e9d"
  },
  "bot": {
    "username": "mrgminerbot",
    "short_name": "app",
    "app_url": "https://app.mrgtoken.xyz/",
    "api_url": "https://mrg.up.railway.app/api",
    "referral": "ref_48649JOT"
  },
  "turnstile": {
    "site_key": "0x4AAAAAAFI-XXL7bFNbLU_J",
    "page_url": "https://app.mrgtoken.xyz/",
    "headless": false,
    "window_mode": "offscreen",
    "timeout": 60,
    "skip_if_fails": true,
    "max_concurrent": 1
  },
  "human_check": {
    "required_code": "HUMAN_CHECK_REQUIRED",
    "expiry_margin_seconds": 600
  },
  "mining": {
    "minimum_claimable": 0.0001,
    "window_seconds": 86400,
    "retry_max": 3,
    "retry_delay_min": 15,
    "retry_delay_max": 30,
    "turnstile_refresh_each_retry": true
  },
  "checkin": {
    "retry_max": 3,
    "retry_delay_min": 20,
    "retry_delay_max": 40,
    "turnstile_refresh_each_retry": true,
    "pre_solve_turnstile": true
  },
  "tasks": {
    "dwell_seconds": 15,
    "cooldown_hours": {
      "recurring_1h": 1,
      "recurring_3h": 3,
      "recurring_6h": 6,
      "recurring_12h": 12,
      "recurring_24h": 24
    },
    "default_cooldown_hours": 3,
    "hold_task_types": ["token_hold", "nft_hold"]
  },
  "cycle": {
    "min_wait_seconds": 600,
    "max_wait_seconds": 21600,
    "request_timeout": 30,
    "retry_count": 3,
    "stagger_seconds": 3
  },
  "initdata": {
    "ttl_minutes": 50
  },
  "checkin_rewards": [5, 6, 7, 8, 9, 10, 15]
}
```

### Window Mode

Pada `turnstile.window_mode`, pilih:

| Mode | Efek | Cocok untuk |
|------|------|-------------|
| `"offscreen"` | Chromium di luar layar | Default (hemat distraksi) |
| `"minimize"` | Chromium tampil 1 detik lalu minimize | Produksi (paling stabil) |
| `"headless"` | Chromium tak terlihat sepenuhnya | ⚠️ Sering gagal Cloudflare |

**Rekomendasi:** gunakan `"minimize"` untuk produksi kalau `"offscreen"` sering gagal.

---

## 📁 Struktur Folder

```
mrg-farmer/
├── mrg.py                     # Script utama
├── .gitignore
├── config.json                # Konfigurasi (otomatis dibuat)
├── requirements.txt           # Dependencies
├── error.log                  # Log error (auto, rotating)
├── README.md
├── sessions/                  # Data session per akun
│   ├── acc_001.session        # Session Telethon
│   ├── acc_001.initdata       # Cache initData
│   └── ...
├── data/                      # State per akun
│   └── acc_001.json
└── chromium-profiles/         # Profil Chromium per akun
    ├── acc_001_mrg/
    └── ...
```

---

## 🧠 Cara Kerja

### Alur Satu Cycle

```
┌─────────────────────────────────────────────┐
│ 1. Connect Telegram (session)               │
│ 2. Fetch / cache initData                   │
│ 3. Login / verify ke API MRG                │
│ 4. Ping presence                            │
│ 5. Update row ACCOUNT & BALANCE             │
│ 6. Daily Check-in (dengan retry)            │
│ 7. Claim Mining (dengan retry)              │
│ 8. Complete Tasks                           │
│ 9. Claim Squad Rewards                      │
│ 10. Refresh account data                    │
│ 11. Hitung wait time → sleep → ulangi       │
└─────────────────────────────────────────────┘
```

### Human Check (Turnstile)

Saat API mengembalikan `HUMAN_CHECK_REQUIRED`:

1. Bot membuka browser (Patchright/Playwright)
2. Load halaman `app.mrgtoken.xyz` dengan `initData` di fragment URL
3. Tunggu widget Turnstile muncul
4. Klik / intercept token via header `x-turnstile-token`
5. Tukar token ke endpoint `/user/verify-human`
6. Simpan `humanVerifiedUntil` — dipakai sampai expired

### Interval Cycle

Wait time dihitung dari:

- Waktu reset task terdekat
- Waktu freeze window mining (`miningSnapshot.timestamp + 86400`)
- Fallback: 1 jam

Lalu di-clamp antara `MIN_WAIT` dan `MAX_WAIT`, plus random 30–120 detik.

---

## 🔧 Troubleshooting

### ❌ `Executable doesn't exist at ... chromium`

Chromium bundled belum diinstall:

```bash
python -m patchright install chromium
```

### ❌ `config.json tidak valid`

Hapus `config.json` dan jalankan ulang `python mrg.py` untuk regenerate.

### ❌ Turnstile token tidak dapat

- Ubah `turnstile.window_mode` jadi `"minimize"` atau `"normal"`
- Naikkan `turnstile.timeout` jadi `90` atau `120`
- Set `turnstile.headless` = `false`
- Pastikan koneksi internet stabil
- Cek `error.log` untuk detail debug

### ❌ Session belum ada — login Telegram

Jalankan `python mrg.py --add` untuk menambah akun baru.

### ❌ Server down (#N)

Bot otomatis exponential backoff. Tunggu saja, akan retry sendiri.

### ❌ Task gagal: security check

Bot akan otomatis solve Turnstile dan retry. Jika tetap gagal, cek limit akun.

### ❌ Chromium crash di Linux

Butuh dependencies tambahan:

```bash
sudo apt update
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
  libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
  libcairo2 libasound2
```

### ❌ Multi akun berat / RAM habis

Ubah `config.json` → `turnstile.max_concurrent` menjadi `1` (satu Chromium buka dalam satu waktu). Sudah default `1`.

---

## 📝 Log

Semua log tersimpan di **`error.log`** dengan format:

```
2026-10-04 22:36:40 [INFO] [acc_001] initData OK (619 chars)
2026-10-04 22:36:41 [WARNING] [acc_001] HTTP 403 POST /user/claim-mining
2026-10-04 22:36:42 [ERROR] [acc_001] Cycle error: RuntimeError: ...
```

Cek log terakhir:

```bash
tail -50 error.log
```

Atau di Windows:

```bash
type error.log
```

---

## 🔐 Keamanan

- **Session Telethon** disimpan sebagai SQLite di `sessions/acc_XXX.session` — **JANGAN commit ke GitHub**
- **`initData`** disimpan di folder `sessions/` — **JANGAN commit ke GitHub**
- **`config.json`** berisi `api_hash` — **JANGAN commit ke GitHub**

**Buat `.gitignore`:**

```gitignore
# Secrets
sessions/
data/
chromium-profiles/
config.json
error.log

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
venv/
env/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## ⚠️ Disclaimer

**Gunakan dengan risiko sendiri.**

- Bot ini adalah **otomatisasi pihak ketiga** — tidak resmi dari MRG Token
- Bisa **melanggar Terms of Service** MRG Token dan menyebabkan **akun di-ban**
- Script **tidak menyimpan** wallet phrase atau private key (karena tidak butuh)
- API endpoint bisa **berubah sewaktu-waktu** dan mematahkan script
- Turnstile Cloudflare bisa **mendeteksi browser otomatis** kapan saja

**Penulis tidak bertanggung jawab atas kerugian apapun** yang timbul dari penggunaan script ini.

---

**Selamat farming! ⛏️💰**
