"""
MRG Farmer

Commands:
  python mrg.py              → Auto farmer (loop dinamis)
  python mrg.py --add        → Tambah akun baru via login Telegram
  python mrg.py pass <acc>   → Fetch initData manual untuk 1 akun
  python mrg.py pass-all     → Fetch initData manual semua akun
  python mrg.py help         → Bantuan
"""

import asyncio
import json
import logging
import random
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, quote

import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import (
    RequestAppWebViewRequest,
    RequestMainWebViewRequest,
    RequestWebViewRequest,
)
from telethon.tl.types import (
    InputBotAppShortName,
    KeyboardButtonWebView,
    KeyboardButtonSimpleWebView,
)


# =====================================================================
# PATH
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
SESSIONS_DIR = BASE_DIR / "sessions"
DATA_DIR = BASE_DIR / "data"
LOG_PATH = BASE_DIR / "error.log"
BROWSER_PROFILES_DIR = BASE_DIR / "chromium-profiles"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# LOGGER
# =====================================================================

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("mrg")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = RotatingFileHandler(
        LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


LOGGER = setup_logger()
LOGGER.info("=" * 70)
LOGGER.info("MRG Farmer dimulai")


def log_info(account_id: str, message: str):
    LOGGER.info(f"[{account_id}] {message}")


def log_warn(account_id: str, message: str):
    LOGGER.warning(f"[{account_id}] {message}")


def log_error(account_id: str, context: str, error: Exception):
    LOGGER.error(f"[{account_id}] {context}: {type(error).__name__}: {error}")
    LOGGER.error(f"[{account_id}] Traceback:\n{traceback.format_exc()}")


# =====================================================================
# CONFIG
# =====================================================================

DEFAULT_CONFIG = {
    "telegram": {
        "api_id": 224069,
        "api_hash": "f2ddfd53867f28a3b6b98e80fa010e9d",
    },
    "bot": {
        "username": "mrgminerbot",
        "short_name": "app",
        "app_url": "https://app.mrgtoken.xyz/",
        "api_url": "https://mrg.up.railway.app/api",
        "referral": "ref_48649JOT",
    },
    "turnstile": {
        "site_key": "0x4AAAAAAFI-XXL7bFNbLU_J",
        "page_url": "https://app.mrgtoken.xyz/",
        "headless": False,
        "window_mode": "offscreen",
        "timeout": 60,
        "skip_if_fails": True,
        "max_concurrent": 1,
    },
    "human_check": {
        "required_code": "HUMAN_CHECK_REQUIRED",
        "expiry_margin_seconds": 600,
    },
    "mining": {
        "minimum_claimable": 0.0001,
        "window_seconds": 86400,
        "retry_max": 3,
        "retry_delay_min": 15,
        "retry_delay_max": 30,
        "turnstile_refresh_each_retry": True,
    },
    "checkin": {
        "retry_max": 3,
        "retry_delay_min": 20,
        "retry_delay_max": 40,
        "turnstile_refresh_each_retry": True,
        "pre_solve_turnstile": True,
    },
    "tasks": {
        "dwell_seconds": 15,
        "cooldown_hours": {
            "recurring_1h": 1,
            "recurring_3h": 3,
            "recurring_6h": 6,
            "recurring_12h": 12,
            "recurring_24h": 24,
        },
        "default_cooldown_hours": 3,
        "hold_task_types": ["token_hold", "nft_hold"],
    },
    "cycle": {
        "min_wait_seconds": 600,
        "max_wait_seconds": 21600,
        "request_timeout": 30,
        "retry_count": 3,
        "stagger_seconds": 3,
    },
    "initdata": {
        "ttl_minutes": 25,
    },
    "checkin_rewards": [5, 6, 7, 8, 9, 10, 15],
}

if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(
        json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("=" * 80)
    print("config.json belum ada — sudah dibuat otomatis.")
    print(f"Lokasi: {CONFIG_PATH}")
    print("=" * 80)
    sys.exit(0)


def load_config() -> dict:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"config.json tidak valid: {e}")
        sys.exit(1)

    def merge(target, defaults):
        for k, v in defaults.items():
            if k not in target:
                target[k] = v
            elif isinstance(v, dict) and isinstance(target[k], dict):
                merge(target[k], v)

    merge(cfg, DEFAULT_CONFIG)
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return cfg


CFG = load_config()

API_ID = int(CFG["telegram"]["api_id"])
API_HASH = str(CFG["telegram"]["api_hash"])

BOT_USERNAME = str(CFG["bot"]["username"]).lstrip("@")
BOT_SHORT_NAME = str(CFG["bot"].get("short_name") or "app").strip("/")
APP_URL = str(CFG["bot"]["app_url"]).rstrip("/")
API_URL = str(CFG["bot"]["api_url"]).rstrip("/")
REFERRAL_CODE = str(CFG["bot"].get("referral") or "").strip()

TURNSTILE_SITE_KEY = CFG["turnstile"]["site_key"]
TURNSTILE_PAGE_URL = CFG["turnstile"]["page_url"]
TURNSTILE_HEADLESS = bool(CFG["turnstile"]["headless"])
TURNSTILE_WINDOW_MODE = str(CFG["turnstile"].get("window_mode", "headless")).lower()
TURNSTILE_TIMEOUT = int(CFG["turnstile"]["timeout"])
TURNSTILE_SKIP_IF_FAILS = bool(CFG["turnstile"].get("skip_if_fails", True))
TURNSTILE_MAX_CONCURRENT = int(CFG["turnstile"].get("max_concurrent", 1))

HUMAN_REQUIRED_CODE = CFG["human_check"]["required_code"]
HUMAN_CHECK_EXPIRY_MARGIN = int(CFG["human_check"]["expiry_margin_seconds"])

MINIMUM_CLAIMABLE_MINING = float(CFG["mining"]["minimum_claimable"])
MINING_WINDOW_SECONDS = int(CFG["mining"]["window_seconds"])
MINING_RETRY_MAX = int(CFG["mining"].get("retry_max", 3))
MINING_RETRY_DELAY_MIN = int(CFG["mining"].get("retry_delay_min", 15))
MINING_RETRY_DELAY_MAX = int(CFG["mining"].get("retry_delay_max", 30))
MINING_REFRESH_TURNSTILE = bool(CFG["mining"].get("turnstile_refresh_each_retry", True))

CHECKIN_RETRY_MAX = int(CFG["checkin"].get("retry_max", 3))
CHECKIN_RETRY_DELAY_MIN = int(CFG["checkin"].get("retry_delay_min", 20))
CHECKIN_RETRY_DELAY_MAX = int(CFG["checkin"].get("retry_delay_max", 40))
CHECKIN_REFRESH_TURNSTILE = bool(CFG["checkin"].get("turnstile_refresh_each_retry", True))
CHECKIN_PRE_SOLVE = bool(CFG["checkin"].get("pre_solve_turnstile", True))

TASK_DWELL_SECONDS = int(CFG["tasks"]["dwell_seconds"])
TASK_COOLDOWN_HOURS = dict(CFG["tasks"]["cooldown_hours"])
DEFAULT_TASK_COOLDOWN_HOURS = int(CFG["tasks"]["default_cooldown_hours"])
HOLD_TASK_TYPES = list(CFG["tasks"]["hold_task_types"])

MIN_WAIT = int(CFG["cycle"]["min_wait_seconds"])
MAX_WAIT = int(CFG["cycle"]["max_wait_seconds"])
REQUEST_TIMEOUT = int(CFG["cycle"]["request_timeout"])
RETRY_COUNT = int(CFG["cycle"]["retry_count"])
STAGGER_SECONDS = int(CFG["cycle"].get("stagger_seconds", 3))

INITDATA_TTL_MIN = int(CFG["initdata"]["ttl_minutes"])

CHECKIN_REWARDS = list(CFG["checkin_rewards"])

# Miner curve constants
MAX_MINER_LEVEL = 1000
BASE_SPEED_THS = 0.2
MID_SPEED_LEVEL = 203
MID_SPEED_THS = 7.56
MAX_SPEED_THS = 5000
DAILY_OUTPUT_PER_THS = 25
LEVEL_ONE_DAILY_OUTPUT = 5


# =====================================================================
# MINER CURVE
# =====================================================================

def get_miner_speed(level: int) -> float:
    if level <= 0:
        return 0.0
    if level >= MAX_MINER_LEVEL:
        return float(MAX_SPEED_THS)

    if level <= MID_SPEED_LEVEL:
        step = (MID_SPEED_THS - BASE_SPEED_THS) / (MID_SPEED_LEVEL - 1)
        return round(BASE_SPEED_THS + (level - 1) * step, 2)

    progress = (level - MID_SPEED_LEVEL) / (MAX_MINER_LEVEL - MID_SPEED_LEVEL)
    val = MID_SPEED_THS + (MAX_SPEED_THS - MID_SPEED_THS) * (progress ** 2.1)
    return round(val, 2)


def get_miner_daily_output(level: int) -> float:
    if level <= 0:
        return 0.0
    if level == 1:
        return float(LEVEL_ONE_DAILY_OUTPUT)
    return round(get_miner_speed(level) * DAILY_OUTPUT_PER_THS, 2)


def get_miner_required_holding(level: int) -> int:
    if level <= 0:
        return 0
    if level == 1:
        return 100
    if level >= MAX_MINER_LEVEL:
        return 3875968992

    if level <= 203:
        return round(100 + 9900 * ((level - 1) / 202) ** 1.8)
    if level <= 450:
        return round(1e4 + 24e4 * ((level - 203) / 247) ** 2)
    if level <= 650:
        return round(25e4 + 26881780 * ((level - 450) / 200) ** 2.2)
    if level <= 850:
        return round(27131780 + 321705420 * ((level - 650) / 200) ** 2.5)
    return round(
        348837200
        + 3527131792 * ((level - 850) / (MAX_MINER_LEVEL - 850)) ** 2.6
    )


def find_miner_level_for_holding(holding: float, wallet_connected: bool = True) -> int:
    amount = float(holding or 0)
    if not wallet_connected and amount <= 0:
        return 0
    if amount < get_miner_required_holding(1):
        return 1 if wallet_connected else 0

    lo, hi, reachable = 1, MAX_MINER_LEVEL, 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if amount >= get_miner_required_holding(mid):
            reachable = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return reachable


# =====================================================================
# DASHBOARD
# =====================================================================

SLOTS = ["ACCOUNT", "AUTH", "MINING", "TASK", "SQUAD", "BALANCE"]

STATUS_STYLES = {
    "SUCCESS": "bold green", "SUCCESSFUL": "bold green",
    "READY": "bold green", "OK": "bold green",
    "JOINED": "bold green", "DONE": "bold green",
    "CLAIMED": "bold green", "VERIFIED": "bold green",
    "START": "bold yellow", "RUNNING": "bold yellow",
    "REQUEST": "yellow", "RESPONSE": "green",
    "WAIT": "bold yellow", "SKIP": "dim yellow",
    "CACHE": "cyan", "FETCH": "cyan", "SAVED": "cyan",
    "MISS": "yellow", "RETRY": "bold magenta", "BUSY": "bold magenta",
    "INPUT": "bold yellow", "CLAIM": "bold yellow",
    "REFRESH": "cyan", "FAILED": "bold red",
    "ERROR": "bold red", "INVALID": "bold red",
    "DWELL": "bold yellow", "SOLVE": "bold yellow",
}


class Dashboard:
    def __init__(self):
        self.accounts: list = []
        self.data: dict = {}
        self.lock = asyncio.Lock()
        self._console = Console()
        self._live = None
        self._started = False

    def register(self, account_id: str):
        if account_id not in self.data:
            self.data[account_id] = {
                slot: {"status": "WAIT", "detail": "Menunggu..."}
                for slot in SLOTS
            }

    def start(self):
        if self._started:
            return
        self._live = Live(
            self.build_layout(),
            console=self._console,
            refresh_per_second=4,
            screen=True,
            transient=False,
        )
        self._live.start(refresh=True)
        self._started = True

    def stop(self):
        if self._live is not None:
            try:
                self._live.stop()
            finally:
                self._live = None
                self._started = False

    async def update(self, account_id: str, slot: str, status: str, detail: str):
        async with self.lock:
            self.register(account_id)
            slot_key = str(slot).upper()
            if slot_key not in SLOTS:
                slot_key = "ACCOUNT"
            self.data[account_id][slot_key] = {
                "status": str(status).upper(),
                "detail": str(detail),
            }
            self.render()

    def build_table(self) -> Table:
        table = Table(
            title="⛏️  MRG Farmer",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold white on blue",
            expand=True,
            show_lines=False,
        )
        table.add_column("ACCOUNT", style="bold cyan", min_width=12, no_wrap=True)
        table.add_column("SLOT", style="bold magenta", min_width=10, no_wrap=True)
        table.add_column("DETAIL", ratio=1, overflow="fold")

        for idx, acc in enumerate(self.accounts):
            if idx > 0:
                table.add_section()
            account_rows = self.data.get(acc, {})
            for slot_idx, slot in enumerate(SLOTS):
                row = account_rows.get(slot, {"status": "WAIT", "detail": "-"})
                status = str(row.get("status", "-")).upper()
                detail = str(row.get("detail", "-")).replace("\n", " ").strip()
                if len(detail) > 110:
                    detail = detail[:107] + "..."
                style = STATUS_STYLES.get(status, "white")
                acc_display = acc if slot_idx == 0 else ""
                table.add_row(
                    acc_display,
                    slot,
                    f"[{style}]{status}[/{style}] · {detail}",
                )
        return table

    def build_layout(self):
        if not self.accounts:
            return Panel("Menunggu akun...", title="⛏️  MRG Farmer")
        return self.build_table()

    def render(self):
        if not self._started or self._live is None:
            return
        self._live.update(self.build_layout(), refresh=True)


DASHBOARD = Dashboard()


async def activity(account_id: str, slot: str, status: str, detail: str):
    await DASHBOARD.update(account_id, slot, status, detail)


# =====================================================================
# STATE
# =====================================================================

@dataclass
class AccountState:
    account_id: str
    last_balance: float = 0.0
    last_level: int = 0
    cycles_run: int = 0
    last_run_ts: int = 0
    task_claims: dict = None
    consecutive_failures: int = 0
    human_verified_until: int = 0

    def __post_init__(self):
        if self.task_claims is None:
            self.task_claims = {}


class StateManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, account_id: str) -> AccountState:
        path = self.base_dir / f"{account_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return AccountState(**data)
            except Exception:
                pass
        return AccountState(account_id=account_id)

    def save(self, state: AccountState):
        path = self.base_dir / f"{state.account_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(asdict(state), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)


# =====================================================================
# HELPERS
# =====================================================================

def now_ts() -> float:
    return time.time()


def parse_iso(ts: str | None) -> float:
    if not ts:
        return 0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def minimize_windows_browser(keyword: str = "mrg") -> bool:
    import platform
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
        )
        found = {"hwnd": None}

        def callback(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if keyword.lower() in title.lower() and user32.IsWindowVisible(hwnd):
                found["hwnd"] = hwnd
                return False
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)

        if found["hwnd"]:
            SW_MINIMIZE = 6
            user32.ShowWindow(found["hwnd"], SW_MINIMIZE)
            return True
    except Exception:
        pass
    return False


def get_launch_args() -> list:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if TURNSTILE_WINDOW_MODE == "offscreen":
        args.extend([
            "--window-position=-3000,-3000",
            "--window-size=500,900",
        ])
    return args


# =====================================================================
# TURNSTILE SOLVER
# =====================================================================

_TURNSTILE_SEM = None


def get_turnstile_semaphore() -> asyncio.Semaphore:
    global _TURNSTILE_SEM
    if _TURNSTILE_SEM is None:
        _TURNSTILE_SEM = asyncio.Semaphore(TURNSTILE_MAX_CONCURRENT)
    return _TURNSTILE_SEM


class TurnstileSolver:
    def __init__(self, account_id: str, init_data: str):
        self.account_id = account_id
        self.init_data = init_data

    async def _load_playwright(self):
        try:
            from patchright.async_api import async_playwright
            return async_playwright
        except ImportError:
            pass
        try:
            from playwright.async_api import async_playwright
            return async_playwright
        except ImportError:
            raise RuntimeError(
                "Install: pip install patchright && "
                "python -m patchright install chromium"
            )

    async def solve(self) -> str | None:
        sem = get_turnstile_semaphore()
        async with sem:
            log_info(self.account_id, "Turnstile slot didapat")
            return await self._solve_inner()

    async def _solve_inner(self) -> str | None:
        try:
            async_playwright = await self._load_playwright()
        except RuntimeError as e:
            log_error(self.account_id, "Load playwright gagal", e)
            return None

        profile_dir = BROWSER_PROFILES_DIR / f"{self.account_id}_mrg"
        profile_dir.mkdir(parents=True, exist_ok=True)

        captured = {"token": None}

        async with async_playwright() as p:
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=TURNSTILE_HEADLESS,
                    args=get_launch_args(),
                )
            except Exception as e:
                log_error(self.account_id, "Launch browser gagal", e)
                return None

            page = await context.new_page()

            # Handle minimize
            if TURNSTILE_WINDOW_MODE == "minimize" and not TURNSTILE_HEADLESS:
                await asyncio.sleep(1.5)
                minimize_windows_browser("mrg")
                minimize_windows_browser("chromium")

            # ===== on_request DI DALAM async with =====
            async def on_request(request):
                if captured["token"]:
                    return
                try:
                    if "mrg.up.railway.app" not in request.url:
                        return
                    headers = request.headers
                    ts_token = headers.get("x-turnstile-token") or \
                               headers.get("X-Turnstile-Token")
                    if ts_token and len(ts_token) > 100:
                        captured["token"] = ts_token
                        log_info(self.account_id, "Turnstile dari header")
                except Exception:
                    pass

            page.on("request", lambda r: asyncio.create_task(on_request(r)))

            webapp_url = (
                f"{APP_URL.rstrip('/')}/"
                f"#tgWebAppData={quote(self.init_data, safe='')}"
                f"&tgWebAppVersion=7.0&tgWebAppPlatform=android"
            )

            try:
                await page.goto(webapp_url, wait_until="domcontentloaded",
                                timeout=30000)
            except Exception as e:
                log_warn(self.account_id, f"Goto gagal: {e}")

            if TURNSTILE_WINDOW_MODE == "minimize" and not TURNSTILE_HEADLESS:
                await asyncio.sleep(1)
                minimize_windows_browser("app.mrgtoken.xyz")
                minimize_windows_browser("mrg")
                minimize_windows_browser("chromium")

            # FASE 1: Tunggu widget Turnstile
            widget_found = False
            start = time.time()
            while time.time() - start < 20:
                try:
                    iframe = await page.query_selector(
                        'iframe[src*="challenges.cloudflare.com"]'
                    )
                    if iframe:
                        widget_found = True
                        log_info(self.account_id, "Turnstile widget terdeteksi")
                        break

                    has_input = await page.evaluate("""
                        () => !!document.querySelector('[name="cf-turnstile-response"]')
                    """)
                    if has_input:
                        widget_found = True
                        log_info(self.account_id, "Turnstile input terdeteksi")
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)

            if not widget_found:
                log_warn(self.account_id, "Turnstile widget tidak muncul")

            # FASE 2: Tunggu token & interaksi
            start = time.time()
            click_attempts = 0
            while time.time() - start < TURNSTILE_TIMEOUT:
                if captured["token"]:
                    break

                token = await self._try_capture_token(page)
                if token:
                    captured["token"] = token
                    log_info(self.account_id, "Token didapat!")
                    break

                try:
                    iframe = await page.query_selector(
                        'iframe[src*="challenges.cloudflare.com"]'
                    )
                    if iframe:
                        box = await iframe.bounding_box()
                        if box and box["width"] > 0:
                            click_x = box["x"] + 30
                            click_y = box["y"] + box["height"] / 2

                            click_attempts += 1
                            log_info(self.account_id,
                                     f"Klik Turnstile #{click_attempts} "
                                     f"@ ({click_x:.0f}, {click_y:.0f})")

                            await page.mouse.click(click_x, click_y)
                            await asyncio.sleep(2)
                except Exception as e:
                    log_warn(self.account_id, f"Klik gagal: {e}")

                await asyncio.sleep(1)

            # FASE 3: Coba ambil token terakhir
            if not captured["token"]:
                token = await self._try_capture_token(page)
                if token:
                    captured["token"] = token

            # Log debug kalau tidak dapat token
            if not captured["token"]:
                try:
                    debug_info = await page.evaluate("""
                        () => {
                            const info = {};
                            info.title = document.title || '';
                            info.turnstileIframes = document.querySelectorAll(
                                'iframe[src*="challenges.cloudflare.com"]'
                            ).length;
                            info.hasCfInput = !!document.querySelector(
                                '[name="cf-turnstile-response"]'
                            );
                            info.hasTurnstileObject = !!window.turnstile;
                            info.url = window.location.href.slice(0, 100);
                            info.bodyPreview = (document.body.innerText || '')
                                .slice(0, 80).replace(/\\n/g, ' ');
                            return info;
                        }
                    """)
                    log_info(self.account_id,
                             f"Debug: {json.dumps(debug_info, ensure_ascii=False)}")
                except Exception as e:
                    log_warn(self.account_id, f"Debug info gagal: {e}")

            # ===== Tutup context DI DALAM async with =====
            try:
                await context.close()
            except Exception:
                pass

        # async with selesai di sini

        if captured["token"]:
            log_info(self.account_id, "Turnstile token didapat")
            return captured["token"]

        log_warn(self.account_id, "Turnstile token tidak dapat")
        return None

    async def _try_capture_token(self, page) -> str | None:
        """Coba ambil token dari berbagai sumber."""
        # Metode 1: input cf-turnstile-response
        try:
            token = await page.evaluate("""
                () => {
                    const el = document.querySelector('[name="cf-turnstile-response"]');
                    return el ? el.value : null;
                }
            """)
            if token and len(token) > 100:
                return token
        except Exception:
            pass

        # Metode 2: window.turnstile.getResponse()
        try:
            token = await page.evaluate("""
                () => {
                    if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                        try {
                            return window.turnstile.getResponse();
                        } catch (e) {
                            return null;
                        }
                    }
                    return null;
                }
            """)
            if token and len(token) > 100:
                return token
        except Exception:
            pass

        # Metode 3: iframe data-response
        try:
            token = await page.evaluate("""
                () => {
                    const iframes = document.querySelectorAll(
                        'iframe[src*="challenges.cloudflare.com"]'
                    );
                    for (const iframe of iframes) {
                        const response = iframe.getAttribute('data-response');
                        if (response && response.length > 100) return response;
                    }
                    return null;
                }
            """)
            if token:
                return token
        except Exception:
            pass

        # Metode 4: input hidden
        try:
            token = await page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input[type="hidden"]');
                    for (const inp of inputs) {
                        if (inp.value && inp.value.length > 100 &&
                            inp.name && inp.name.toLowerCase().includes('turnstile')) {
                            return inp.value;
                        }
                    }
                    return null;
                }
            """)
            if token:
                return token
        except Exception:
            pass

        return None


# =====================================================================
# API CLIENT
# =====================================================================

class ApiClient:
    def __init__(self, account_id: str, init_data: str):
        self.account_id = account_id
        self.init_data = init_data
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        self._turnstile_token = None

    async def close(self):
        await self._client.aclose()

    def set_turnstile(self, token: str | None):
        self._turnstile_token = token

    def _headers(self) -> dict:
        return {
            "Accept": "application/json, text/plain, */*",
            "Origin": APP_URL,
            "Referer": APP_URL + "/",
            "Content-Type": "application/json",
        }

    async def call(self, path: str, data: dict | None = None) -> dict:
        url = f"{API_URL}{path}"
        payload_data = {**(data or {}), "initData": self.init_data}

        if self._turnstile_token:
            payload_data["turnstileToken"] = self._turnstile_token

        last_error = None
        for attempt in range(RETRY_COUNT):
            try:
                response = await self._client.post(
                    url,
                    json=payload_data,
                    headers=self._headers(),
                )
                payload = response.json() if response.content else {}

                if response.status_code >= 500:
                    log_warn(
                        self.account_id,
                        f"HTTP {response.status_code} POST {path}",
                    )

                return payload if isinstance(payload, dict) else {}

            except Exception as e:
                last_error = e
                if attempt < RETRY_COUNT - 1:
                    await asyncio.sleep(2 * (attempt + 1))

        return {"success": False, "error": f"HTTP error: {last_error}"}


# =====================================================================
# MRG CLIENT
# =====================================================================

class MRGClient:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.tg: TelegramClient | None = None
        self.api: ApiClient | None = None
        self.init_data_raw: str | None = None
        self.init_data_fetched_at: float = 0
        self.user_obj: dict | None = None
        self.tg_id: int | None = None
        self.account_data: dict = {}
        self.account_read_at: float = 0
        self._joined_channels: set = set()
        self.task_claims: dict = {}
        self.human_verified_until: int = 0

    # ------------------------------------------------------------------
    # Cache paths
    # ------------------------------------------------------------------

    def _session_path(self) -> Path:
        return SESSIONS_DIR / self.account_id

    def _initdata_cache_path(self) -> Path:
        return SESSIONS_DIR / f"{self.account_id}.initdata"

    def _load_cached_initdata(self) -> tuple[str | None, float]:
        p = self._initdata_cache_path()
        if not p.exists():
            return None, 0
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None, 0
            init_data = data.get("initData")
            fetched_at = float(data.get("fetchedAt", 0))
            if not init_data:
                return None, 0
            age_min = (now_ts() - fetched_at) / 60
            if age_min > INITDATA_TTL_MIN:
                return None, fetched_at
            return init_data, fetched_at
        except Exception:
            return None, 0

    def _save_initdata(self, init_data: str):
        try:
            self._initdata_cache_path().write_text(
                json.dumps({
                    "initData": init_data,
                    "fetchedAt": int(now_ts()),
                    "userId": self.tg_id,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            log_warn(self.account_id, f"Gagal simpan initData: {e}")

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    async def connect(self, require_login: bool = True) -> bool:
        self.tg = TelegramClient(
            str(self._session_path()),
            API_ID, API_HASH,
            device_model="Samsung Galaxy S23",
            system_version="Android 14",
            app_version="10.5.2",
            lang_code="en",
            system_lang_code="en-US",
        )

        last_error = None
        for attempt in range(RETRY_COUNT):
            try:
                await self.tg.connect()
                last_error = None
                break
            except Exception as e:
                last_error = e
                await asyncio.sleep(2 + attempt * 2)

        if last_error:
            raise RuntimeError(f"Telegram connect failed: {last_error}")

        if not await self.tg.is_user_authorized():
            if not require_login:
                return False
            await activity(self.account_id, "AUTH", "INPUT",
                           "Session belum ada — login Telegram")
            await self.tg.disconnect()
            await self.login_new_telegram()
            return True

        me = await self.tg.get_me()
        await activity(self.account_id, "AUTH", "OK",
                       f"@{me.username or '-'} | ID={me.id}")
        return True

    async def login_new_telegram(self):
        self.tg = TelegramClient(
            str(self._session_path()),
            API_ID, API_HASH,
            device_model="Samsung Galaxy S23",
            system_version="Android 14",
            app_version="10.5.2",
            lang_code="en",
            system_lang_code="en-US",
        )
        await self.tg.connect()
        phone = input(f"\nNomor Telegram untuk {self.account_id}: ").strip()
        if not phone:
            raise RuntimeError("Nomor kosong")
        await self.tg.send_code_request(phone)
        code_input = input("Kode OTP: ").strip()
        try:
            await self.tg.sign_in(phone=phone, code=code_input)
        except SessionPasswordNeededError:
            password = input("Password 2FA: ")
            await self.tg.sign_in(password=password)

        me = await self.tg.get_me()
        await activity(self.account_id, "AUTH", "SUCCESS",
                       f"@{me.username or '-'} | ID={me.id}")

    async def close(self):
        if self.api:
            try:
                await self.api.close()
            except Exception:
                pass
        if self.tg:
            try:
                await self.tg.disconnect()
            except Exception:
                pass
            self.tg = None

    # ------------------------------------------------------------------
    # Fetch initData
    # ------------------------------------------------------------------

    async def fetch_webapp_query(self) -> str:
        if not self.tg:
            raise RuntimeError("Telegram belum connect")

        bot = await self.tg.get_entity(BOT_USERNAME)
        start_param = REFERRAL_CODE or "start"

        await activity(self.account_id, "AUTH", "FETCH",
                       "Buka WebApp bot...")

        if BOT_SHORT_NAME:
            try:
                result = await self.tg(RequestAppWebViewRequest(
                    peer=bot,
                    app=InputBotAppShortName(
                        bot_id=bot,
                        short_name=BOT_SHORT_NAME,
                    ),
                    platform="android",
                    start_param=start_param,
                ))
                if result.url and "#" in result.url:
                    return self._extract_init_data_from_url(result.url)
            except Exception as e:
                log_warn(self.account_id, f"RequestAppWebView gagal: {e}")

        try:
            messages = await self.tg.get_messages(bot, limit=20)
            for msg in messages:
                if not msg.reply_markup:
                    continue
                rows = getattr(msg.reply_markup, "rows", None) or []
                for row in rows:
                    for button in row.buttons:
                        url = getattr(button, "url", None)
                        if not url:
                            continue
                        if isinstance(button, KeyboardButtonWebView) or \
                           isinstance(button, KeyboardButtonSimpleWebView):
                            try:
                                result = await self.tg(RequestWebViewRequest(
                                    peer=bot, bot=bot, platform="android",
                                    url=url, start_param=start_param,
                                ))
                                if result.url and "#" in result.url:
                                    return self._extract_init_data_from_url(result.url)
                            except Exception:
                                continue
        except Exception:
            pass

        try:
            result = await self.tg(RequestMainWebViewRequest(
                peer=bot, bot=bot, platform="android",
                start_param=start_param,
            ))
            if result.url and "#" in result.url:
                return self._extract_init_data_from_url(result.url)
        except Exception as e:
            log_warn(self.account_id, f"RequestMainWebView gagal: {e}")

        raise RuntimeError(f"WebApp URL tidak ditemukan di @{BOT_USERNAME}")

    def _extract_init_data_from_url(self, url: str) -> str:
        if "#" not in url:
            raise RuntimeError("URL tidak memiliki fragment")
        fragment = url.split("#", 1)[1]
        params = parse_qs(fragment)
        if "tgWebAppData" not in params:
            raise RuntimeError("tgWebAppData tidak ada")
        raw = params["tgWebAppData"][0]
        qs = parse_qs(raw)
        if "user" not in qs:
            raise RuntimeError("Data user tidak ada")
        try:
            user_obj = json.loads(qs["user"][0])
        except Exception as e:
            raise RuntimeError(f"JSON user tidak valid: {e}")
        if not isinstance(user_obj, dict) or not user_obj.get("id"):
            raise RuntimeError("Data user tidak valid")

        self.init_data_raw = raw
        self.user_obj = user_obj
        self.tg_id = int(user_obj["id"])
        self.init_data_fetched_at = now_ts()

        self._save_initdata(raw)
        log_info(self.account_id, f"initData OK ({len(raw)} chars)")
        return raw

    async def ensure_init_data(self) -> str:
        cached, fetched_at = self._load_cached_initdata()
        if cached:
            age_min = (now_ts() - fetched_at) / 60
            await activity(self.account_id, "AUTH", "CACHE",
                           f"initData cache ({age_min:.0f}m)")
            self.init_data_raw = cached
            self.init_data_fetched_at = fetched_at
            qs = parse_qs(cached)
            if "user" in qs:
                try:
                    self.user_obj = json.loads(qs["user"][0])
                    self.tg_id = int(self.user_obj.get("id") or 0)
                except Exception:
                    pass
            return cached

        if not self.tg:
            await self.connect(require_login=True)

        await activity(self.account_id, "AUTH", "FETCH",
                       "Fetch initData baru...")
        return await self.fetch_webapp_query()

    # ------------------------------------------------------------------
    # Human check cache
    # ------------------------------------------------------------------

    def is_human_check_valid(self, margin_seconds: int = None) -> bool:
        if margin_seconds is None:
            margin_seconds = HUMAN_CHECK_EXPIRY_MARGIN
        if not self.human_verified_until:
            return False
        return self.human_verified_until - now_ts() > margin_seconds

    def store_human_verified_until(self, until_str: str, state: AccountState = None):
        ts = parse_iso(until_str)
        if ts:
            self.human_verified_until = int(ts)
            if state:
                state.human_verified_until = int(ts)

    # ------------------------------------------------------------------
    # Turnstile
    # ------------------------------------------------------------------

    async def solve_turnstile(self) -> str | None:
        solver = TurnstileSolver(self.account_id, self.init_data_raw or "")
        return await solver.solve()

    async def verify_human(self, turnstile_token: str) -> dict:
        """Tukar Turnstile token dengan humanVerifiedUntil."""
        return await self.api.call("/user/verify-human", {
            "turnstileToken": turnstile_token,
        })

    async def ensure_turnstile(self, force: bool = False,
                                state: AccountState = None) -> bool:
        """
        Pastikan human check valid.
        1. Cek cache humanVerifiedUntil
        2. Kalau expired, solve Turnstile
        3. Tukar token dengan humanVerifiedUntil
        """
        # Cek cache dulu
        if not force and self.is_human_check_valid():
            until = datetime.fromtimestamp(self.human_verified_until)
            await activity(self.account_id, "HUMAN", "OK",
                           f"Valid until {until.strftime('%H:%M:%S')}")
            return True

        await activity(self.account_id, "HUMAN", "SOLVE",
                       "Solving Turnstile...")
        token = await self.solve_turnstile()
        if not token:
            await activity(self.account_id, "HUMAN", "SKIP",
                           "Turnstile gagal")
            return False

        # Tukar token dengan humanVerifiedUntil
        await activity(self.account_id, "HUMAN", "RUNNING",
                       "Verify human...")
        result = await self.verify_human(token)

        if result.get("success") and result.get("humanVerifiedUntil"):
            self.store_human_verified_until(
                result["humanVerifiedUntil"], state
            )
            until_str = result["humanVerifiedUntil"][:19]
            await activity(self.account_id, "HUMAN", "OK",
                           f"Valid until {until_str}")
            return True

        err = str(result.get("error") or "")[:50]
        await activity(self.account_id, "HUMAN", "FAILED", err)
        return False

    # ------------------------------------------------------------------
    # Login / auth
    # ------------------------------------------------------------------

    async def login(self):
        await self.ensure_init_data()

        if not self.api:
            self.api = ApiClient(self.account_id, self.init_data_raw)

        await activity(self.account_id, "AUTH", "RUNNING",
                       "Verify account...")
        result = await self.api.call("/auth/verify", {
            "startParam": REFERRAL_CODE,
            "deviceInfo": self.get_device_info(),
        })

        if result.get("success") is False:
            err = result.get("error") or "Verify gagal"
            await activity(self.account_id, "AUTH", "FAILED", str(err)[:60])
            raise RuntimeError(f"Verify gagal: {err}")

        await self.load_account()
        await activity(self.account_id, "AUTH", "SUCCESS",
                       f"@{self.user_obj.get('username') or self.tg_id}")

    def get_device_info(self) -> dict:
        return {
            "platform": "android",
            "deviceName": "Samsung Galaxy S23",
            "ram": "8 GB",
            "cpuCores": 8,
            "screenResolution": "1080x2400",
            "userAgent": (
                "Mozilla/5.0 (Linux; Android 14; SM-S916B) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Mobile Safari/537.36"
            ),
            "timezone": "Asia/Jakarta",
            "language": "en",
        }

    # ------------------------------------------------------------------
    # Account state
    # ------------------------------------------------------------------

    async def load_account(self):
        result = await self.api.call("/user/me", {
            "deviceInfo": self.get_device_info(),
        })
        if isinstance(result, dict) and result.get("user"):
            self.account_data = result
            self.account_read_at = now_ts()
        return self.account_data

    def user(self) -> dict:
        return self.account_data.get("user", {})

    def tasks(self) -> list:
        return self.account_data.get("tasks", [])

    def transactions(self) -> list:
        return self.account_data.get("transactions", [])

    def get_active_level(self) -> int:
        return int(self.account_data.get("activeLevel") or 0)

    def get_completed_task_ids(self) -> list:
        return self.account_data.get("completedTaskIds", [])

    async def ping(self):
        try:
            await self.api.call("/user/ping")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Check-in (DENGAN RETRY)
    # ------------------------------------------------------------------

    def _get_checkin_days(self) -> tuple[str, str]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = datetime.fromtimestamp(
            now_ts() - 86400, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        return today, yesterday

    async def _sleep_countdown(self, seconds: int, slot: str, title: str):
        """Sleep dengan countdown di dashboard."""
        remaining = int(seconds)
        while remaining > 0:
            await activity(self.account_id, slot, "WAIT",
                           f"{title} | {remaining:02d}s")
            await asyncio.sleep(min(3, remaining))
            remaining -= 3

    async def check_in_daily(self, state: AccountState = None):
        """
        Check-in harian dengan retry otomatis.
        Retry kalau gagal karena human check / Turnstile issue.
        """
        user = self.user()
        today, yesterday = self._get_checkin_days()

        if user.get("checkinLastDay") == today:
            await activity(self.account_id, "TASK", "SKIP",
                           "Sudah check-in hari ini")
            return

        streak = (
            (int(user.get("checkinStreak") or 0) + 1)
            if user.get("checkinLastDay") == yesterday
            else 1
        )
        day = ((streak - 1) % len(CHECKIN_REWARDS)) + 1
        expected_reward = CHECKIN_REWARDS[day - 1]

        # Pre-solve Turnstile kalau expired
        if CHECKIN_PRE_SOLVE and not self.is_human_check_valid():
            await activity(self.account_id, "TASK", "SOLVE",
                           "Solve Turnstile dulu...")
            await self.ensure_turnstile(force=True, state=state)

        # Retry loop
        for attempt in range(1, CHECKIN_RETRY_MAX + 1):
            attempt_info = ""
            if attempt > 1:
                attempt_info = f" [{attempt}/{CHECKIN_RETRY_MAX}]"

            await activity(self.account_id, "TASK", "CLAIM",
                           f"Day {day} (streak {streak}){attempt_info}")

            # Refresh Turnstile tiap retry
            if attempt > 1 and CHECKIN_REFRESH_TURNSTILE:
                await activity(self.account_id, "TASK", "REFRESH",
                               "Refresh Turnstile...")
                await self.ensure_turnstile(force=True, state=state)

            # Coba check-in
            try:
                result = await self.api.call("/user/daily-checkin")
            except Exception as e:
                log_warn(self.account_id, f"Check-in exception: {e}")
                result = {"success": False, "error": str(e)}

            # Sukses?
            if result.get("success") and not result.get("code"):
                if result.get("user"):
                    self.account_data["user"] = result["user"]

                reward = result.get("reward", expected_reward)
                await activity(self.account_id, "TASK", "SUCCESS",
                               f"Day {day} +{reward} MRG")
                log_info(self.account_id,
                         f"Check-in day {day} +{reward} MRG "
                         f"(attempt {attempt})")
                return

            # Cek error
            code = result.get("code", "")
            err_msg = str(result.get("error") or "").lower()

            is_human_error = (
                code == HUMAN_REQUIRED_CODE
                or "security check" in err_msg
                or "human" in err_msg
                or "captcha" in err_msg
                or "turnstile" in err_msg
            )

            # Bukan human error → skip retry
            if not is_human_error:
                err = str(result.get("error") or "")[:60]
                await activity(self.account_id, "TASK", "FAILED", err)
                log_warn(self.account_id,
                         f"Check-in gagal (non-retryable): {err}")
                return

            log_warn(self.account_id,
                     f"Check-in butuh human check (attempt {attempt}): "
                     f"{err_msg[:50]}")

            # Retry terakhir → menyerah
            if attempt >= CHECKIN_RETRY_MAX:
                await activity(self.account_id, "TASK", "SKIP",
                               f"Gagal {CHECKIN_RETRY_MAX}x, skip")
                log_warn(self.account_id,
                         f"Check-in gagal setelah {CHECKIN_RETRY_MAX} percobaan")
                return

            # Solve Turnstile
            await activity(self.account_id, "TASK", "SOLVE",
                           "Solve Turnstile...")
            ok = await self.ensure_turnstile(force=True, state=state)

            # Tunggu sebelum retry (baik Turnstile OK maupun gagal)
            delay = random.uniform(CHECKIN_RETRY_DELAY_MIN,
                                   CHECKIN_RETRY_DELAY_MAX)
            if not ok:
                log_warn(self.account_id,
                         f"Turnstile gagal, tunggu {delay:.0f}s")
                await self._sleep_countdown(
                    int(delay), "TASK", "Turnstile gagal, wait"
                )
            else:
                await self._sleep_countdown(
                    int(delay), "TASK", "Retry in"
                )

    # ------------------------------------------------------------------
    # Mining (DENGAN RETRY)
    # ------------------------------------------------------------------

    async def claim_mining(self, state: AccountState = None):
        user = self.user()
        pending = Decimal(str(user.get("unclaimedMiningBalance") or 0))

        if pending <= Decimal(str(MINIMUM_CLAIMABLE_MINING)):
            await activity(self.account_id, "MINING", "SKIP",
                           f"Pending {pending} < min")
            return

        # Retry loop
        for attempt in range(1, MINING_RETRY_MAX + 1):
            attempt_info = ""
            if attempt > 1:
                attempt_info = f" [{attempt}/{MINING_RETRY_MAX}]"

            await activity(self.account_id, "MINING", "CLAIM",
                           f"Pending={pending} MRG{attempt_info}")

            if attempt > 1 and MINING_REFRESH_TURNSTILE:
                await self.ensure_turnstile(force=True, state=state)

            try:
                result = await self.api.call("/user/claim-mining")
            except Exception as e:
                log_warn(self.account_id, f"Mining exception: {e}")
                result = {"success": False, "error": str(e)}

            # Sukses?
            if result.get("success") and not result.get("code"):
                if result.get("user"):
                    self.account_data["user"] = result["user"]

                claimed = result.get("claimedAmount", "?")
                await activity(self.account_id, "MINING", "SUCCESS",
                               f"+{claimed} MRG")
                log_info(self.account_id,
                         f"Claim mining +{claimed} MRG (attempt {attempt})")
                return

            # Cek error
            code = result.get("code", "")
            err_msg = str(result.get("error") or "").lower()

            is_human_error = (
                code == HUMAN_REQUIRED_CODE
                or "security check" in err_msg
                or "human" in err_msg
                or "captcha" in err_msg
                or "turnstile" in err_msg
            )

            if not is_human_error:
                err = str(result.get("error") or "")[:60]
                await activity(self.account_id, "MINING", "FAILED", err)
                return

            log_warn(self.account_id,
                     f"Mining butuh human check (attempt {attempt})")

            if attempt >= MINING_RETRY_MAX:
                await activity(self.account_id, "MINING", "SKIP",
                               f"Gagal {MINING_RETRY_MAX}x, skip")
                return

            # Solve Turnstile
            await self.ensure_turnstile(force=True, state=state)

            delay = random.uniform(MINING_RETRY_DELAY_MIN,
                                   MINING_RETRY_DELAY_MAX)
            await self._sleep_countdown(int(delay), "MINING", "Retry in")

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def _get_task_cooldown_ms(self, task: dict) -> int:
        task_type = task.get("taskType")
        hours = TASK_COOLDOWN_HOURS.get(task_type, DEFAULT_TASK_COOLDOWN_HOURS)
        return hours * 60 * 60 * 1000

    def _is_task_on_cooldown(self, task: dict) -> bool:
        claimed_at = self.task_claims.get(str(task.get("taskId")), 0)
        return claimed_at + self._get_task_cooldown_ms(task) > now_ts() * 1000

    def _is_hold_task(self, task: dict) -> bool:
        return task.get("verificationType") in HOLD_TASK_TYPES

    def _is_task_claimable(self, task: dict) -> bool:
        if task.get("isPaused"):
            return False
        if self._is_hold_task(task):
            return False
        task_type = task.get("taskType")
        if not task_type or task_type == "one_time":
            return (
                task.get("taskId") not in self.get_completed_task_ids()
                and not self._is_task_on_cooldown(task)
            )
        return not self._is_task_on_cooldown(task)

    def _get_task_url(self, task: dict) -> str:
        user_id = str(self.tg_id or "0")
        url = str(task.get("url") or "")
        import re
        url = re.sub(r"REFCODE", user_id, url)
        url = re.sub(r"(startapp=ref_)[A-Za-z0-9_]+", rf"\g<1>{user_id}", url)
        url = re.sub(r"(startapp%3Dref_)[A-Za-z0-9_]+", rf"\g<1>{user_id}", url)
        return url

    def _record_task_claim(self, task_id: str, state: AccountState):
        self.task_claims[task_id] = int(now_ts() * 1000)
        state.task_claims = self.task_claims

    async def complete_tasks(self, state: AccountState) -> int:
        all_tasks = self.tasks()
        if not all_tasks:
            await activity(self.account_id, "TASK", "SKIP",
                           "Tidak ada task")
            return 0

        claimable = [t for t in all_tasks if self._is_task_claimable(t)]

        if not claimable:
            await activity(self.account_id, "TASK", "SKIP",
                           "Semua task di-cooldown / done")
            return self._next_task_reset(all_tasks)

        for task in claimable:
            try:
                await self._complete_task(task, state)
            except Exception as e:
                log_warn(self.account_id,
                         f"Task '{task.get('title')}' error: {e}")
            await asyncio.sleep(3)

        return self._next_task_reset(all_tasks)

    def _next_task_reset(self, tasks: list) -> int:
        now_ms = int(now_ts() * 1000)
        earliest = None
        for task in tasks:
            claimed_at = self.task_claims.get(str(task.get("taskId")), 0)
            if not claimed_at:
                continue
            reset_at = claimed_at + self._get_task_cooldown_ms(task)
            if reset_at > now_ms:
                if earliest is None or reset_at < earliest:
                    earliest = reset_at
        return int(earliest / 1000) if earliest else 0

    def _is_telegram_url(self, url: str) -> bool:
        """Cek apakah URL adalah link Telegram (t.me / telegram.me)."""
        if not url:
            return False
        return "t.me/" in url or "telegram.me/" in url

    async def _complete_task(self, task: dict, state: AccountState):
        title = task.get("title", "?")
        reward = task.get("reward", 0)
        task_id = str(task.get("taskId"))

        await activity(self.account_id, "TASK", "RUNNING",
                       f"{title[:35]}")

        if not self._is_hold_task(task):
            url = self._get_task_url(task)

            # Hanya join kalau URL Telegram
            if url and self.tg and self._is_telegram_url(url):
                await self._join_telegram_link(url)

            # Dwell untuk semua task non-hold (Twitter/YouTube/Telegram)
            await activity(self.account_id, "TASK", "DWELL",
                           f"{title[:30]} | wait {TASK_DWELL_SECONDS}s")
            await asyncio.sleep(TASK_DWELL_SECONDS)

        result = await self.api.call("/user/claim-task", {"taskId": task_id})

        # Human check?
        if result.get("code") == HUMAN_REQUIRED_CODE:
            ok = await self.ensure_turnstile(force=True, state=state)
            if not ok:
                await activity(self.account_id, "TASK", "FAILED",
                               f"{title[:30]}: Turnstile gagal")
                return
            result = await self.api.call("/user/claim-task",
                                          {"taskId": task_id})

        if result.get("success"):
            self._record_task_claim(task_id, state)
            await activity(self.account_id, "TASK", "SUCCESS",
                           f"{title[:35]} +{reward} MRG")
            log_info(self.account_id,
                     f"Claimed '{title}' +{reward} MRG")
        else:
            err = str(result.get("error") or "")[:50]
            await activity(self.account_id, "TASK", "FAILED",
                           f"{title[:30]}: {err}")
            log_warn(self.account_id, f"Task '{title}' gagal: {err}")

        await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Squad
    # ------------------------------------------------------------------

    async def claim_squad_rewards(self):
        friends_result = await self.api.call("/user/friends")
        team_stats = (friends_result or {}).get("teamStats", {})

        bonus = Decimal(str(team_stats.get("unclaimedOneTimeBonusMRG") or 0))
        if bonus > 0:
            await activity(self.account_id, "SQUAD", "CLAIM",
                           f"Bonus {bonus} MRG")
            result = await self.api.call("/user/claim-one-time-bonus")
            if result.get("success"):
                await activity(self.account_id, "SQUAD", "SUCCESS",
                               f"Bonus +{bonus} MRG")
            else:
                await activity(self.account_id, "SQUAD", "FAILED",
                               str(result.get("error"))[:50])
        else:
            await activity(self.account_id, "SQUAD", "SKIP",
                           "Tidak ada bonus")

        commission = Decimal(str(
            self.user().get("unclaimedTeamCommission") or 0
        ))
        if commission > 0:
            await activity(self.account_id, "SQUAD", "CLAIM",
                           f"Commission {commission} MRG")
            result = await self.api.call("/user/claim-commission")
            if result.get("success"):
                if result.get("user"):
                    self.account_data["user"] = result["user"]
                await activity(self.account_id, "SQUAD", "SUCCESS",
                               f"Commission +{commission} MRG")
            else:
                await activity(self.account_id, "SQUAD", "FAILED",
                               str(result.get("error"))[:50])

    # ------------------------------------------------------------------
    # Join Telegram link
    # ------------------------------------------------------------------

    async def _join_telegram_link(self, link: str) -> bool:
        if not self.tg or not link:
            return False

        username = None
        try:
            parts = link.rstrip("/").split("/")
            for part in parts:
                if part and part not in ("t.me", "telegram.me",
                                          "http:", "https:") \
                   and not part.startswith("?"):
                    username = part
                    break
        except Exception:
            return False

        if not username:
            return False

        if username in self._joined_channels:
            return True

        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            entity = await self.tg.get_entity(username)
            await self.tg(JoinChannelRequest(entity))
            self._joined_channels.add(username)
            log_info(self.account_id, f"Joined @{username}")
            return True
        except Exception as e:
            err = str(e).lower()
            if "already" in err or "participant" in err:
                self._joined_channels.add(username)
                return True
            log_warn(self.account_id, f"Gagal join {username}: {e}")
            return False

    # ------------------------------------------------------------------
    # Update ACCOUNT row
    # ------------------------------------------------------------------

    async def update_account_row(self, status: str = "READY"):
        user = self.user()
        active_level = self.get_active_level()
        balance = user.get("inAppBalance", 0)
        pending = user.get("unclaimedMiningBalance", 0)
        streak = user.get("checkinStreak", 0)

        detail = (
            f"Lv={active_level} | "
            f"Speed={get_miner_speed(active_level):.2f} TH/s | "
            f"Daily={get_miner_daily_output(active_level):.2f} | "
            f"Bal={balance} | Pending={pending} | Streak={streak}"
        )
        await activity(self.account_id, "ACCOUNT", status, detail)

    async def update_balance_row(self):
        user = self.user()
        in_app = user.get("inAppBalance") or 0
        lifetime = user.get("totalMinedLifetime") or 0
        wallet_bal = user.get("tonWalletBalance") or 0
        wallet_addr = user.get("tonWalletAddress")
        level = self.get_active_level()
        speed = get_miner_speed(level)

        def fmt(v):
            try:
                f = float(v)
                if f >= 1000:
                    return f"{f:,.2f}"
                if f >= 1:
                    return f"{f:.2f}"
                return f"{f:.6f}"
            except (TypeError, ValueError):
                return str(v)

        parts = [f"In-App {fmt(in_app)}"]

        # Wallet hanya tampil kalau terhubung
        if wallet_addr and wallet_bal:
            parts.append(f"Wallet {fmt(wallet_bal)}")

        if lifetime:
            parts.append(f"Lifetime {fmt(lifetime)}")

        parts.append(f"Lv{level} ({speed:.2f} TH/s)")

        detail = " | ".join(parts)
        await activity(self.account_id, "BALANCE", "READY", detail)

    # ------------------------------------------------------------------
    # Process (satu cycle)
    # ------------------------------------------------------------------

    async def process(self, state: AccountState) -> int:
        # Restore state
        self.task_claims = state.task_claims or {}
        self.human_verified_until = state.human_verified_until or 0

        # 1. Ensure Telegram
        if not self.tg:
            await self.connect(require_login=True)

        # 2. Login
        await self.login()

        # 3. Ping presence
        await self.ping()

        # 4. Update ACCOUNT
        await self.update_account_row("READY")

        # 5. Update BALANCE 
        await self.update_balance_row()

        # 6. Check-in (dengan retry)
        await self.check_in_daily(state)

        # 7. Mining (dengan retry)
        await self.claim_mining(state)

        # 8. Tasks
        next_task_reset = await self.complete_tasks(state)

        # 9. Squad
        await self.claim_squad_rewards()

        # 10. Refresh account
        await self.load_account()
        await self.update_account_row("READY")
        await self.update_balance_row()

        # Save state
        state.last_balance = float(self.user().get("inAppBalance") or 0)
        state.last_level = self.get_active_level()
        state.cycles_run += 1
        state.last_run_ts = int(now_ts())
        state.task_claims = self.task_claims
        state.human_verified_until = self.human_verified_until
        state.consecutive_failures = 0

        await activity(self.account_id, "ACCOUNT", "SUCCESS",
                       f"Cycle done | Bal={state.last_balance}")

        # Hitung wait
        now = now_ts()
        candidates = []
        if next_task_reset and next_task_reset > now:
            candidates.append(next_task_reset - now)

        snapshot = self.user().get("miningSnapshot") or {}
        snapshot_ts = snapshot.get("timestamp")
        if snapshot_ts:
            start = parse_iso(snapshot_ts)
            freeze_at = start + MINING_WINDOW_SECONDS
            if freeze_at > now:
                candidates.append(freeze_at - now)

        if candidates:
            wait = min(candidates)
        else:
            wait = 3600

        wait = max(MIN_WAIT, min(wait, MAX_WAIT))
        wait += random.randint(30, 120)
        return int(wait)


# =====================================================================
# WORKER
# =====================================================================

async def run_account_cycle(account_id: str, state_mgr: StateManager) -> int:
    state = state_mgr.load(account_id)
    client = MRGClient(account_id)
    log_info(account_id, "Cycle dimulai")
    try:
        wait = await client.process(state)
        return wait
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        state.consecutive_failures += 1
        wait = min(900 * (2 ** (state.consecutive_failures - 1)), 14400)
        log_warn(account_id,
                 f"Server down (#{state.consecutive_failures}), "
                 f"wait {wait//60}m")
        await activity(account_id, "ACCOUNT", "WAIT",
                       f"Server down #{state.consecutive_failures} | "
                       f"wait {wait//60}m")
        return wait
    except Exception as e:
        state.consecutive_failures += 1
        log_error(account_id, "Cycle error", e)
        msg = str(e).strip() or type(e).__name__
        await activity(account_id, "ACCOUNT", "ERROR", msg[:70])
        wait = min(600 * (2 ** (state.consecutive_failures - 1)), 7200)
        return wait
    finally:
        state_mgr.save(state)
        await client.close()


async def run_account_worker(account_id: str, state_mgr: StateManager):
    while True:
        wait = await run_account_cycle(account_id, state_mgr)

        remaining = wait
        while remaining > 0:
            h = remaining // 3600
            m = (remaining % 3600) // 60
            s = remaining % 60
            await activity(account_id, "ACCOUNT", "WAIT",
                           f"Next cycle in {h:02d}:{m:02d}:{s:02d}")
            await asyncio.sleep(min(60, remaining))
            remaining -= 60


async def _staggered_worker(account_id: str, state_mgr: StateManager,
                             delay: int):
    if delay > 0:
        await asyncio.sleep(delay)
    await run_account_worker(account_id, state_mgr)


# =====================================================================
# GET INITDATA MODE
# =====================================================================

async def get_pass_mode(account_id: str):
    print(f"\n🔑 Fetch initData — {account_id}\n")
    client = MRGClient(account_id)
    try:
        await client.connect(require_login=True)
        init_data = await client.fetch_webapp_query()
        print(f"✅ initData OK ({len(init_data)} chars)")
    finally:
        await client.close()


async def get_pass_all_mode():
    accounts = sorted(p.stem for p in SESSIONS_DIR.glob("acc_*.session"))
    if not accounts:
        print("❌ Tidak ada akun")
        sys.exit(1)
    for idx, acc in enumerate(accounts, 1):
        print(f"\n[{idx}/{len(accounts)}] {acc}")
        try:
            await get_pass_mode(acc)
        except Exception as e:
            print(f"❌ {acc}: {e}")


# =====================================================================
# ADD ACCOUNT MODE
# =====================================================================

async def add_account_mode():
    print()
    print("=" * 70)
    print("  ➕ TAMBAH AKUN BARU (MRG)")
    print("=" * 70)
    print()

    existing = sorted(p.stem for p in SESSIONS_DIR.glob("acc_*.session"))
    next_num = 1
    while f"acc_{next_num:03d}" in existing:
        next_num += 1
    account_id = f"acc_{next_num:03d}"

    print(f"Akun berikutnya: {account_id}")
    print()
    confirm = input("Lanjut? (y/n): ").strip().lower()
    if confirm != "y":
        print("Dibatalkan.")
        return

    client = MRGClient(account_id)
    try:
        await client.connect(require_login=True)
        print()
        print("📥 Fetch initData...")
        try:
            await client.fetch_webapp_query()
            print("✅ initData disimpan")
        except Exception as e:
            print(f"⚠️  Gagal fetch initData: {e}")
    finally:
        await client.close()

    print()
    print("=" * 70)
    print(f"  ✅ {account_id} siap")
    print("=" * 70)


# =====================================================================
# MAIN
# =====================================================================

def get_existing_accounts() -> list[str]:
    return sorted(p.stem for p in SESSIONS_DIR.glob("acc_*.session"))


async def run_farmer():
    log_info("main", "Main loop dimulai")
    print()
    print("=" * 70)
    print("  ⛏️  MRG FARMER — AUTO MODE")
    print("=" * 70)
    print()

    accounts = get_existing_accounts()
    if not accounts:
        print("Belum ada akun. Tambah dulu:")
        print("  python mrg.py --add")
        sys.exit(0)

    DASHBOARD.accounts = accounts
    for account in accounts:
        DASHBOARD.register(account)

    DASHBOARD.start()
    DASHBOARD.render()

    try:
        state_mgr = StateManager(DATA_DIR)
        tasks = []
        for idx, acc in enumerate(accounts):
            delay = idx * STAGGER_SECONDS
            tasks.append(_staggered_worker(acc, state_mgr, delay))
        await asyncio.gather(*tasks)
    except SystemExit:
        log_warn("main", "Worker exit")
    except Exception as e:
        log_error("main", "run_farmer exception", e)
    finally:
        DASHBOARD.stop()
        log_info("main", "Main loop selesai")


def print_help():
    print(__doc__)
    print()
    print("Contoh:")
    print("  python mrg.py --add          → tambah akun baru")
    print("  python mrg.py                → start farmer")
    print("  python mrg.py pass acc_001   → fetch initData 1 akun")
    print("  python mrg.py pass-all       → fetch initData semua akun")


if __name__ == "__main__":
    try:
        args = sys.argv[1:]

        if not args:
            asyncio.run(run_farmer())
        elif args[0] in ("--add", "add"):
            asyncio.run(add_account_mode())
        elif args[0] == "pass":
            if len(args) < 2:
                print("Usage: python mrg.py pass <account_id>")
                sys.exit(1)
            asyncio.run(get_pass_mode(args[1]))
        elif args[0] == "pass-all":
            asyncio.run(get_pass_all_mode())
        elif args[0] in ("-h", "--help", "help"):
            print_help()
        else:
            print(f"❌ Argumen tidak dikenal: {args[0]}")
            print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        LOGGER.info("Bot dihentikan oleh user")
        print()
        print("Bot dihentikan.")
    except Exception as e:
        LOGGER.critical(f"FATAL: {type(e).__name__}: {e}")
        LOGGER.critical(traceback.format_exc())
        print(f"\n❌ Bot crash: {e}")
        print(f"Cek detail di: {LOG_PATH}")
        raise
