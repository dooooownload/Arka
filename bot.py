# -*- coding: utf-8 -*-
"""
🎬 دانلودر آرکا — Universal Premium Downloader
Version 5.3.0 — Pro Music Edition
Made with ❤️ by @AMIRALI_IRX
"""

from __future__ import annotations

import asyncio, contextlib, html, logging, os, random, re, shutil
import sqlite3, subprocess, sys, threading, time, uuid, zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yt_dlp
try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except ImportError:
    ImpersonateTarget = None

try:
    import curl_cffi  # noqa: F401
    HAS_CURL_CFFI = True
except Exception:
    HAS_CURL_CFFI = False

try:
    import gallery_dl
    HAS_GALLERY_DL = True
except ImportError:
    gallery_dl = None
    HAS_GALLERY_DL = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand, CallbackQuery, FSInputFile, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware
except Exception:
    BaseRequestMiddleware = object
from pydantic_settings import BaseSettings, SettingsConfigDict


# ══════════════════════════════════════════════════════════════
# AUTO VERSION
# ══════════════════════════════════════════════════════════════
def _detect_version() -> str:
    try:
        content = Path(__file__).read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'Version\s+([\d]+\.[\d]+(?:\.[\d]+)?)', content)
        return m.group(1) if m else "0.0.0"
    except Exception:
        return "0.0.0"


FILE_VERSION = _detect_version()


# ══════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backups"
UPDATE_DIR = BASE_DIR / "updates"
ENV_FILE = BASE_DIR / ".env"

for _d in (DATA_DIR, DOWNLOAD_DIR, LOG_DIR, BACKUP_DIR, UPDATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

LOCAL_TG_API = "http://127.0.0.1:8081"
LOCAL_TG_DATA = DATA_DIR / "tg-api"
PHOTO_TG_LIMIT = 9 * 1024 * 1024


# ══════════════════════════════════════════════════════════════
# TERMINAL
# ══════════════════════════════════════════════════════════════
if os.name == "nt":
    os.system("")


class C:
    R = "\033[0m"; B = "\033[1m"; D = "\033[2m"
    RED = "\033[91m"; GRN = "\033[92m"; YEL = "\033[93m"
    BLU = "\033[94m"; MAG = "\033[95m"; CYN = "\033[96m"


def print_banner():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(
        f"\n{C.CYN}{C.B}"
        f"   █████╗ ██████╗ ██╗  ██╗ █████╗\n"
        f"  ██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗\n"
        f"  ███████║██████╔╝█████╔╝ ███████║\n"
        f"  ██╔══██║██╔══██╗██╔═██╗ ██╔══██║\n"
        f"  ██║  ██║██║  ██║██║  ██╗██║  ██║\n"
        f"  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝\n{C.R}\n"
        f"{C.MAG}{C.B}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}\n"
        f"  {C.YEL}⚡{C.R} {C.B}Version{C.R}  {C.CYN}{FILE_VERSION}{C.R}"
        f"      {C.YEL}👤{C.R} {C.B}Owner{C.R}  {C.CYN}@AMIRALI_IRX{C.R}"
        f"      {C.YEL}💎{C.R} {C.B}System{C.R}  {C.GRN}Premium{C.R}\n"
        f"{C.MAG}{C.B}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}\n\n"
    )
    sys.stdout.flush()


def log_step(label: str, value: str, ok: bool = True):
    icon = f"{C.GRN}✓{C.R}" if ok else f"{C.RED}✗{C.R}"
    sys.stdout.write(f"  {C.D}│{C.R} {icon} {label:<20} {C.D}{value}{C.R}\n")
    sys.stdout.flush()


def log_ok(msg: str):
    sys.stdout.write(f"  {C.GRN}✓ {msg}{C.R}\n")
    sys.stdout.flush()


def log_err(msg: str):
    sys.stdout.write(f"  {C.RED}✗ {msg}{C.R}\n")
    sys.stdout.flush()


def log_warn(msg: str):
    sys.stdout.write(f"  {C.YEL}⚠ {msg}{C.R}\n")
    sys.stdout.flush()


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def fmt_bytes(v) -> str:
    if not v:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{v:.1f} PB"


def fmt_duration(s) -> str:
    if not s:
        return "—"
    try:
        s = int(s)
    except (TypeError, ValueError):
        return "—"
    h, m, x = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{x:02d}" if h else f"{m:02d}:{x:02d}"


def progress_bar(p: float, length: int = 12) -> str:
    try:
        p = max(0.0, min(100.0, float(p)))
    except (TypeError, ValueError):
        p = 0.0
    filled = int(length * p / 100)
    if p >= 100:
        return "🟩" * length
    return "🟩" * filled + ("🟨" if filled < length else "") + \
           "⬜" * max(0, length - filled - 1)


def now_ts() -> float:
    return time.time()


def fmt_time(ts) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except Exception:
        return "—"


def fmt_dt_short(ts) -> str:
    try:
        return time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
    except Exception:
        return "unknown"


def safe_cb(data: str) -> str:
    if data is None:
        return ""
    b = data.encode("utf-8")
    if len(b) <= 64:
        return data
    truncated = b[:64]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""


def new_id() -> str:
    return uuid.uuid4().hex[:8].upper()


_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def is_valid_url(t: str) -> bool:
    return bool(_URL_RE.match((t or "").strip()))


# ══════════════════════════════════════════════════════════════
# PHOTO / VIDEO / AUDIO SUPPORT
# ══════════════════════════════════════════════════════════════
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif",
              ".bmp", ".tiff", ".heic", ".svg", ".avif")

VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv", ".m4v",
              ".avi", ".3gp", ".flv", ".ts", ".mpeg", ".mpg")

AUDIO_EXTS = (".mp3", ".m4a", ".opus", ".ogg",
              ".flac", ".wav", ".aac", ".wma")

IMAGE_HOST_HINTS = (
    "pinimg.com", "i.imgur.com", "images.unsplash.com",
    "cdninstagram.com", "fbcdn.net", "pbs.twimg.com",
    "pixabay.com", "pexels.com", "wikimedia.org",
    "ggpht.com", "staticflickr.com", "imagebam.com",
    "postimg.cc", "imgbox.com", "flickr.com",
)

_IMG_CTYPE_EXT = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg",
    "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "image/bmp": ".bmp",
    "image/tiff": ".tiff", "image/heic": ".heic",
    "image/avif": ".avif", "image/svg+xml": ".svg",
}


def is_direct_image_url(url: str) -> bool:
    low = (url or "").lower().split("?")[0].split("#")[0]
    if low.endswith(IMAGE_EXTS):
        return True
    return any(h in low for h in IMAGE_HOST_HINTS)


def is_image_file(path) -> bool:
    try:
        return Path(path).suffix.lower() in IMAGE_EXTS
    except Exception:
        return False


def is_video_file(path) -> bool:
    try:
        return Path(path).suffix.lower() in VIDEO_EXTS
    except Exception:
        return False


def is_audio_file(path) -> bool:
    try:
        return Path(path).suffix.lower() in AUDIO_EXTS
    except Exception:
        return False


def cleanup_empty_dir(path_like) -> bool:
    try:
        p = Path(path_like)
        if p.exists() and p.is_dir() and not any(p.iterdir()):
            p.rmdir()
            return True
    except Exception:
        pass
    return False


def _probe_duration(path: Path) -> int:
    if not shutil.which("ffprobe"):
        return 0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30,
        )
        val = (r.stdout or "").strip()
        if val and val not in ("N/A", "nan"):
            return int(float(val))
    except Exception:
        pass
    return 0


def compress_image_for_tg(path: Path, max_bytes: int = PHOTO_TG_LIMIT) -> Path:
    if not HAS_PIL:
        return path
    try:
        if not path.exists() or path.stat().st_size <= max_bytes:
            return path
    except Exception:
        return path
    try:
        img = Image.open(path)
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        out = path.with_name(path.stem + "_tg.jpg")
        for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
            if scale < 1.0:
                ns = (max(1, int(img.width * scale)),
                      max(1, int(img.height * scale)))
                cur = img.resize(ns, Image.LANCZOS)
            else:
                cur = img
            for q in (88, 78, 68, 55, 45, 35):
                try:
                    cur.save(out, "JPEG", quality=q, optimize=True)
                except Exception:
                    continue
                if out.stat().st_size <= max_bytes:
                    return out
        if out.exists():
            return out
    except Exception as e:
        logging.warning(f"compress failed: {e}")
    return path


async def download_tg_file(bot: Bot, file_id: str, dest: Path) -> None:
    tg_file = await bot.get_file(file_id)
    file_path = (tg_file.file_path or "").strip()
    if file_path.startswith("/var/lib/telegram-bot-api/"):
        rel = file_path[len("/var/lib/telegram-bot-api/"):]
        for src in (LOCAL_TG_DATA / rel,
                    Path("/var/lib/telegram-bot-api") / rel):
            if src.exists() and src.is_file():
                shutil.copy2(src, dest)
                return
        raise FileNotFoundError("Local TG API file not accessible")
    await bot.download_file(file_path, dest)


# ══════════════════════════════════════════════════════════════
# EMOJI
# ══════════════════════════════════════════════════════════════
_NORMAL_EMOJI_RE = re.compile(
    "(?:"
    "[\U0001F1E0-\U0001F1FF]"
    "|[\U0001F300-\U0001F5FF]"
    "|[\U0001F600-\U0001F64F]"
    "|[\U0001F680-\U0001F6FF]"
    "|[\U0001F700-\U0001F77F]"
    "|[\U0001F780-\U0001F7FF]"
    "|[\U0001F800-\U0001F8FF]"
    "|[\U0001F900-\U0001F9FF]"
    "|[\U0001FA00-\U0001FAFF]"
    "|[\U00002600-\U000026FF]"
    "|[\U00002700-\U000027BF]"
    "|[\U00002B00-\U00002BFF]"
    ")[\U0001F3FB-\U0001F3FF\uFE0F]?", re.UNICODE
)

_TG_EMOJI_TAG_RE = re.compile(
    r'<tg-emoji\s+emoji-id="[^"]*">.*?</tg-emoji>', re.DOTALL
)

_TG_EMOJI_STRIP_RE = re.compile(
    r'<tg-emoji\s+emoji-id="[^"]*">(.*?)</tg-emoji>', re.DOTALL
)


def extract_premium_emojis(message: Message):
    out = []
    try:
        text = message.text or message.caption or ""
        ents = list(getattr(message, "entities", None) or [])
        ents += list(getattr(message, "caption_entities", None) or [])
        for ent in ents:
            cid = str(getattr(ent, "custom_emoji_id", "") or "").strip()
            if not cid:
                continue
            off = int(getattr(ent, "offset", 0) or 0)
            ln = int(getattr(ent, "length", 0) or 0)
            fb = ""
            if text:
                raw = text.encode("utf-16-le")
                fb = raw[off * 2:(off + ln) * 2].decode(
                    "utf-16-le", errors="ignore")
            if not fb or not fb.strip():
                fb = "✨"
            out.append((cid, fb))
    except Exception as e:
        logging.warning(f"extract_premium_emojis failed: {e}")
    return out


def extract_normal_emojis(text: str):
    if not text:
        return []
    return _NORMAL_EMOJI_RE.findall(text)


# ══════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )
    bot_token: str = ""
    owner_ids: str = ""
    bot_name: str = "دانلودر آرکا"
    owner_username: str = "@AMIRALI_IRX"

    @property
    def db_path(self) -> Path:
        return DATA_DIR / "bot.db"

    @property
    def cookies_file(self) -> Path:
        return DATA_DIR / "cookies.txt"


CFG: Optional[Settings] = None
DB_PATH: Path = DATA_DIR / "bot.db"
OWNER_IDS: list = []


# ══════════════════════════════════════════════════════════════
# DOCKER MANAGER
# ══════════════════════════════════════════════════════════════
def ensure_docker_running(api_id: str, api_hash: str):
    print(f"  {C.CYN}⏳ Checking local Telegram server (Docker)...{C.R}")
    VOLUME = "telegram-bot-api-data"
    IMAGE = "aiogram/telegram-bot-api:latest"

    def _sh(*args, timeout=30):
        try:
            return subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=timeout)
        except Exception:
            return None

    def _api_alive(timeout=3) -> bool:
        import urllib.request, urllib.error
        try:
            urllib.request.urlopen("http://127.0.0.1:8081/", timeout=timeout)
            return True
        except urllib.error.HTTPError as e:
            return e.code in (401, 404)
        except Exception:
            return False

    try:
        res = _sh("docker", "inspect", "-f",
                  "{{.State.Running}}", "telegram-bot-api")
        running = res is not None and "true" in (res.stdout or "").lower()
        if running and _api_alive():
            log_step("Docker", "telegram-bot-api is alive")
            return
        _sh("docker", "rm", "-f", "telegram-bot-api")
        log_step("Docker", "Starting telegram-bot-api (network=host)...")
        _sh("docker", "run", "-d",
            "--name", "telegram-bot-api", "--restart=always",
            "--network", "host",
            "-v", f"{VOLUME}:/var/lib/telegram-bot-api",
            "-e", f"TELEGRAM_API_ID={api_id}",
            "-e", f"TELEGRAM_API_HASH={api_hash}",
            "-e", "TELEGRAM_LOCAL=1", IMAGE, timeout=60)
        for i in range(20):
            time.sleep(1)
            if _api_alive(timeout=2):
                log_step("Docker", f"Telegram API online ({i+1}s)")
                return
        log_warn("Telegram API didn't respond in 20s")
    except Exception as e:
        log_warn(f"Docker auto-start warning: {e}")


def load_settings() -> Settings:
    global CFG, DB_PATH, OWNER_IDS
    env_token = os.getenv("BOT_TOKEN", "").strip()
    env_owners = os.getenv("OWNER_IDS", "").strip()
    api_id = os.getenv("TELEGRAM_API_ID", "2040").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH",
                          "b18441a1ff607e10a989891a5462e627").strip()

    token = ""
    owner_ids_raw = ""

    if ENV_FILE.exists():
        try:
            from dotenv import dotenv_values
            env_data = dotenv_values(str(ENV_FILE))
            token = (env_data.get("BOT_TOKEN") or "").strip()
            owner_ids_raw = (env_data.get("OWNER_IDS")
                             or env_data.get("ADMIN_ID") or "").strip()
            api_id = (env_data.get("TELEGRAM_API_ID") or "2040").strip()
            api_hash = (env_data.get("TELEGRAM_API_HASH")
                        or "b18441a1ff607e10a989891a5462e627").strip()
        except Exception:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith(("OWNER_IDS=", "ADMIN_ID=")):
                        owner_ids_raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("TELEGRAM_API_ID="):
                        api_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("TELEGRAM_API_HASH="):
                        api_hash = line.split("=", 1)[1].strip().strip('"').strip("'")

    if env_token:
        token = env_token
    if env_owners:
        owner_ids_raw = env_owners

    if not token or ":" not in token:
        print_banner()
        print(f"\n  {C.CYN}{C.B}▸ Setup: Bot Token{C.R}\n")
        try:
            token = input(f"  {C.CYN}▸{C.R} {C.B}BOT_TOKEN{C.R}: ").strip()
        except (EOFError, KeyboardInterrupt):
            log_err("Cancelled")
            sys.exit(1)
        if not token or ":" not in token:
            log_err("Invalid token format")
            sys.exit(1)

    ids = []
    for x in owner_ids_raw.replace(",", " ").replace(";", " ").split():
        x = x.strip().lstrip("@")
        if x.isdigit() or (x.startswith("-") and x[1:].isdigit()):
            ids.append(int(x))

    if not ids:
        try:
            raw = input(f"  {C.CYN}▸{C.R} {C.B}OWNER_IDS{C.R}: ").strip()
        except (EOFError, KeyboardInterrupt):
            log_err("Cancelled")
            sys.exit(1)
        for x in raw.replace(",", " ").replace(";", " ").split():
            x = x.strip().lstrip("@")
            if x.isdigit() or (x.startswith("-") and x[1:].isdigit()):
                ids.append(int(x))
        if not ids:
            log_err("Invalid Owner ID")
            sys.exit(1)

    try:
        content = (
            "# Arka Downloader Configuration\n"
            f'BOT_TOKEN="{token}"\n'
            f'OWNER_IDS="{",".join(map(str, ids))}"\n'
            f'TELEGRAM_API_ID="{api_id}"\n'
            f'TELEGRAM_API_HASH="{api_hash}"\n'
            'BOT_NAME="دانلودر آرکا"\n'
            'OWNER_USERNAME="@AMIRALI_IRX"\n'
        )
        ENV_FILE.write_text(content, encoding="utf-8")
        with contextlib.suppress(Exception):
            os.chmod(ENV_FILE, 0o600)
    except Exception:
        pass

    os.environ["BOT_TOKEN"] = token
    os.environ["OWNER_IDS"] = ",".join(map(str, ids))
    ensure_docker_running(api_id, api_hash)
    s = Settings()
    CFG = s
    DB_PATH = s.db_path
    OWNER_IDS = ids
    return s


# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S", stream=sys.stdout)
logging.getLogger("aiogram.event").setLevel(logging.ERROR)
logging.getLogger("aiohttp.access").setLevel(logging.ERROR)
logging.getLogger("yt_dlp").setLevel(logging.ERROR)
logging.getLogger("gallery_dl").setLevel(logging.ERROR)


# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════
_local = threading.local()


def _make_conn():
    c = sqlite3.connect(str(DB_PATH), timeout=30,
                        isolation_level=None, check_same_thread=False)
    c.row_factory = sqlite3.Row
    with contextlib.suppress(Exception):
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=10000")
    return c


def get_conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = _make_conn()
        _local.conn = c
    return c


def close_conn():
    c = getattr(_local, "conn", None)
    if c is not None:
        with contextlib.suppress(Exception):
            c.close()
        _local.conn = None


@contextmanager
def transaction():
    c = get_conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        yield c
        c.execute("COMMIT")
    except Exception:
        with contextlib.suppress(Exception):
            c.execute("ROLLBACK")
        raise


MIGRATIONS = ["""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    downloads INTEGER NOT NULL DEFAULT 0,
    success_dl INTEGER NOT NULL DEFAULT 0,
    failed_dl INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
    is_vip INTEGER NOT NULL DEFAULT 0,
    lang TEXT NOT NULL DEFAULT 'fa',
    lang_chosen INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    quality TEXT NOT NULL DEFAULT 'best',
    duration INTEGER NOT NULL DEFAULT 0,
    filesize INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0,
    speed TEXT, eta TEXT, file_path TEXT, thumbnail TEXT,
    msg_id INTEGER, notice_msg_id INTEGER,
    delete_at REAL, error TEXT,
    created_at REAL NOT NULL,
    started_at REAL, finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at REAL NOT NULL,
    answered_at REAL
);
CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (user_id, job_id)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS custom_texts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits (
    user_id INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'video',
    hour_start REAL NOT NULL, hour_count INTEGER NOT NULL DEFAULT 0,
    day_start REAL NOT NULL, day_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, mode)
);
CREATE TABLE IF NOT EXISTS menu_buttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL, btn_key TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    is_visible INTEGER DEFAULT 1,
    color TEXT DEFAULT 'default',
    label TEXT, emoji_id TEXT, emoji_fb TEXT,
    created_at REAL NOT NULL,
    UNIQUE(scope, btn_key)
);
CREATE TABLE IF NOT EXISTS emoji_map (
    normal_emoji TEXT PRIMARY KEY,
    premium_id TEXT NOT NULL,
    fallback_emoji TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS custom_buttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL, callback TEXT NOT NULL,
    row_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS extra_admins (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER NOT NULL,
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER, action TEXT NOT NULL,
    details TEXT, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL, size INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS update_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL, prev_version TEXT,
    applied INTEGER NOT NULL DEFAULT 1,
    backup_path TEXT, note TEXT,
    created_at REAL NOT NULL
);
"""]


DEFAULT_SETTINGS = {
    "max_file_size_mb": "2048",
    "max_photo_size_mb": "2048",
    "max_dl_hour": "10",
    "max_dl_day": "50",
    "max_concurrent": "2",
    "delete_delay": "60",
    "max_retries": "2",
    "maintenance": "0",
    "maintenance_text": "🔧 ربات در حال تعمیر است.",
    "allowed_quality": (
        "best,4320p,2160p,1440p,1080p,720p,480p,360p,"
        "audio_best,audio,audio_320,audio_128"
    ),
    "broadcast_delay": "0.05",
    "send_thumbnail": "1",
    "download_subtitles": "0",
    "force_join": "0",
    "channel_username": "",
    "premium_emoji_enabled": "1",
    "start_emoji_id": "",
    "start_emoji_fb": "✨",
    "start_emoji_kind": "",
    "start_sticker_file_id": "",
    "start_sticker_enabled": "1",
    "bot_version": FILE_VERSION,
    "prev_version": "",
    "menu_cols_user": "2",
    "menu_cols_admin": "2",
    "menu_download": "1", "menu_history": "1", "menu_favs": "1",
    "menu_stats": "1", "menu_support": "1", "menu_help": "1",
    "menu_admin": "1",
    "miniapp_url": "", "miniapp_enabled": "0",
    "auto_backup_enabled": "0",
    "auto_backup_hours": "24",
    "auto_backup_last": "0",
    "show_custom_buttons": "1",
    "photo_download_enabled": "1",
    "video_download_enabled": "1",
    "music_download_enabled": "1",
    "max_photo_hour": "30",
    "max_photo_day": "200",
    "max_music_hour": "30",
    "max_music_day": "200",
    "music_send_as_audio": "1",
    "keep_state_after_download": "1",
    "photo_delete_delay": "60",
    "compress_large_photos": "1",
    "announce_enabled": "0",
    "announce_audience": "all",
    "announce_pin": "0",
    "announce_silent": "0",
    "announce_preview": "1",
    "announce_schedule": "",
    "announce_schedule_ts": "0",
    "announce_last_ts": "0",
    "announce_total_sent": "0",
    "announce_total_failed": "0",
    "announce_auto_delete": "0",
    "announce_delete_after": "3600",
    "announce_channel_id": "",
    "announce_channel_enabled": "0",
    "announce_channel_pin": "0",
    "announce_channel_silent": "0",
    "announce_channel_last_ts": "0",
    "announce_channel_total": "0",
    "limit_vip_unlimited": "1",
    "limit_owner_unlimited": "1",
    "limit_cooldown_sec": "3",
    "smart_quality": "1",
    "migration_v530_quality": "0",
    "migration_v530_lang_chosen": "0",
}


def _table_exists(table: str) -> bool:
    try:
        r = get_conn().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        return bool(r)
    except Exception:
        return False


def ensure_columns(table: str, columns: dict):
    try:
        if not _table_exists(table):
            return
        cur = get_conn().execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cur.fetchall()}
        for col_name, col_def in columns.items():
            if col_name not in existing:
                with contextlib.suppress(Exception):
                    get_conn().execute(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    except Exception as e:
        logging.warning(f"ensure_columns({table}) failed: {e}")


def run_migrations():
    c = get_conn()
    for sql in MIGRATIONS:
        c.executescript(sql)

    with contextlib.suppress(Exception):
        cols = {r["name"] for r in c.execute(
            "PRAGMA table_info(rate_limits)").fetchall()}
        if "mode" not in cols:
            c.execute("ALTER TABLE rate_limits RENAME TO rate_limits_old")
            c.execute("""CREATE TABLE rate_limits (
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL DEFAULT 'video',
                hour_start REAL NOT NULL, hour_count INTEGER NOT NULL DEFAULT 0,
                day_start REAL NOT NULL, day_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, mode))""")
            c.execute("""INSERT INTO rate_limits
                (user_id, mode, hour_start, hour_count, day_start, day_count)
                SELECT user_id, 'video', hour_start, hour_count,
                       day_start, day_count FROM rate_limits_old""")
            c.execute("DROP TABLE rate_limits_old")

    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                  (k, v))
    db_set("bot_version", FILE_VERSION)

    with contextlib.suppress(Exception):
        if db_get("migration_v530_quality", "0") != "1":
            cur_val = db_get("allowed_quality", "")
            if cur_val:
                parts = {x.strip() for x in cur_val.split(",") if x.strip()}
                for q in ("audio_best", "audio", "audio_320", "audio_128"):
                    parts.add(q)
                db_set("allowed_quality", ",".join(sorted(parts)))
            db_set("migration_v530_quality", "1")

    with contextlib.suppress(Exception):
        if db_get("migration_v530_lang_chosen", "0") != "1":
            c.execute("UPDATE users SET lang_chosen=1")
            db_set("migration_v530_lang_chosen", "1")

    with contextlib.suppress(Exception):
        c.execute("DELETE FROM menu_buttons WHERE btn_key='menu_lang'")

    ensure_columns("users", {
        "chat_id": "INTEGER NOT NULL DEFAULT 0",
        "username": "TEXT", "first_name": "TEXT",
        "downloads": "INTEGER NOT NULL DEFAULT 0",
        "success_dl": "INTEGER NOT NULL DEFAULT 0",
        "failed_dl": "INTEGER NOT NULL DEFAULT 0",
        "is_blocked": "INTEGER NOT NULL DEFAULT 0",
        "is_vip": "INTEGER NOT NULL DEFAULT 0",
        "lang": "TEXT NOT NULL DEFAULT 'fa'",
        "lang_chosen": "INTEGER NOT NULL DEFAULT 0",
        "created_at": "REAL NOT NULL DEFAULT 0",
        "updated_at": "REAL NOT NULL DEFAULT 0",
    })
    ensure_columns("jobs", {
        "user_id": "INTEGER NOT NULL DEFAULT 0",
        "chat_id": "INTEGER NOT NULL DEFAULT 0",
        "url": "TEXT NOT NULL DEFAULT ''",
        "title": "TEXT", "quality": "TEXT NOT NULL DEFAULT 'best'",
        "duration": "INTEGER NOT NULL DEFAULT 0",
        "filesize": "INTEGER NOT NULL DEFAULT 0",
        "status": "TEXT NOT NULL DEFAULT 'queued'",
        "progress": "REAL NOT NULL DEFAULT 0",
        "speed": "TEXT", "eta": "TEXT",
        "file_path": "TEXT", "thumbnail": "TEXT",
        "msg_id": "INTEGER", "notice_msg_id": "INTEGER",
        "delete_at": "REAL", "error": "TEXT",
        "created_at": "REAL NOT NULL DEFAULT 0",
        "started_at": "REAL", "finished_at": "REAL",
    })


def db_get(key: str, default: str = "") -> str:
    r = get_conn().execute(
        "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(r["value"]) if r else default


def db_set(key: str, value):
    get_conn().execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))


def db_log(admin_id: int, action: str, details: str = ""):
    with contextlib.suppress(Exception):
        get_conn().execute(
            "INSERT INTO logs(admin_id, action, details, created_at) "
            "VALUES (?, ?, ?, ?)", (admin_id, action, details, now_ts()))


def checkpoint_db():
    with contextlib.suppress(Exception):
        get_conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")


# ══════════════════════════════════════════════════════════════
# QUALITY
# ══════════════════════════════════════════════════════════════
VIDEO_QUALITIES = ("best", "4320p", "2160p", "1440p",
                   "1080p", "720p", "480p", "360p")
MUSIC_QUALITIES = ("audio_best", "audio", "audio_320", "audio_128")
ALL_QUALITIES   = VIDEO_QUALITIES + MUSIC_QUALITIES
QUALITY_ORDER   = ALL_QUALITIES


def is_audio_quality(q) -> bool:
    return isinstance(q, str) and q in MUSIC_QUALITIES


QUALITY_HEIGHTS = {
    "4320p": 4320, "2160p": 2160, "1440p": 1440,
    "1080p": 1080, "720p": 720, "480p": 480, "360p": 360,
}

QUALITY_LABELS = {
    "fa": {
        "best":       "🌟 بهترین کیفیت",
        "4320p":      "🔥 کیفیت 8K",
        "2160p":      "🎬 کیفیت 4K",
        "1440p":      "🎬 کیفیت 2K",
        "1080p":      "🎬 کیفیت 1080p",
        "720p":       "🎥 کیفیت 720p",
        "480p":       "📺 کیفیت 480p",
        "360p":       "📱 کیفیت 360p",
        "audio_best": "🌟 بهترین کیفیت صوتی",
        "audio":      "🎵 MP3 (192kbps)",
        "audio_320":  "🎵 MP3 320kbps",
        "audio_128":  "🎵 MP3 128kbps",
    },
    "en": {
        "best":       "🌟 Best Quality",
        "4320p":      "🔥 8K",
        "2160p":      "🎬 4K",
        "1440p":      "🎬 2K",
        "1080p":      "🎬 1080p",
        "720p":       "🎥 720p",
        "480p":       "📺 480p",
        "360p":       "📱 360p",
        "audio_best": "🌟 Best Audio Quality",
        "audio":      "🎵 MP3 (192kbps)",
        "audio_320":  "🎵 MP3 320kbps",
        "audio_128":  "🎵 MP3 128kbps",
    },
}


def allowed_qualities() -> set:
    raw = db_get("allowed_quality", ",".join(ALL_QUALITIES))
    return {x.strip() for x in raw.split(",") if x.strip()}


# ══════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════
@dataclass
class User:
    user_id: int
    chat_id: int
    username: Optional[str]
    first_name: Optional[str]
    downloads: int
    success_dl: int
    failed_dl: int
    is_blocked: bool
    is_vip: bool
    lang: str

    @classmethod
    def from_row(cls, r) -> "User":
        keys = set(r.keys())
        def g(k, d=None):
            return r[k] if k in keys else d
        return cls(
            user_id=int(g("user_id", 0) or 0),
            chat_id=int(g("chat_id", 0) or 0),
            username=g("username"), first_name=g("first_name"),
            downloads=int(g("downloads", 0) or 0),
            success_dl=int(g("success_dl", 0) or 0),
            failed_dl=int(g("failed_dl", 0) or 0),
            is_blocked=bool(g("is_blocked", 0)),
            is_vip=bool(g("is_vip", 0)),
            lang=str(g("lang", "fa") or "fa"),
        )


@dataclass
class Job:
    job_id: str
    user_id: int
    chat_id: int
    url: str
    title: Optional[str]
    quality: str
    duration: int
    filesize: int
    status: str
    progress: float
    file_path: Optional[str]
    thumbnail: Optional[str]
    msg_id: Optional[int]
    notice_msg_id: Optional[int]
    delete_at: Optional[float]
    created_at: Optional[float] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @classmethod
    def from_row(cls, r) -> "Job":
        keys = set(r.keys())
        def g(k, d=None):
            return r[k] if k in keys else d
        return cls(
            job_id=str(g("job_id", "") or ""),
            user_id=int(g("user_id", 0) or 0),
            chat_id=int(g("chat_id", 0) or 0),
            url=str(g("url", "") or ""),
            title=g("title"),
            quality=str(g("quality", "best") or "best"),
            duration=int(g("duration", 0) or 0),
            filesize=int(g("filesize", 0) or 0),
            status=str(g("status", "queued") or "queued"),
            progress=float(g("progress", 0) or 0),
            file_path=g("file_path"), thumbnail=g("thumbnail"),
            msg_id=g("msg_id"), notice_msg_id=g("notice_msg_id"),
            delete_at=g("delete_at"),
            created_at=g("created_at"),
            started_at=g("started_at"), finished_at=g("finished_at"),
        )


STATUS_QUEUED = "queued"
STATUS_ANALYZING = "analyzing"
STATUS_DOWNLOADING = "downloading"
STATUS_UPLOADING = "uploading"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_PENDING = "pending"
ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_ANALYZING,
                   STATUS_DOWNLOADING, STATUS_UPLOADING)


# ══════════════════════════════════════════════════════════════
# REPOSITORIES
# ══════════════════════════════════════════════════════════════
class UserRepo:
    @staticmethod
    def upsert(user_id, chat_id, username, first_name):
        t = now_ts()
        get_conn().execute(
            """INSERT INTO users(user_id, chat_id, username, first_name,
                                 created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 chat_id=excluded.chat_id,
                 username=excluded.username,
                 first_name=excluded.first_name,
                 updated_at=excluded.updated_at""",
            (user_id, chat_id, username, first_name, t, t))

    @staticmethod
    def get(uid) -> Optional[User]:
        r = get_conn().execute(
            "SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        return User.from_row(r) if r else None

    @staticmethod
    def set_blocked(uid, value):
        get_conn().execute(
            "UPDATE users SET is_blocked=?, updated_at=? WHERE user_id=?",
            (int(value), now_ts(), uid))

    @staticmethod
    def set_vip(uid, value):
        get_conn().execute(
            "UPDATE users SET is_vip=?, updated_at=? WHERE user_id=?",
            (int(value), now_ts(), uid))

    @staticmethod
    def set_lang(uid, lang):
        get_conn().execute(
            "UPDATE users SET lang=?, lang_chosen=1, updated_at=? "
            "WHERE user_id=?", (lang, now_ts(), uid))

    @staticmethod
    def bump(uid, col, d=1):
        if col not in {"downloads", "success_dl", "failed_dl"}:
            return
        get_conn().execute(
            f"UPDATE users SET {col}={col}+?, updated_at=? WHERE user_id=?",
            (d, now_ts(), uid))

    @staticmethod
    def active_jobs(uid) -> int:
        ph = ",".join("?" for _ in ACTIVE_STATUSES)
        r = get_conn().execute(
            f"SELECT COUNT(*) AS c FROM jobs WHERE user_id=? AND status IN ({ph})",
            (uid, *ACTIVE_STATUSES)).fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def list_recent(limit=20, offset=0):
        rows = get_conn().execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)).fetchall()
        return [User.from_row(r) for r in rows]

    @staticmethod
    def list_vip(limit=20, offset=0):
        rows = get_conn().execute(
            "SELECT * FROM users WHERE is_vip=1 ORDER BY updated_at DESC "
            "LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [User.from_row(r) for r in rows]

    @staticmethod
    def count_all() -> int:
        r = get_conn().execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def count_vip() -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_vip=1").fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def stats() -> dict:
        r = get_conn().execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN is_blocked=1 THEN 1 ELSE 0 END) AS blocked,
                      SUM(CASE WHEN is_vip=1 THEN 1 ELSE 0 END) AS vip
               FROM users""").fetchone()
        return {"total": int(r["total"] or 0),
                "blocked": int(r["blocked"] or 0),
                "vip": int(r["vip"] or 0)}


class JobRepo:
    @staticmethod
    def create(user_id, chat_id, url, status=STATUS_QUEUED) -> Job:
        jid = new_id()
        get_conn().execute(
            """INSERT INTO jobs(job_id, user_id, chat_id, url, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (jid, user_id, chat_id, url, status, now_ts()))
        return JobRepo.get(jid)

    @staticmethod
    def get(jid) -> Optional[Job]:
        r = get_conn().execute(
            "SELECT * FROM jobs WHERE job_id=?", (jid,)).fetchone()
        return Job.from_row(r) if r else None

    ALLOWED_UPD = {
        "title", "quality", "duration", "filesize", "status", "progress",
        "speed", "eta", "file_path", "thumbnail", "msg_id", "notice_msg_id",
        "delete_at", "error", "started_at", "finished_at",
    }

    @staticmethod
    def update(jid, **fields):
        f = {k: v for k, v in fields.items() if k in JobRepo.ALLOWED_UPD}
        if not f:
            return
        sets = ", ".join(f"{k}=?" for k in f)
        get_conn().execute(
            f"UPDATE jobs SET {sets} WHERE job_id=?", (*f.values(), jid))

    @staticmethod
    def history(uid, limit=10, offset=0):
        rows = get_conn().execute(
            """SELECT * FROM jobs WHERE user_id=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (uid, limit, offset)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def count_for_user(uid) -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE user_id=?", (uid,)).fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def by_status(status, limit=10, offset=0):
        rows = get_conn().execute(
            "SELECT * FROM jobs WHERE status=? "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def count_by_status(status) -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status=?", (status,)).fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def active(limit=20, offset=0):
        ph = ",".join("?" for _ in ACTIVE_STATUSES)
        rows = get_conn().execute(
            f"SELECT * FROM jobs WHERE status IN ({ph}) "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*ACTIVE_STATUSES, limit, offset)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def count_active() -> int:
        ph = ",".join("?" for _ in ACTIVE_STATUSES)
        r = get_conn().execute(
            f"SELECT COUNT(*) AS c FROM jobs WHERE status IN ({ph})",
            ACTIVE_STATUSES).fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def list_paginated(status: str, limit=10, offset=0):
        if status == "active":
            return JobRepo.active(limit=limit, offset=offset)
        if status == "recent":
            rows = get_conn().execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
            return [Job.from_row(r) for r in rows]
        return JobRepo.by_status(status, limit=limit, offset=offset)

    @staticmethod
    def count_for_filter(status: str) -> int:
        if status == "active":
            return JobRepo.count_active()
        if status == "recent":
            r = get_conn().execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
            return int(r["c"] or 0)
        return JobRepo.count_by_status(status)

    @staticmethod
    def due_for_delete(now):
        rows = get_conn().execute(
            """SELECT * FROM jobs
               WHERE delete_at IS NOT NULL AND delete_at <= ?
                 AND notice_msg_id IS NULL
                 AND (file_path IS NOT NULL OR msg_id IS NOT NULL)""",
            (now,)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def stuck_queued(older_than):
        rows = get_conn().execute(
            "SELECT * FROM jobs WHERE status='queued' AND created_at < ?",
            (older_than,)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def totals() -> dict:
        r = get_conn().execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed
               FROM jobs""").fetchone()
        return {"total": int(r["total"] or 0),
                "completed": int(r["completed"] or 0),
                "failed": int(r["failed"] or 0)}


class FavRepo:
    @staticmethod
    def add(uid: int, jid: str):
        get_conn().execute(
            "INSERT OR IGNORE INTO favorites(user_id, job_id, created_at) "
            "VALUES (?, ?, ?)", (uid, jid, now_ts()))

    @staticmethod
    def remove(uid: int, jid: str):
        get_conn().execute(
            "DELETE FROM favorites WHERE user_id=? AND job_id=?", (uid, jid))

    @staticmethod
    def is_fav(uid: int, jid: str) -> bool:
        r = get_conn().execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND job_id=?",
            (uid, jid)).fetchone()
        return bool(r)

    @staticmethod
    def list(uid: int, limit: int = 10, offset: int = 0):
        rows = get_conn().execute(
            """SELECT j.* FROM favorites f
               JOIN jobs j ON j.job_id = f.job_id
               WHERE f.user_id=?
               ORDER BY f.created_at DESC LIMIT ? OFFSET ?""",
            (uid, limit, offset)).fetchall()
        return [Job.from_row(r) for r in rows]

    @staticmethod
    def count(uid: int) -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM favorites WHERE user_id=?",
            (uid,)).fetchone()
        return int(r["c"] or 0)


class RateRepo:
    _HOUR = 3600
    _DAY = 86400

    @staticmethod
    def check_and_consume(uid, mode, hour_limit, day_limit):
        if mode not in ("photo", "video", "music"):
            mode = "video"
        now = now_ts()
        with transaction() as c:
            row = c.execute(
                "SELECT * FROM rate_limits WHERE user_id=? AND mode=?",
                (uid, mode)).fetchone()
            if not row:
                c.execute(
                    """INSERT INTO rate_limits(user_id, mode, hour_start,
                       hour_count, day_start, day_count)
                       VALUES (?, ?, ?, 1, ?, 1)""", (uid, mode, now, now))
                return
            hs = float(row["hour_start"] or now)
            hc = int(row["hour_count"] or 0)
            ds = float(row["day_start"] or now)
            dc = int(row["day_count"] or 0)
            if now - hs >= RateRepo._HOUR:
                hs, hc = now, 0
            if now - ds >= RateRepo._DAY:
                ds, dc = now, 0
            if day_limit > 0 and dc >= day_limit:
                raise PermissionError("rate_day")
            if hour_limit > 0 and hc >= hour_limit:
                raise PermissionError("rate_hour")
            c.execute(
                """UPDATE rate_limits
                   SET hour_start=?, hour_count=?, day_start=?, day_count=?
                   WHERE user_id=? AND mode=?""",
                (hs, hc + 1, ds, dc + 1, uid, mode))


class TicketRepo:
    @staticmethod
    def create(uid, msg) -> int:
        cur = get_conn().execute(
            "INSERT INTO tickets(user_id, message, status, created_at) "
            "VALUES (?, ?, 'open', ?)", (uid, msg, now_ts()))
        return cur.lastrowid or 0

    @staticmethod
    def get(tid):
        return get_conn().execute(
            "SELECT * FROM tickets WHERE ticket_id=?", (tid,)).fetchone()

    @staticmethod
    def answer(tid, answer):
        get_conn().execute(
            "UPDATE tickets SET answer=?, status='answered', answered_at=? "
            "WHERE ticket_id=?", (answer, now_ts(), tid))

    @staticmethod
    def close(tid):
        get_conn().execute(
            "UPDATE tickets SET status='closed' WHERE ticket_id=?", (tid,))

    @staticmethod
    def by_status(status, limit=10, offset=0):
        if status == "all":
            return get_conn().execute(
                "SELECT * FROM tickets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
        return get_conn().execute(
            """SELECT * FROM tickets WHERE status=?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (status, limit, offset)).fetchall()

    @staticmethod
    def count_by_status(status) -> int:
        if status == "all":
            r = get_conn().execute("SELECT COUNT(*) AS c FROM tickets").fetchone()
        else:
            r = get_conn().execute(
                "SELECT COUNT(*) AS c FROM tickets WHERE status=?",
                (status,)).fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def by_user(uid: int, limit: int = 10):
        return get_conn().execute(
            "SELECT * FROM tickets WHERE user_id=? "
            "ORDER BY created_at DESC LIMIT ?", (uid, limit)).fetchall()

    @staticmethod
    def open_count() -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE status='open'").fetchone()
        return int(r["c"] or 0)


class MenuButtonRepo:
    USER_KEYS = [
        "menu_download", "menu_history", "menu_favs", "menu_stats",
        "menu_support", "menu_help", "menu_admin",
    ]
    ADMIN_KEYS = [
        "admin_stats", "admin_users", "admin_jobs", "admin_broadcast",
        "admin_tickets", "admin_settings", "admin_limits", "admin_channel",
        "admin_quality", "admin_style", "admin_announce", "admin_miniapp",
        "admin_tools", "admin_update", "admin_logs",
        "admin_buttons", "admin_texts", "admin_guide", "admin_admins",
    ]
    DEFAULTS_USER = {
        "menu_download": ("btn_download", "menu:download"),
        "menu_history": ("btn_history", "menu:history"),
        "menu_favs": ("btn_favs", "menu:favs"),
        "menu_stats": ("btn_stats", "menu:stats"),
        "menu_support": ("btn_support", "menu:support"),
        "menu_help": ("btn_help", "menu:help"),
        "menu_admin": ("btn_admin", "admin:home"),
    }
    DEFAULTS_ADMIN = {
        "admin_stats": ("ad_stats", "admin:stats"),
        "admin_users": ("ad_users", "admin:users"),
        "admin_jobs": ("ad_jobs", "admin:jobs"),
        "admin_broadcast": ("ad_broadcast", "admin:broadcast"),
        "admin_tickets": ("ad_tickets", "admin:tickets"),
        "admin_settings": ("ad_settings", "admin:settings"),
        "admin_limits": ("ad_limits", "admin:limits"),
        "admin_channel": ("ad_channel", "admin:channel"),
        "admin_quality": ("ad_quality", "admin:quality"),
        "admin_style": ("ad_style", "admin:style"),
        "admin_announce": ("ad_announce", "admin:announce"),
        "admin_miniapp": ("ad_miniapp", "admin:miniapp"),
        "admin_tools": ("ad_tools", "admin:tools"),
        "admin_update": ("ad_update", "admin:update"),
        "admin_logs": ("ad_logs", "admin:logs"),
        "admin_buttons": ("ad_buttons", "admin:buttons"),
        "admin_texts": ("ad_texts", "admin:texts"),
        "admin_guide": ("ad_guide", "admin:guide"),
        "admin_admins": ("ad_admins", "admin:admins"),
    }

    @staticmethod
    def seed_defaults():
        now = now_ts()
        for i, k in enumerate(MenuButtonRepo.USER_KEYS):
            get_conn().execute(
                """INSERT OR IGNORE INTO menu_buttons
                   (scope, btn_key, position, is_visible, color, created_at)
                   VALUES ('user', ?, ?, 1, 'default', ?)""", (k, i, now))
        for i, k in enumerate(MenuButtonRepo.ADMIN_KEYS):
            get_conn().execute(
                """INSERT OR IGNORE INTO menu_buttons
                   (scope, btn_key, position, is_visible, color, created_at)
                   VALUES ('admin', ?, ?, 1, 'default', ?)""", (k, i, now))

    @staticmethod
    def get(scope, key):
        return get_conn().execute(
            "SELECT * FROM menu_buttons WHERE scope=? AND btn_key=?",
            (scope, key)).fetchone()

    @staticmethod
    def by_scope(scope, visible_only=True):
        q = "SELECT * FROM menu_buttons WHERE scope=?"
        if visible_only:
            q += " AND is_visible=1"
        q += " ORDER BY position, id"
        return get_conn().execute(q, (scope,)).fetchall()

    @staticmethod
    def update(scope, key, **fields):
        allowed = {"label", "color", "is_visible",
                   "emoji_id", "emoji_fb", "position"}
        f = {k: v for k, v in fields.items() if k in allowed}
        if not f:
            return
        sets = ", ".join(f"{k}=?" for k in f)
        get_conn().execute(
            f"UPDATE menu_buttons SET {sets} WHERE scope=? AND btn_key=?",
            (*f.values(), scope, key))

    @staticmethod
    def toggle_visible(scope, key):
        cur = MenuButtonRepo.get(scope, key)
        if not cur:
            return
        MenuButtonRepo.update(
            scope, key, is_visible=0 if cur["is_visible"] else 1)

    @staticmethod
    def reset(scope, key):
        get_conn().execute(
            """UPDATE menu_buttons SET label=NULL, color='default',
               emoji_id=NULL, emoji_fb=NULL, is_visible=1
               WHERE scope=? AND btn_key=?""", (scope, key))

    @staticmethod
    def set_color(scope, key, color):
        if color not in ("default", "success", "danger", "primary"):
            return
        MenuButtonRepo.update(scope, key, color=color)

    @staticmethod
    def count_all() -> int:
        r = get_conn().execute(
            "SELECT COUNT(*) AS c FROM menu_buttons").fetchone()
        return int(r["c"] or 0)

    @staticmethod
    def move(scope, key, direction):
        rows = list(MenuButtonRepo.by_scope(scope, visible_only=False))
        idx = next((i for i, r in enumerate(rows) if r["btn_key"] == key), -1)
        if idx < 0:
            return False
        try:
            cols = int(db_get(f"menu_cols_{scope}", "2"))
        except ValueError:
            cols = 2
        if direction == "left":
            new_idx = idx - 1
        elif direction == "right":
            new_idx = idx + 1
        elif direction == "up":
            new_idx = idx - cols
        elif direction == "down":
            new_idx = idx + cols
        elif direction == "top":
            new_idx = 0
        elif direction == "bottom":
            new_idx = len(rows) - 1
        else:
            return False
        if not (0 <= new_idx < len(rows)) or new_idx == idx:
            return False
        a, b = rows[idx], rows[new_idx]
        with transaction() as c:
            c.execute("UPDATE menu_buttons SET position=? WHERE id=?",
                      (b["position"], a["id"]))
            c.execute("UPDATE menu_buttons SET position=? WHERE id=?",
                      (a["position"], b["id"]))
        return True


def cleanup_menu_buttons():
    try:
        valid_user = set(MenuButtonRepo.USER_KEYS)
        valid_admin = set(MenuButtonRepo.ADMIN_KEYS)
        c = get_conn()
        rows = c.execute("SELECT scope, btn_key FROM menu_buttons").fetchall()
        for row in rows:
            s, k = row["scope"], row["btn_key"]
            if (s == "user" and k not in valid_user) or \
               (s == "admin" and k not in valid_admin):
                c.execute("DELETE FROM menu_buttons WHERE scope=? AND btn_key=?",
                          (s, k))
    except Exception as e:
        logging.warning(f"cleanup_menu_buttons failed: {e}")


# ══════════════════════════════════════════════════════════════
# I18N
# ══════════════════════════════════════════════════════════════
I18N = {
    "fa": {
        "welcome": "👋 <b>سلام {name}</b>\n\n🎬 به <b>دانلودر آرکا</b> خوش آمدی\n✨ سریع، هوشمند، قدرتمند\n\n📌 از منوی زیر استفاده کن:",
        "btn_download": "🚀 دانلود سریع",
        "btn_history": "📜 تاریخچه دانلودها",
        "btn_favs": "⭐ علاقه‌مندی‌ها",
        "btn_stats": "📊 حساب کاربری من",
        "btn_support": "🎧 پشتیبانی و ارتباط",
        "btn_help": "📚 راهنمای استفاده",
        "btn_admin": "🛠 پنل مدیریت",
        "back": "◀️ بازگشت",
        "cancel": "❌ انصراف",
        "yes": "✅ بله",
        "no": "❌ خیر",
        "saved": "✅ ذخیره شد",
        "deleted": "🗑 حذف شد",
        "toggle": "🔀 تغییر وضعیت",
        "delete": "🗑 حذف",
        "invalid": "⚠️ مقدار نامعتبر",
        "empty": "📭 خالی است",
        "unauthorized": "⛔ دسترسی ندارید",
        "blocked": "🚫 شما مسدود شده‌اید",
        "active": "🟢 فعال",
        "disabled": "🔴 غیرفعال",
        "refresh": "🔄 بروزرسانی",
        "confirm": "✅ تأیید",
        "reset": "♻️ بازنشانی",
        "lang_title": "🌐 <b>انتخاب زبان</b>\n\nزبان مورد نظر خود را انتخاب کنید:",
        "lang_same": "⚠️ همین زبان فعلی است",
        "please_join": "🔒 برای استفاده از ربات، ابتدا در کانال زیر عضو شوید:",
        "join_ok": "✅ عضویت شما تأیید شد",
        "join_first": "⚠️ ابتدا در کانال عضو شوید",
        "check_join": "✅ عضو شدم",
        "fallback_info": "ℹ️ لطفاً از منوی زیر استفاده کنید",
        "noop": "•",
        "received_data": "✅ دریافت شد",
        "button_inactive": "⚠️ این دکمه دیگر فعال نیست",

        "dl_choose_type": "🚀 <b>دانلود سریع</b>\n\n💫 چه چیزی می‌خواهی دانلود کنی؟\n\n🖼 عکس\n🎬 ویدئو\n🎵 آهنگ",
        "dl_btn_photo": "🖼 دانلود عکس",
        "dl_btn_video": "🎬 دانلود ویدئو",
        "dl_btn_music": "🎵 دانلود آهنگ",
        "dl_photo_center": "🖼 <b>دانلود عکس</b>\n\n🔗 لینک عکس را برایم بفرست:",
        "dl_video_center": "🎬 <b>دانلود ویدئو</b>\n\n🔗 لینک ویدئو را برایم بفرست:",
        "dl_music_center": "🎵 <b>دانلود آهنگ</b>\n\n🔗 لینک آهنگ را برایم بفرست:\n\n<i>🎧 پشتیبانی از YouTube، SoundCloud، Spotify و...</i>",
        "dl_photo_invalid": "⚠️ لینک عکس نامعتبر است",
        "dl_video_invalid": "⚠️ لینک ویدئو نامعتبر است",
        "dl_music_invalid": "⚠️ لینک آهنگ نامعتبر است",
        "dl_photo_downloading": "🖼 <b>در حال دانلود عکس...</b>\n\n🆔 <code>{id}</code>",
        "dl_photo_compressing": "🗜 <b>در حال فشرده‌سازی...</b>\n\n🆔 <code>{id}</code>",
        "dl_photo_completed": "✅ <b>عکس با موفقیت دانلود شد</b>\n\n💾 {size}\n🆔 <code>{id}</code>\n\n<i>⏰ حذف خودکار پس از {delay} ثانیه</i>",
        "dl_photo_failed": "❌ <b>خطا در دانلود عکس</b>\n\n{error}\n🆔 <code>{id}</code>",
        "dl_music_analyzing": "🔍 <b>در حال تحلیل آهنگ...</b>\n\n🎵 <code>{id}</code>",
        "dl_music_downloading": "⬇️ <b>در حال دانلود آهنگ...</b>\n\n🎵 <code>{id}</code>",
        "dl_music_completed": "✅ <b>{title}</b>\n\n🎤 هنرمند: {artist}\n💾 حجم: {size}\n⏱ مدت: {duration}\n🎵 <code>{id}</code>\n\n<i>⏰ حذف خودکار پس از {delay} ثانیه</i>",
        "dl_music_failed": "❌ <b>خطا در دانلود آهنگ</b>\n\n{error}\n🎵 <code>{id}</code>",
        "dl_back_to_types": "◀️ بازگشت",
        "dl_center": "📥 مرکز دانلود",
        "dl_invalid": "⚠️ لینک نامعتبر است",
        "dl_analyzing": "🔍 <b>در حال تحلیل لینک...</b>\n\nلطفاً چند لحظه صبر کنید ⏳",
        "dl_analyze_failed": "❌ خطا در تحلیل لینک!\nلطفاً لینک را بررسی کنید یا دوباره تلاش کنید.",
        "dl_select_quality": "🎞 <b>کیفیت مورد نظر خود را انتخاب کن:</b>",
        "qualities_available_hint": "\n\n💡 <i>کیفیت‌های موجود: تا {max}p</i>",
        "max_height_label": "🎞 حداکثر: <b>{max}p</b>",
        "error_prefix": "❌ خطا: ",
        "dl_queued": "✅ <b>در صف دانلود قرار گرفت</b>\n\n🎞 کیفیت: {quality}\n🆔 <code>{id}</code>",
        "dl_downloading": "⬇️ <b>{title}</b>\n\n📊 پیشرفت: <b>{pct:.1f}%</b>\n{bar}\n\n🚀 سرعت: {speed}\n⏱ زمان باقی‌مانده: {eta}\n\n🆔 <code>{id}</code>",
        "dl_completed": "✅ <b>{title}</b>\n\n🎞 کیفیت: {quality}\n💾 حجم: {size}\n⏱ مدت: {duration}\n🆔 <code>{id}</code>\n\n<i>⏰ حذف خودکار پس از {delay} ثانیه</i>",
        "dl_failed": "❌ دانلود ناموفق بود\n\n🆔 <code>{id}</code>",
        "dl_cancelled": "🚫 دانلود لغو شد",
        "dl_too_large": "⚠️ حجم فایل بیش از حد مجاز است",
        "dl_no_quality": "⚠️ هیچ کیفیتی در دسترس نیست",
        "dl_concurrent": "⏳ حد مجاز دانلود همزمان: {limit}\nلطفاً تا اتمام دانلودهای فعلی صبر کنید.",
        "dl_cooldown": "⏳ لطفاً {sec} ثانیه صبر کنید و دوباره لینک بفرستید.",
        "rate_hour": "🚦 سهمیه ساعتی شما تمام شده است. کمی صبر کنید.",
        "rate_day": "🚦 سهمیه روزانه شما تمام شده است. فردا دوباره امتحان کنید.",
        "file_removed": "🗑 فایل حذف شد",
        "btn_redo": "🔄 دانلود مجدد",
        "artist_unknown": "نامشخص",
        "subtitle_label": "📝 زیرنویس",

        "hist_title": "📜 <b>تاریخچه دانلودها</b>",
        "hist_empty": "📭 تاریخچه دانلود شما خالی است",
        "hist_page_title": "📜 <b>تاریخچه دانلودها</b>\n\n📄 صفحه {page}/{total}",
        "hist_item_detail": "📋 <b>جزئیات دانلود</b>\n\n📝 عنوان: {title}\n🆔 <code>{id}</code>\n🎞 کیفیت: {quality}\n📊 وضعیت: {status}\n💾 حجم: {size}\n⏱ مدت: {duration}\n🕐 تاریخ: {date}",
        "hist_delete_btn": "🗑 حذف از تاریخچه",
        "hist_delete_ok": "🗑 حذف شد",
        "hist_clear_btn": "🧹 پاک کردن همه",
        "hist_clear_confirm": "⚠️ <b>آیا مطمئنی؟</b>\n\nتمام تاریخچه دانلود شما پاک می‌شود.",
        "hist_cleared": "🧹 {count} مورد پاک شد",

        "fav_title": "⭐ <b>علاقه‌مندی‌ها</b>",
        "fav_empty": "📭 لیست علاقه‌مندی‌های شما خالی است",
        "fav_page_title": "⭐ <b>علاقه‌مندی‌ها</b> ({count})",
        "fav_empty_new": "📭 لیست علاقه‌مندی‌های شما خالی است",
        "fav_add_btn": "⭐ افزودن به علاقه‌مندی‌ها",
        "fav_remove_btn": "💔 حذف از علاقه‌مندی‌ها",
        "fav_add_ok": "⭐ به علاقه‌مندی‌ها اضافه شد",
        "fav_remove_ok": "💔 از علاقه‌مندی‌ها حذف شد",
        "fav_already": "⚠️ قبلاً در علاقه‌مندی‌ها است",
        "fav_not_in": "⚠️ در علاقه‌مندی‌ها نیست",
        "back_to_history": "◀️ بازگشت به تاریخچه",
        "back_to_favs": "◀️ بازگشت به علاقه‌مندی‌ها",
        "view_details": "👁 مشاهده جزئیات",
        "resend": "📤 ارسال مجدد",

        "stats_title": "📊 <b>حساب کاربری من</b>\n\n👤 نام: {name}\n🆔 شناسه: <code>{uid}</code>\n\n📥 کل دانلودها: <b>{total}</b>\n✅ موفق: <b>{success}</b>\n❌ ناموفق: <b>{failed}</b>\n⚡ فعال: <b>{active}</b>\n\n{tier}",
        "tier_vip": "💎 کاربر ویژه",
        "tier_normal": "👤 کاربر عادی",

        "support_title": "🎧 <b>پشتیبانی</b>\n\n✍️ پیام خود را بنویسید و ارسال کنید:",
        "support_sent": "✅ پیام شما ارسال شد\n\n🎫 شماره تیکت: <code>{id}</code>",
        "support_menu_title": "🎧 <b>پشتیبانی و ارتباط</b>\n\nیک گزینه را انتخاب کنید:",
        "support_new": "📝 ارسال پیام جدید",
        "support_my": "🎫 تیکت‌های من",
        "my_tickets_title": "🎫 <b>تیکت‌های من</b>",
        "my_tickets_empty": "📭 شما هیچ تیکتی ندارید",
        "ticket_status_open": "🟢 باز",
        "ticket_status_answered": "🟡 پاسخ داده شده",
        "ticket_status_closed": "🔴 بسته",
        "ticket_detail_user": "🎫 <b>تیکت #{id}</b>\n\n📊 وضعیت: {status}\n🕐 تاریخ: {date}\n\n💬 پیام شما:\n{msg}",
        "ticket_reply_label": "💬 پاسخ پشتیبانی:",
        "ticket_admin_notify": "🎫 <b>تیکت جدید #{id}</b>\n\n👤 {name}\n🆔 <code>{uid}</code>\n\n💬 {msg}",
        "ticket_view_btn": "👁 مشاهده",

        "help_text": "📚 <b>راهنمای استفاده</b>\n\n🎬 برای دانلود، از منوی «دانلود سریع» استفاده کن.\n📥 لینک ویدئو، عکس یا آهنگ را بفرست.\n🎞 کیفیت مورد نظر را انتخاب کن.\n⏱ پس از مدتی فایل به‌صورت خودکار حذف می‌شود.",

        "ad_title": "🛠 <b>پنل مدیریت</b>\n\nیک گزینه را انتخاب کنید:",
        "ad_stats": "📈 آمار",
        "ad_users": "👥 کاربران",
        "ad_jobs": "📦 دانلودها",
        "ad_broadcast": "📢 پیام همگانی",
        "ad_tickets": "🎫 تیکت‌ها",
        "ad_settings": "⚙️ تنظیمات",
        "ad_limits": "🚦 محدودیت‌ها",
        "ad_channel": "🔒 کانال اجباری",
        "ad_quality": "🎞 کیفیت‌ها",
        "ad_style": "🎨 استایل",
        "ad_tools": "🧰 ابزارها",
        "ad_update": "🔄 بروزرسانی",
        "ad_announce": "📣 اطلاع‌رسانی",
        "ad_miniapp": "🌐 مینی‌اپ",
        "ad_logs": "📜 گزارش‌ها",
        "ad_buttons": "🔘 دکمه‌ها",
        "ad_texts": "📝 متن‌ها",
        "ad_guide": "📖 راهنما",
        "ad_admins": "👑 ادمین‌ها",
        "ad_dl_types": "🎛 نوع دانلود",
        "ad_dlt_title": "🎛 <b>نوع دانلود</b>\n\n🖼 عکس: {photo}\n🎬 ویدئو: {video}\n🎵 آهنگ: {music}",
        "ad_dlt_music": "🎵 آهنگ",
        "ad_back": "◀️ بازگشت",
        "home_back": "🏠 منوی اصلی",
        "ad_rs_title": "📈 <b>آمار ربات</b>\n\n👥 کاربران: <b>{users}</b>\n💎 ویژه: <b>{vip}</b>\n🚫 مسدود: <b>{blocked}</b>\n\n📥 کل دانلودها: <b>{total}</b>\n✅ موفق: <b>{success}</b>\n❌ ناموفق: <b>{failed}</b>\n⚡ فعال: <b>{active}</b>\n\n🎫 تیکت‌های باز: <b>{tickets}</b>\n💾 حجم دیتابیس: <b>{db_size}</b>",

        "ad_u_title": "👥 <b>مدیریت کاربران</b>\n\nیک گزینه را انتخاب کنید:",
        "ad_u_search": "🔍 جستجو",
        "ad_u_recent": "📋 اخیر",
        "ad_u_vip": "💎 ویژه‌ها",
        "ad_u_search_ask": "🔍 آیدی، یوزرنیم یا نام کاربر را وارد کنید:",
        "ad_u_not_found": "❌ کاربری پیدا نشد",
        "ad_u_recent_title": "📋 <b>کاربران اخیر</b>",
        "ad_u_vip_title": "💎 <b>کاربران ویژه</b>",
        "ad_u_search_title": "🔍 <b>نتایج جستجو</b>",
        "ad_u_profile": "👤 <b>پروفایل کاربر</b>\n\n🆔 شناسه: <code>{uid}</code>\n📛 نام: {name}\n🔗 یوزرنیم: {username}\n\n📥 کل دانلودها: {total}\n✅ موفق: {success}\n❌ ناموفق: {failed}\n\nوضعیت: {status}\nنوع: {tier}",
        "ad_u_block": "🚫 مسدود",
        "ad_u_unblock": "✅ رفع مسدودی",
        "ad_u_vip_on": "💎 ویژه کن",
        "ad_u_vip_off": "💔 لغو ویژه",
        "ad_u_blocked": "🚫 کاربر مسدود شد",
        "ad_u_unblocked": "✅ کاربر آزاد شد",
        "ad_u_vip_on_ok": "💎 کاربر ویژه شد",
        "ad_u_vip_off_ok": "💔 از حالت ویژه خارج شد",
        "status_active": "🟢 فعال",
        "status_blocked": "🔴 مسدود",

        "ad_j_title": "📦 <b>مدیریت دانلودها</b>\n\nوضعیت: {status}  |  تعداد: {count}",
        "ad_j_active": "⚡ فعال",
        "ad_j_completed": "✅ موفق",
        "ad_j_failed": "❌ ناموفق",
        "ad_j_recent": "🕐 اخیر",
        "ad_j_detail": "📦 <b>جزئیات دانلود</b>\n\n🆔 <code>{id}</code>\n👤 کاربر: <code>{uid}</code>\n🎬 عنوان: {title}\n🎞 کیفیت: {quality}\n📊 وضعیت: {status}\n💾 حجم: {size}\n⏱ مدت: {duration}\n\n🔗 {url}",
        "ad_j_retry": "🔄 تلاش مجدد",
        "ad_j_cancel": "❌ لغو",
        "ad_j_empty": "📭 دانلودی یافت نشد",
        "ad_j_retried": "✅ در صف قرار گرفت",
        "ad_j_cancelled": "🚫 لغو شد",
        "ad_j_delete_file": "🗑 حذف فایل",
        "ad_j_file_deleted": "🗑 فایل حذف شد",

        "ad_bc_title": "📢 <b>پیام همگانی</b>\n\nپیام خود را ارسال کنید (متن، عکس، ویدئو، فایل):",
        "ad_bc_sending": "📤 <b>در حال ارسال به {count} کاربر...</b>",
        "ad_bc_done": "✅ <b>ارسال کامل شد</b>\n\n✔️ موفق: {sent}\n✖️ ناموفق: {failed}",
        "ad_bc_no_content": "⚠️ محتوایی دریافت نشد",
        "ad_bc_preview": "👁 <b>پیش‌نمایش</b>\n\n{preview}\n\n❓ ارسال شود؟",
        "bc_progress": "📤 <b>در حال ارسال...</b>",
        "wc_users": "👥 {total}",
        "wc_sent": "✅ {sent}",
        "wc_failed": "❌ {failed}",
        "wc_progress": "📊 {idx}/{total}",
        "wc_complete": "✅ <b>کامل شد</b>",

        "ad_tk_title": "🎫 <b>تیکت‌ها</b>\n\nوضعیت: {status}  |  تعداد: {count}",
        "ad_tk_open": "🟢 باز",
        "ad_tk_closed": "🔴 بسته",
        "ad_tk_all": "📋 همه",
        "ad_tk_detail": "🎫 <b>تیکت #{id}</b>\n\n👤 کاربر: <code>{uid}</code>\n📊 وضعیت: {status}\n🕐 تاریخ: {date}\n\n💬 پیام:\n{msg}",
        "ad_tk_reply": "💬 پاسخ",
        "ad_tk_close": "🔒 بستن",
        "ad_tk_ask_reply": "💬 پاسخ خود را بنویسید:",
        "ad_tk_reply_sent": "✅ پاسخ ارسال شد",
        "ad_tk_closed_ok": "🔒 تیکت بسته شد",
        "ad_tk_reply_prefix": "💬 <b>پاسخ تیکت #{id}</b>\n\n",

        "ad_set_title": "⚙️ <b>تنظیمات ربات</b>\n\n💾 حداکثر حجم: {maxsize}MB\n⏱ تاخیر حذف: {delay}s\n🔄 تلاش مجدد: {retry}\n🖼 تصویر پیش‌نمایش: {thumb}\n📝 زیرنویس: {subs}\n🔧 تعمیرات: {maint}\n🖼 عکس: {photo}\n🎬 ویدئو: {video}\n🗜 فشرده‌سازی: {compress}",
        "ad_set_maxsize": "💾 حداکثر حجم",
        "ad_set_delay": "⏱ تاخیر حذف",
        "ad_set_retry": "🔄 تعداد تلاش",
        "ad_set_thumb": "🖼 تصویر پیش‌نمایش",
        "ad_set_subs": "📝 دانلود زیرنویس",
        "ad_set_maint": "🔧 حالت تعمیرات",
        "ad_set_maint_text": "✏️ متن تعمیرات",
        "ad_set_dl_types": "🎛 نوع دانلود",
        "ad_set_compress": "🗜 فشرده‌سازی عکس",
        "ad_set_ask": "✏️ مقدار جدید برای {label} را وارد کنید:",
        "ad_set_ask_maint": "✏️ متن حالت تعمیرات را وارد کنید:",
        "smart_quality_lbl": "🎯 کیفیت هوشمند",

        "ad_lm_title": "🚦 <b>محدودیت‌ها</b>",
        "ad_lm_hour": "⏱ در ساعت",
        "ad_lm_day": "📅 در روز",
        "ad_lm_concurrent": "⚡ همزمان",
        "ad_lm_video_tab": "🎬 ویدئو",
        "ad_lm_photo_tab": "🖼 عکس",
        "ad_lm_music_tab": "🎵 آهنگ",
        "ad_lm_ask": "✏️ مقدار جدید برای {label} را وارد کنید:",
        "ad_lm_back_to_limits": "◀️ بازگشت به محدودیت‌ها",
        "ad_lm_advanced": "⚙️ پیشرفته",
        "cooldown_lbl": "⏸ زمان انتظار",
        "vip_unlimited_lbl": "💎 نامحدود ویژه",
        "owner_unlimited_lbl": "👑 نامحدود مالک",
        "cooldown_label": "⏸ زمان انتظار",
        "vip_unlimited": "💎 نامحدود ویژه",
        "owner_unlimited": "👑 نامحدود مالک",

        "ad_ch_title": "🔒 <b>کانال اجباری</b>\n\nوضعیت: {status}\n📢 کانال: <code>{channel}</code>",
        "ad_ch_toggle": "🔀 تغییر وضعیت",
        "ad_ch_set": "✏️ تنظیم کانال",
        "ad_ch_ask": "✏️ آیدی کانال را وارد کنید (مثال: @mychannel):",

        "ad_q_title": "🎞 <b>کیفیت‌های فعال</b>\n\n✅ فعال: {enabled}\n❌ غیرفعال: {disabled}",

        "ad_logs_title": "📜 <b>گزارش‌های اخیر</b>",
        "ad_logs_empty": "📭 گزارشی وجود ندارد",

        "ad_tools_title": "🧰 <b>ابزارها</b>\n\n💾 حجم دیتابیس: {db_size}\n📦 تعداد بکاپ‌ها: {backups}",
        "ad_tools_backup": "💾 بکاپ دیتابیس",
        "ad_tools_vacuum": "⚡ بهینه‌سازی",
        "ad_tools_clear_logs": "🗑 پاک کردن لاگ‌ها",
        "ad_tools_clear_dl": "🧹 پاک کردن دانلودها",
        "ad_tools_auto_backup": "⏰ بکاپ خودکار",
        "ad_tools_backup_ok": "✅ بکاپ ساخته شد: {name}",
        "ad_tools_vacuum_ok": "⚡ بهینه‌سازی انجام شد",
        "ad_tools_logs_ok": "🗑 {count} فایل لاگ پاک شد",
        "ad_tools_dl_ok": "🧹 {count} فایل پاک شد",
        "ad_auto_backup_title": "⏰ <b>بکاپ خودکار</b>\n\nوضعیت: {status}\n🕐 هر {hours} ساعت\n📅 آخرین بکاپ: {last}",
        "ad_auto_backup_toggle": "🔀 تغییر وضعیت",
        "ad_auto_backup_hours": "✏️ تغییر ساعت",
        "ad_auto_backup_ask": "✏️ فاصله زمانی (ساعت) را وارد کنید:",
        "ad_auto_backup_ok": "✅ ذخیره شد",

        "ad_up_title": "🔄 <b>بروزرسانی ربات</b>\n\n📌 نسخه فعلی: <code>{version}</code>\n📁 فایل اجرایی: <code>{run_file}</code>\n✏️ قابل نوشتن: {writable}",
        "ad_up_apply": "📤 اعمال بروزرسانی",
        "ad_up_fetch": "📥 دریافت سورس",
        "ad_up_history": "📜 تاریخچه",
        "ad_up_rollback": "↩️ بازگردانی",
        "ad_up_ask_zip": "📤 فایل ZIP یا PY جدید را ارسال کنید:",
        "ad_up_invalid_zip": "⚠️ فایل نامعتبر",
        "ad_up_applied": "✅ نسخه {version} اعمال شد",
        "ad_up_failed": "❌ خطا: {error}",
        "ad_up_history_title": "📜 <b>تاریخچه بروزرسانی</b>",
        "ad_up_history_empty": "📭 تاریخچه خالی است",
        "ad_up_no_backup": "❌ بکاپی یافت نشد",
        "ad_up_rollback_ok": "↩️ بازگردانی انجام شد",
        "ad_up_rollback_note": "⚠️ ربات ری‌استارت می‌شود",
        "ad_up_restart_note": "🔄 لطفاً ربات را دستی ری‌استارت کنید",
        "ad_up_restart_msg": "🔄 ربات در حال ری‌استارت...",
        "ad_up_no_botpy": "❌ فایل bot.py در ZIP یافت نشد",
        "ad_up_invalid_file": "⚠️ فایل نامعتبر (.zip یا .py)",
        "rollback_title": "↩️ بازگردانی",
        "rollback_confirm_text": "⚠️ بازگشت به نسخه قبلی و ری‌استارت؟",
        "rollback_restarting": "♻️ در حال ری‌استارت...",

        "ad_an_title": "📣 <b>اطلاع‌رسانی</b>",
        "ad_an_set_ch": "✏️ تنظیم کانال",
        "ad_an_send": "📤 ارسال",
        "ad_an_ask_ch": "✏️ آیدی کانال را وارد کنید:",
        "ad_an_ask_msg": "✍️ پیام خود را بنویسید:",
        "ad_an_sent": "✅ ارسال شد",
        "ad_an_no_ch": "⚠️ کانال تنظیم نشده",
        "an_main_title": "📣 <b>اطلاع‌رسانی حرفه‌ای</b>\n━━━━━━━━━━━━━━━━━━━━━\n👥 <b>کاربران:</b>\n  🔘 {status}\n  🎯 {audience} ({count})\n  ✅ {sent} | ❌ {failed}\n━━━━━━━━━━━━━━━━━━━━━\n📢 <b>کانال:</b>\n  <code>{channel}</code>\n  📊 {ch_total}\n━━━━━━━━━━━━━━━━━━━━━",
        "an_btn_users": "👥 کاربران",
        "an_btn_channel": "📢 کانال",
        "an_btn_stats": "📊 آمار",
        "an_btn_history": "📜 تاریخچه",
        "an_users_title": "👥 <b>ارسال به کاربران</b>\n━━━━━━━━━━━━━━━━━━━━━\n🔘 {status}  |  🎯 {audience} ({count})\n📌 {pin}  |  🔇 {silent}\n👁 {preview}  |  🗑 {autodel}\n━━━━━━━━━━━━━━━━━━━━━",
        "an_channel_title": "📢 <b>ارسال به کانال</b>\n━━━━━━━━━━━━━━━━━━━━━\n🔘 {status}\n📢 <code>{channel}</code>\n📌 {pin}  |  🔇 {silent}\n━━━━━━━━━━━━━━━━━━━━━\n📊 {total}  |  🕐 {last}",
        "an_btn_audience": "🎯 {label} ({count})",
        "an_btn_text": "📝 متنی",
        "an_btn_media": "🖼 رسانه",
        "an_btn_forward": "↗️ فوروارد",
        "an_btn_test": "🧪 تست",
        "an_btn_pin": "📌 پین: {v}",
        "an_btn_silent": "🔇 سایلنت: {v}",
        "an_btn_preview": "👁 پیش‌نمایش: {v}",
        "an_btn_autodel": "🗑 حذف خودکار: {v}",
        "an_btn_schedule": "⏰ زمان‌بندی",
        "an_btn_enable": "▶️ فعال‌سازی",
        "an_btn_reset": "🧹 صفر کردن",
        "an_btn_set": "📢 تنظیم",
        "an_set_ch_ask": "📢 <b>آیدی کانال:</b>\n\nمثال: <code>@mychannel</code>\nیا: <code>-1001234567890</code>\n\n⚠️ ربات باید ادمین باشد!",
        "an_bot_not_admin": "⚠️ ربات ادمین کانال نیست!",
        "an_text_ask": "📝 <b>متن را ارسال کنید:</b>",
        "an_media_ask": "🖼 <b>رسانه را ارسال کنید:</b>",
        "an_forward_ask": "↗️ <b>پیام مورد نظر را فوروارد کنید:</b>",
        "an_test_ask": "🧪 <b>متن تست:</b>",
        "an_ch_empty": "⚠️ کانال تنظیم نشده",
        "an_send_confirm": "❓ ارسال شود؟",
        "an_send_btn": "📤 ارسال",
        "an_cancel_btn": "❌ لغو",
        "an_sent_ok": "✅ ارسال شد",
        "an_sending": "📤 <b>در حال ارسال...</b>",
        "an_complete": "✅ <b>کامل شد</b>",
        "an_schedule_ask": "⏰ <b>فرمت YYYY-MM-DD HH:MM</b>",
        "an_adv_btn": "⚙️ پیشرفته",
        "an_stats_title": "📊 <b>آمار اطلاع‌رسانی</b>\n━━━━━━━━━━━━━━━━━━━━━\n👥 کاربران: ✅ {sent}  ❌ {failed}\n📢 کانال: 📤 {ch_sent}\n━━━━━━━━━━━━━━━━━━━━━\n👥 {total}  💎 {vip}\n⚡ {active}  😴 {inactive}",
        "an_preview_title": "👁 <b>پیش‌نمایش</b>\n📢 <code>{channel}</code>\n━━━━━━━━━━━━━━━━━━━━━",
        "an_audience_title": "🎯 <b>مخاطبین</b>\n\n👥 {total}  💎 {vip}\n⚡ {active}  😴 {inactive}",
        "an_preview_audience": "🎯 {label} ({count})",
        "an_audience_lbl_all": "👥 همه",
        "an_audience_lbl_vip": "💎 ویژه",
        "an_audience_lbl_active": "⚡ فعال",
        "an_audience_lbl_inactive": "😴 غیرفعال",
        "schedule_future_required": "⚠️ باید در آینده باشد",
        "schedule_format": "⚠️ فرمت: YYYY-MM-DD HH:MM",

        "ad_ma_title": "🌐 <b>مینی‌اپ</b>\n\nوضعیت: {status}\n🔗 آدرس: {url}",
        "ad_ma_set_url": "✏️ تنظیم آدرس",
        "ad_ma_toggle": "🔀 تغییر وضعیت",
        "ad_ma_ask_url": "✏️ آدرس مینی‌اپ را وارد کنید (با https:// شروع شود):",
        "ad_ma_invalid": "⚠️ آدرس نامعتبر",

        "style_title": "🎨 <b>استایل و ظاهر</b>\n\n💎 ایموجی پریمیوم: {premium}\n🗺 تعداد ایموجی‌ها: {map_count}\n🔘 تعداد دکمه‌ها: {total_btns}",
        "style_emoji_map": "🗺 نقشه ایموجی‌ها",
        "style_premium_toggle": "💎 ایموجی پریمیوم",
        "style_start_emoji": "✨ ایموجی شروع",
        "style_start_sticker": "🎯 استیکر شروع",
        "style_reset_all": "🔄 بازنشانی همه رنگ‌ها",
        "style_reset_ok": "🟢 بازنشانی شد",
        "btns_hub": "🔘 مرکز دکمه‌ها",
        "btns_title": "🔘 <b>مدیریت دکمه‌ها</b>\n\nتعداد کل: {total}",
        "btns_user_menu": "👤 منوی کاربر",
        "btns_admin_menu": "🛠 منوی ادمین",
        "btns_custom": "🔘 دکمه‌های سفارشی",
        "em_title": "💎 <b>نقشه ایموجی‌های پریمیوم</b>\n\n🗺 تعداد: {count}\n📊 وضعیت: {status}",
        "em_add": "➕ افزودن",
        "em_list": "📋 لیست",
        "em_clear": "🧹 پاک کردن همه",
        "em_step1": "💎 <b>ایموجی پریمیوم را ارسال کنید</b>\n\nبرای افزودن نقشه، ابتدا ایموجی‌های پریمیوم را ارسال کنید:",
        "em_need_premium": "⚠️ ایموجی پریمیوم یافت نشد",
        "em_need_normal": "⚠️ ایموجی معمولی یافت نشد",
        "em_saved": "✅ ذخیره شد",
        "em_deleted": "🗑 حذف شد",
        "em_cleared": "🧹 {count} مورد حذف شد",
        "em_list_title": "📋 <b>لیست ایموجی‌ها</b>",
        "em_list_empty": "📭 لیست خالی است",
        "em_confirm_clear": "⚠️ آیا از حذف {count} مورد اطمینان دارید؟",
        "start_emoji_title": "✨ <b>ایموجی شروع</b>\n\nایموجی مورد نظر را ارسال کنید:",
        "start_emoji_saved_premium": "✅ ایموجی پریمیوم ذخیره شد",
        "start_emoji_saved_normal": "✅ ایموجی معمولی ذخیره شد",
        "start_emoji_ask": "⚠️ ایموجی معتبر ارسال کنید",
        "start_sticker_title": "🎯 <b>استیکر شروع</b>\n\nوضعیت: {status}",
        "start_sticker_saved": "✅ استیکر ذخیره شد",
        "start_sticker_removed": "🗑 استیکر حذف شد",
        "start_sticker_bad": "⚠️ لطفاً یک استیکر ارسال کنید",
        "start_sticker_not_set": "⚙️ استیکری تنظیم نشده",

        "mn_edit_title": "🎛 <b>ویرایش دکمه</b>",
        "mn_edit_label": "📝 تغییر عنوان",
        "mn_set_emoji": "💎 تنظیم ایموجی",
        "mn_remove_emoji": "🗑 حذف ایموجی",
        "mn_toggle_vis": "🔀 نمایش/مخفی",
        "mn_reset": "♻️ بازنشانی",
        "mn_move": "🔀 جابجایی",
        "mn_cols": "📊 تعداد ستون",
        "mn_set_label_ask": "📝 عنوان جدید را وارد کنید (برای پیش‌فرض «-»):",
        "mn_set_emoji_ask": "💎 ایموجی پریمیوم را ارسال کنید:",
        "mn_emoji_removed": "🗑 ایموجی حذف شد",
        "mn_emoji_saved": "✅ ایموجی ذخیره شد",
        "mn_label_saved": "✅ عنوان ذخیره شد",
        "mn_reset_ok": "♻️ بازنشانی شد",
        "mn_group_label": "گروه",
        "mn_title_label": "عنوان",
        "mn_color_label": "رنگ",
        "mn_status_label": "وضعیت",
        "mn_emoji_label": "ایموجی",
        "mn_vis_active": "✅ فعال",
        "mn_vis_hidden": "🚫 مخفی",
        "mn_color_default_lbl": "⚪ پیش‌فرض",
        "mn_color_success_lbl": "🟢 سبز",
        "mn_color_danger_lbl": "🔴 قرمز",
        "mn_color_primary_lbl": "🔵 آبی",
        "mn_show_all": "👁 نمایش همه",
        "mn_hide_all": "🚫 مخفی همه",
        "mn_reset_all": "🔄 بازنشانی همه",
        "mv_up": "⬆️ بالا",
        "mv_down": "⬇️ پایین",
        "mv_left": "⬅️ چپ",
        "mv_right": "➡️ راست",
        "mv_top": "🔝 اول",
        "mv_bottom": "🔚 آخر",
        "color_default": "⚪ پیش‌فرض",
        "color_success": "🟢 سبز",
        "color_danger": "🔴 قرمز",
        "color_primary": "🔵 آبی",
        "color_set": "✅ رنگ {color} اعمال شد",
        "menu_user": "👤 منوی کاربر",
        "menu_admin": "🛠 منوی ادمین",

        "cbtn_title": "🔘 <b>دکمه‌های سفارشی</b>",
        "cbtn_add": "➕ افزودن دکمه",
        "cbtn_ask_label": "✏️ عنوان دکمه را وارد کنید:",
        "cbtn_ask_cb": "🔗 مقدار callback_data را وارد کنید:",
        "cbtn_added": "✅ دکمه اضافه شد",
        "cbtn_empty": "📭 دکمه‌ای وجود ندارد",
        "callback_data_prompt": "🔗 مقدار callback_data:",
        "normal_emojis_prompt": "📝 ایموجی‌های معمولی:",

        "texts_title": "📝 <b>مدیریت متن‌ها</b>\n\nیک متن را برای ویرایش انتخاب کنید:",
        "texts_ask": "📝 متن جدید برای {key}:",
        "texts_current": "📝 <b>{key}</b>\n\nمتن فعلی:\n<code>{current}</code>\n\n✏️ متن جدید را وارد کنید:",
        "texts_reset_btn": "♻️ بازنشانی",
        "texts_reset_ok": "♻️ به حالت پیش‌فرض بازگشت",
        "texts_custom_status": "✏️ سفارشی",
        "texts_default_status": "⚙️ پیش‌فرض",
        "texts_ask_new": "✏️ متن جدید را بفرست:",
        "guide_title": "📖 <b>راهنما</b>",
        "guide_ask": "✍️ متن راهنما برای زبان {lang} را وارد کنید:",

        "admins_title": "👑 <b>مدیران</b>",
        "admins_ask": "👑 آیدی عددی کاربر را وارد کنید:",
        "admins_added": "✅ ادمین اضافه شد",
        "admins_exists": "⚠️ کاربر قبلاً ادمین است",
        "cols_set": "✅ تعداد ستون: {n}",
        "ad_admins_title": "👑 <b>مدیران</b> ({count})",
        "ad_admins_empty": "📭 ادمینی وجود ندارد",
        "ad_admins_add": "➕ افزودن ادمین",
        "ad_admins_ask": "👑 آیدی عددی کاربر را وارد کنید:",
        "ad_admins_added": "✅ ادمین اضافه شد",
        "ad_admins_exists_owner": "⚠️ این کاربر مالک است",
        "ad_admins_exists_admin": "⚠️ این کاربر قبلاً ادمین است",
        "ad_admins_invalid": "⚠️ آیدی نامعتبر",
        "ad_admins_self": "⚠️ نمی‌توانید خودتان را اضافه کنید",
        "ad_admins_profile": "👑 <b>پروفایل ادمین</b>\n\n🆔 شناسه: <code>{uid}</code>\n📛 نام: {name}\n🔗 یوزرنیم: {username}\n🕐 تاریخ افزودن: {date}\n📊 وضعیت: {status}",
        "ad_admins_remove_btn": "🗑 حذف از ادمین‌ها",
        "ad_admins_removed": "🗑 حذف شد",
        "ad_admins_not_found": "❌ ادمین یافت نشد",
        "ad_admins_search": "🔍 جستجو",
        "ad_admins_search_ask": "🔍 آیدی عددی ادمین را وارد کنید:",
        "ad_admins_back": "◀️ بازگشت",
        "nav_prev": "◀️",
        "nav_page": "📄 {page}",
        "nav_next": "▶️",
    },
    "en": {
        "welcome": "👋 <b>Hello {name}</b>\n\n🎬 Welcome to <b>Arka Downloader</b>\n✨ Fast, Smart, Powerful\n\n📌 Use the menu below:",
        "btn_download": "🚀 Quick Download",
        "btn_history": "📜 Download History",
        "btn_favs": "⭐ Favorites",
        "btn_stats": "📊 My Account",
        "btn_support": "🎧 Support & Contact",
        "btn_help": "📚 Help Guide",
        "btn_admin": "🛠 Admin Panel",
        "back": "◀️ Back",
        "cancel": "❌ Cancel",
        "yes": "✅ Yes",
        "no": "❌ No",
        "saved": "✅ Saved",
        "deleted": "🗑 Deleted",
        "toggle": "🔀 Toggle",
        "delete": "🗑 Delete",
        "invalid": "⚠️ Invalid value",
        "empty": "📭 Empty",
        "unauthorized": "⛔ Unauthorized",
        "blocked": "🚫 You are blocked",
        "active": "🟢 Active",
        "disabled": "🔴 Disabled",
        "refresh": "🔄 Refresh",
        "confirm": "✅ Confirm",
        "reset": "♻️ Reset",
        "lang_title": "🌐 <b>Select Language</b>\n\nChoose your preferred language:",
        "lang_same": "⚠️ Same language is already active",
        "please_join": "🔒 Please join our channel first:",
        "join_ok": "✅ Membership confirmed",
        "join_first": "⚠️ Please join the channel first",
        "check_join": "✅ I Joined",
        "fallback_info": "ℹ️ Please use the menu below",
        "noop": "•",
        "received_data": "✅ Received",
        "button_inactive": "⚠️ This button is no longer active",

        "dl_choose_type": "🚀 <b>Quick Download</b>\n\n💫 What would you like to download?\n\n🖼 Photo\n🎬 Video\n🎵 Music",
        "dl_btn_photo": "🖼 Download Photo",
        "dl_btn_video": "🎬 Download Video",
        "dl_btn_music": "🎵 Download Music",
        "dl_photo_center": "🖼 <b>Photo Download</b>\n\n🔗 Send me the image link:",
        "dl_video_center": "🎬 <b>Video Download</b>\n\n🔗 Send me the video link:",
        "dl_music_center": "🎵 <b>Music Download</b>\n\n🔗 Send me the music link:\n\n<i>🎧 Supports YouTube, SoundCloud, Spotify and more...</i>",
        "dl_photo_invalid": "⚠️ Invalid image link",
        "dl_video_invalid": "⚠️ Invalid video link",
        "dl_music_invalid": "⚠️ Invalid music link",
        "dl_photo_downloading": "🖼 <b>Downloading image...</b>\n\n🆔 <code>{id}</code>",
        "dl_photo_compressing": "🗜 <b>Compressing...</b>\n\n🆔 <code>{id}</code>",
        "dl_photo_completed": "✅ <b>Image downloaded successfully</b>\n\n💾 {size}\n🆔 <code>{id}</code>\n\n<i>⏰ Auto-delete after {delay}s</i>",
        "dl_photo_failed": "❌ <b>Image download failed</b>\n\n{error}\n🆔 <code>{id}</code>",
        "dl_music_analyzing": "🔍 <b>Analyzing music...</b>\n\n🎵 <code>{id}</code>",
        "dl_music_downloading": "⬇️ <b>Downloading music...</b>\n\n🎵 <code>{id}</code>",
        "dl_music_completed": "✅ <b>{title}</b>\n\n🎤 Artist: {artist}\n💾 Size: {size}\n⏱ Duration: {duration}\n🎵 <code>{id}</code>\n\n<i>⏰ Auto-delete after {delay}s</i>",
        "dl_music_failed": "❌ <b>Music download failed</b>\n\n{error}\n🎵 <code>{id}</code>",
        "dl_back_to_types": "◀️ Back",
        "dl_center": "📥 Download Center",
        "dl_invalid": "⚠️ Invalid link",
        "dl_analyzing": "🔍 <b>Analyzing link...</b>\n\nPlease wait a moment ⏳",
        "dl_analyze_failed": "❌ Failed to analyze link!\nPlease check the URL or try again.",
        "dl_select_quality": "🎞 <b>Select the desired quality:</b>",
        "qualities_available_hint": "\n\n💡 <i>Available qualities: up to {max}p</i>",
        "max_height_label": "🎞 Max: <b>{max}p</b>",
        "error_prefix": "❌ Error: ",
        "dl_queued": "✅ <b>Added to download queue</b>\n\n🎞 Quality: {quality}\n🆔 <code>{id}</code>",
        "dl_downloading": "⬇️ <b>{title}</b>\n\n📊 Progress: <b>{pct:.1f}%</b>\n{bar}\n\n🚀 Speed: {speed}\n⏱ ETA: {eta}\n\n🆔 <code>{id}</code>",
        "dl_completed": "✅ <b>{title}</b>\n\n🎞 Quality: {quality}\n💾 Size: {size}\n⏱ Duration: {duration}\n🆔 <code>{id}</code>\n\n<i>⏰ Auto-delete after {delay}s</i>",
        "dl_failed": "❌ Download failed\n\n🆔 <code>{id}</code>",
        "dl_cancelled": "🚫 Download cancelled",
        "dl_too_large": "⚠️ File size exceeds the limit",
        "dl_no_quality": "⚠️ No quality available",
        "dl_concurrent": "⏳ Max concurrent downloads: {limit}\nPlease wait until current downloads finish.",
        "dl_cooldown": "⏳ Please wait {sec}s before sending another link.",
        "rate_hour": "🚦 Hourly quota reached. Please wait.",
        "rate_day": "🚦 Daily quota reached. Try again tomorrow.",
        "file_removed": "🗑 File removed",
        "btn_redo": "🔄 Re-download",
        "artist_unknown": "Unknown",
        "subtitle_label": "📝 Subtitle",

        "hist_title": "📜 <b>Download History</b>",
        "hist_empty": "📭 Your download history is empty",
        "hist_page_title": "📜 <b>Download History</b>\n\n📄 Page {page}/{total}",
        "hist_item_detail": "📋 <b>Job Details</b>\n\n📝 Title: {title}\n🆔 <code>{id}</code>\n🎞 Quality: {quality}\n📊 Status: {status}\n💾 Size: {size}\n⏱ Duration: {duration}\n🕐 Date: {date}",
        "hist_delete_btn": "🗑 Delete from History",
        "hist_delete_ok": "🗑 Deleted",
        "hist_clear_btn": "🧹 Clear All",
        "hist_clear_confirm": "⚠️ <b>Are you sure?</b>\n\nAll your download history will be deleted.",
        "hist_cleared": "🧹 {count} items removed",

        "fav_title": "⭐ <b>Favorites</b>",
        "fav_empty": "📭 Your favorites list is empty",
        "fav_page_title": "⭐ <b>Favorites</b> ({count})",
        "fav_empty_new": "📭 Your favorites list is empty",
        "fav_add_btn": "⭐ Add to Favorites",
        "fav_remove_btn": "💔 Remove from Favorites",
        "fav_add_ok": "⭐ Added to favorites",
        "fav_remove_ok": "💔 Removed from favorites",
        "fav_already": "⚠️ Already in favorites",
        "fav_not_in": "⚠️ Not in favorites",
        "back_to_history": "◀️ Back to History",
        "back_to_favs": "◀️ Back to Favorites",
        "view_details": "👁 View Details",
        "resend": "📤 Resend",

        "stats_title": "📊 <b>My Account</b>\n\n👤 Name: {name}\n🆔 ID: <code>{uid}</code>\n\n📥 Total: <b>{total}</b>\n✅ Success: <b>{success}</b>\n❌ Failed: <b>{failed}</b>\n⚡ Active: <b>{active}</b>\n\n{tier}",
        "tier_vip": "💎 VIP User",
        "tier_normal": "👤 Regular User",

        "support_title": "🎧 <b>Support</b>\n\n✍️ Write and send your message:",
        "support_sent": "✅ Your message has been sent\n\n🎫 Ticket ID: <code>{id}</code>",
        "support_menu_title": "🎧 <b>Support & Contact</b>\n\nChoose an option:",
        "support_new": "📝 Send New Message",
        "support_my": "🎫 My Tickets",
        "my_tickets_title": "🎫 <b>My Tickets</b>",
        "my_tickets_empty": "📭 You have no tickets",
        "ticket_status_open": "🟢 Open",
        "ticket_status_answered": "🟡 Answered",
        "ticket_status_closed": "🔴 Closed",
        "ticket_detail_user": "🎫 <b>Ticket #{id}</b>\n\n📊 Status: {status}\n🕐 Date: {date}\n\n💬 Your message:\n{msg}",
        "ticket_reply_label": "💬 Support reply:",
        "ticket_admin_notify": "🎫 <b>New Ticket #{id}</b>\n\n👤 {name}\n🆔 <code>{uid}</code>\n\n💬 {msg}",
        "ticket_view_btn": "👁 View",

        "help_text": "📚 <b>Help Guide</b>\n\n🎬 To download, use the «Quick Download» menu.\n📥 Send a video, image or music link.\n🎞 Choose the desired quality.\n⏱ The file will be auto-deleted after a while.",

        "ad_title": "🛠 <b>Admin Panel</b>\n\nChoose an option:",
        "ad_stats": "📈 Statistics",
        "ad_users": "👥 Users",
        "ad_jobs": "📦 Downloads",
        "ad_broadcast": "📢 Broadcast",
        "ad_tickets": "🎫 Tickets",
        "ad_settings": "⚙️ Settings",
        "ad_limits": "🚦 Limits",
        "ad_channel": "🔒 Force Join",
        "ad_quality": "🎞 Qualities",
        "ad_style": "🎨 Style",
        "ad_tools": "🧰 Tools",
        "ad_update": "🔄 Update",
        "ad_announce": "📣 Announce",
        "ad_miniapp": "🌐 Mini App",
        "ad_logs": "📜 Logs",
        "ad_buttons": "🔘 Buttons",
        "ad_texts": "📝 Texts",
        "ad_guide": "📖 Guide",
        "ad_admins": "👑 Admins",
        "ad_dl_types": "🎛 Download Types",
        "ad_dlt_title": "🎛 <b>Download Types</b>\n\n🖼 Photo: {photo}\n🎬 Video: {video}\n🎵 Music: {music}",
        "ad_dlt_music": "🎵 Music",
        "ad_back": "◀️ Back",
        "home_back": "🏠 Main Menu",
        "ad_rs_title": "📈 <b>Bot Statistics</b>\n\n👥 Users: <b>{users}</b>\n💎 VIP: <b>{vip}</b>\n🚫 Blocked: <b>{blocked}</b>\n\n📥 Total Jobs: <b>{total}</b>\n✅ Success: <b>{success}</b>\n❌ Failed: <b>{failed}</b>\n⚡ Active: <b>{active}</b>\n\n🎫 Open Tickets: <b>{tickets}</b>\n💾 DB Size: <b>{db_size}</b>",

        "ad_u_title": "👥 <b>User Management</b>\n\nChoose an option:",
        "ad_u_search": "🔍 Search",
        "ad_u_recent": "📋 Recent",
        "ad_u_vip": "💎 VIP",
        "ad_u_search_ask": "🔍 Enter user ID, username or name:",
        "ad_u_not_found": "❌ User not found",
        "ad_u_recent_title": "📋 <b>Recent Users</b>",
        "ad_u_vip_title": "💎 <b>VIP Users</b>",
        "ad_u_search_title": "🔍 <b>Search Results</b>",
        "ad_u_profile": "👤 <b>User Profile</b>\n\n🆔 ID: <code>{uid}</code>\n📛 Name: {name}\n🔗 Username: {username}\n\n📥 Total: {total}\n✅ Success: {success}\n❌ Failed: {failed}\n\nStatus: {status}\nType: {tier}",
        "ad_u_block": "🚫 Block",
        "ad_u_unblock": "✅ Unblock",
        "ad_u_vip_on": "💎 Make VIP",
        "ad_u_vip_off": "💔 Remove VIP",
        "ad_u_blocked": "🚫 User blocked",
        "ad_u_unblocked": "✅ User unblocked",
        "ad_u_vip_on_ok": "💎 User is now VIP",
        "ad_u_vip_off_ok": "💔 VIP removed",
        "status_active": "🟢 Active",
        "status_blocked": "🔴 Blocked",

        "ad_j_title": "📦 <b>Download Management</b>\n\nStatus: {status}  |  Count: {count}",
        "ad_j_active": "⚡ Active",
        "ad_j_completed": "✅ Completed",
        "ad_j_failed": "❌ Failed",
        "ad_j_recent": "🕐 Recent",
        "ad_j_detail": "📦 <b>Job Details</b>\n\n🆔 <code>{id}</code>\n👤 User: <code>{uid}</code>\n🎬 Title: {title}\n🎞 Quality: {quality}\n📊 Status: {status}\n💾 Size: {size}\n⏱ Duration: {duration}\n\n🔗 {url}",
        "ad_j_retry": "🔄 Retry",
        "ad_j_cancel": "❌ Cancel",
        "ad_j_empty": "📭 No jobs found",
        "ad_j_retried": "✅ Queued",
        "ad_j_cancelled": "🚫 Cancelled",
        "ad_j_delete_file": "🗑 Delete File",
        "ad_j_file_deleted": "🗑 File deleted",

        "ad_bc_title": "📢 <b>Broadcast</b>\n\nSend your message (text, photo, video, file):",
        "ad_bc_sending": "📤 <b>Sending to {count} users...</b>",
        "ad_bc_done": "✅ <b>Broadcast complete</b>\n\n✔️ Sent: {sent}\n✖️ Failed: {failed}",
        "ad_bc_no_content": "⚠️ No content received",
        "ad_bc_preview": "👁 <b>Preview</b>\n\n{preview}\n\n❓ Send it?",
        "bc_progress": "📤 <b>Sending...</b>",
        "wc_users": "👥 {total}",
        "wc_sent": "✅ {sent}",
        "wc_failed": "❌ {failed}",
        "wc_progress": "📊 {idx}/{total}",
        "wc_complete": "✅ <b>Complete</b>",

        "ad_tk_title": "🎫 <b>Tickets</b>\n\nStatus: {status}  |  Count: {count}",
        "ad_tk_open": "🟢 Open",
        "ad_tk_closed": "🔴 Closed",
        "ad_tk_all": "📋 All",
        "ad_tk_detail": "🎫 <b>Ticket #{id}</b>\n\n👤 User: <code>{uid}</code>\n📊 Status: {status}\n🕐 Date: {date}\n\n💬 Message:\n{msg}",
        "ad_tk_reply": "💬 Reply",
        "ad_tk_close": "🔒 Close",
        "ad_tk_ask_reply": "💬 Write your reply:",
        "ad_tk_reply_sent": "✅ Reply sent",
        "ad_tk_closed_ok": "🔒 Ticket closed",
        "ad_tk_reply_prefix": "💬 <b>Reply to ticket #{id}</b>\n\n",

        "ad_set_title": "⚙️ <b>Bot Settings</b>\n\n💾 Max Size: {maxsize}MB\n⏱ Delete Delay: {delay}s\n🔄 Retries: {retry}\n🖼 Thumbnail: {thumb}\n📝 Subtitles: {subs}\n🔧 Maintenance: {maint}\n🖼 Photo: {photo}\n🎬 Video: {video}\n🗜 Compression: {compress}",
        "ad_set_maxsize": "💾 Max Size",
        "ad_set_delay": "⏱ Delete Delay",
        "ad_set_retry": "🔄 Retries",
        "ad_set_thumb": "🖼 Thumbnail",
        "ad_set_subs": "📝 Subtitles",
        "ad_set_maint": "🔧 Maintenance",
        "ad_set_maint_text": "✏️ Maintenance Text",
        "ad_set_dl_types": "🎛 Download Types",
        "ad_set_compress": "🗜 Image Compression",
        "ad_set_ask": "✏️ Enter new value for {label}:",
        "ad_set_ask_maint": "✏️ Enter maintenance mode text:",
        "smart_quality_lbl": "🎯 Smart Quality",

        "ad_lm_title": "🚦 <b>Limits</b>",
        "ad_lm_hour": "⏱ Per Hour",
        "ad_lm_day": "📅 Per Day",
        "ad_lm_concurrent": "⚡ Concurrent",
        "ad_lm_video_tab": "🎬 Video",
        "ad_lm_photo_tab": "🖼 Photo",
        "ad_lm_music_tab": "🎵 Music",
        "ad_lm_ask": "✏️ Enter new value for {label}:",
        "ad_lm_back_to_limits": "◀️ Back to Limits",
        "ad_lm_advanced": "⚙️ Advanced",
        "cooldown_lbl": "⏸ Cooldown",
        "vip_unlimited_lbl": "💎 VIP Unlimited",
        "owner_unlimited_lbl": "👑 Owner Unlimited",
        "cooldown_label": "⏸ Cooldown",
        "vip_unlimited": "💎 VIP Unlimited",
        "owner_unlimited": "👑 Owner Unlimited",

        "ad_ch_title": "🔒 <b>Force Join Channel</b>\n\nStatus: {status}\n📢 Channel: <code>{channel}</code>",
        "ad_ch_toggle": "🔀 Toggle",
        "ad_ch_set": "✏️ Set Channel",
        "ad_ch_ask": "✏️ Enter channel ID (e.g. @mychannel):",

        "ad_q_title": "🎞 <b>Active Qualities</b>\n\n✅ Enabled: {enabled}\n❌ Disabled: {disabled}",

        "ad_logs_title": "📜 <b>Recent Logs</b>",
        "ad_logs_empty": "📭 No logs found",

        "ad_tools_title": "🧰 <b>Tools</b>\n\n💾 DB Size: {db_size}\n📦 Backups: {backups}",
        "ad_tools_backup": "💾 Database Backup",
        "ad_tools_vacuum": "⚡ Vacuum",
        "ad_tools_clear_logs": "🗑 Clear Logs",
        "ad_tools_clear_dl": "🧹 Clear Downloads",
        "ad_tools_auto_backup": "⏰ Auto Backup",
        "ad_tools_backup_ok": "✅ Backup created: {name}",
        "ad_tools_vacuum_ok": "⚡ Vacuum completed",
        "ad_tools_logs_ok": "🗑 {count} log files removed",
        "ad_tools_dl_ok": "🧹 {count} files removed",
        "ad_auto_backup_title": "⏰ <b>Auto Backup</b>\n\nStatus: {status}\n🕐 Every {hours} hours\n📅 Last backup: {last}",
        "ad_auto_backup_toggle": "🔀 Toggle",
        "ad_auto_backup_hours": "✏️ Change Interval",
        "ad_auto_backup_ask": "✏️ Enter interval (hours):",
        "ad_auto_backup_ok": "✅ Saved",

        "ad_up_title": "🔄 <b>Bot Update</b>\n\n📌 Current Version: <code>{version}</code>\n📁 Run File: <code>{run_file}</code>\n✏️ Writable: {writable}",
        "ad_up_apply": "📤 Apply Update",
        "ad_up_fetch": "📥 Fetch Source",
        "ad_up_history": "📜 History",
        "ad_up_rollback": "↩️ Rollback",
        "ad_up_ask_zip": "📤 Send the new ZIP or PY file:",
        "ad_up_invalid_zip": "⚠️ Invalid file",
        "ad_up_applied": "✅ Version {version} applied",
        "ad_up_failed": "❌ Error: {error}",
        "ad_up_history_title": "📜 <b>Update History</b>",
        "ad_up_history_empty": "📭 History is empty",
        "ad_up_no_backup": "❌ No backup found",
        "ad_up_rollback_ok": "↩️ Rollback complete",
        "ad_up_rollback_note": "⚠️ Bot will restart",
        "ad_up_restart_note": "🔄 Please restart the bot manually",
        "ad_up_restart_msg": "🔄 Bot is restarting...",
        "ad_up_no_botpy": "❌ bot.py not found in ZIP",
        "ad_up_invalid_file": "⚠️ Invalid file (.zip or .py)",
        "rollback_title": "↩️ Rollback",
        "rollback_confirm_text": "⚠️ Restore previous version and restart?",
        "rollback_restarting": "♻️ Restarting...",

        "ad_an_title": "📣 <b>Announcements</b>",
        "ad_an_set_ch": "✏️ Set Channel",
        "ad_an_send": "📤 Send",
        "ad_an_ask_ch": "✏️ Enter channel ID:",
        "ad_an_ask_msg": "✍️ Write your message:",
        "ad_an_sent": "✅ Sent",
        "ad_an_no_ch": "⚠️ Channel not set",
        "an_main_title": "📣 <b>Pro Announce</b>\n━━━━━━━━━━━━━━━━━━━━━\n👥 <b>Users:</b>\n  🔘 {status}\n  🎯 {audience} ({count})\n  ✅ {sent} | ❌ {failed}\n━━━━━━━━━━━━━━━━━━━━━\n📢 <b>Channel:</b>\n  <code>{channel}</code>\n  📊 {ch_total}\n━━━━━━━━━━━━━━━━━━━━━",
        "an_btn_users": "👥 Users",
        "an_btn_channel": "📢 Channel",
        "an_btn_stats": "📊 Stats",
        "an_btn_history": "📜 History",
        "an_users_title": "👥 <b>Send to Users</b>\n━━━━━━━━━━━━━━━━━━━━━\n🔘 {status}  |  🎯 {audience} ({count})\n📌 {pin}  |  🔇 {silent}\n👁 {preview}  |  🗑 {autodel}\n━━━━━━━━━━━━━━━━━━━━━",
        "an_channel_title": "📢 <b>Send to Channel</b>\n━━━━━━━━━━━━━━━━━━━━━\n🔘 {status}\n📢 <code>{channel}</code>\n📌 {pin}  |  🔇 {silent}\n━━━━━━━━━━━━━━━━━━━━━\n📊 {total}  |  🕐 {last}",
        "an_btn_audience": "🎯 {label} ({count})",
        "an_btn_text": "📝 Text",
        "an_btn_media": "🖼 Media",
        "an_btn_forward": "↗️ Forward",
        "an_btn_test": "🧪 Test",
        "an_btn_pin": "📌 Pin: {v}",
        "an_btn_silent": "🔇 Silent: {v}",
        "an_btn_preview": "👁 Preview: {v}",
        "an_btn_autodel": "🗑 AutoDel: {v}",
        "an_btn_schedule": "⏰ Schedule",
        "an_btn_enable": "▶️ Enable",
        "an_btn_reset": "🧹 Reset",
        "an_btn_set": "📢 Set",
        "an_set_ch_ask": "📢 <b>Channel ID:</b>\n\nExample: <code>@mychannel</code>\nOr: <code>-1001234567890</code>\n\n⚠️ Bot must be admin!",
        "an_bot_not_admin": "⚠️ Bot is not admin of the channel!",
        "an_text_ask": "📝 <b>Send text:</b>",
        "an_media_ask": "🖼 <b>Send media:</b>",
        "an_forward_ask": "↗️ <b>Forward the message:</b>",
        "an_test_ask": "🧪 <b>Test text:</b>",
        "an_ch_empty": "⚠️ Channel not set",
        "an_send_confirm": "❓ Send?",
        "an_send_btn": "📤 Send",
        "an_cancel_btn": "❌ Cancel",
        "an_sent_ok": "✅ Sent",
        "an_sending": "📤 <b>Sending...</b>",
        "an_complete": "✅ <b>Complete</b>",
        "an_schedule_ask": "⏰ <b>Format YYYY-MM-DD HH:MM</b>",
        "an_adv_btn": "⚙️ Advanced",
        "an_stats_title": "📊 <b>Announce Stats</b>\n━━━━━━━━━━━━━━━━━━━━━\n👥 Users: ✅ {sent}  ❌ {failed}\n📢 Channel: 📤 {ch_sent}\n━━━━━━━━━━━━━━━━━━━━━\n👥 {total}  💎 {vip}\n⚡ {active}  😴 {inactive}",
        "an_preview_title": "👁 <b>Preview</b>\n📢 <code>{channel}</code>\n━━━━━━━━━━━━━━━━━━━━━",
        "an_audience_title": "🎯 <b>Audience</b>\n\n👥 {total}  💎 {vip}\n⚡ {active}  😴 {inactive}",
        "an_preview_audience": "🎯 {label} ({count})",
        "an_audience_lbl_all": "👥 All",
        "an_audience_lbl_vip": "💎 VIP",
        "an_audience_lbl_active": "⚡ Active",
        "an_audience_lbl_inactive": "😴 Inactive",
        "schedule_future_required": "⚠️ Must be in the future",
        "schedule_format": "⚠️ Format: YYYY-MM-DD HH:MM",

        "ad_ma_title": "🌐 <b>Mini App</b>\n\nStatus: {status}\n🔗 URL: {url}",
        "ad_ma_set_url": "✏️ Set URL",
        "ad_ma_toggle": "🔀 Toggle",
        "ad_ma_ask_url": "✏️ Enter Mini App URL (must start with https://):",
        "ad_ma_invalid": "⚠️ Invalid URL",

        "style_title": "🎨 <b>Style & Appearance</b>\n\n💎 Premium Emoji: {premium}\n🗺 Emoji Map: {map_count}\n🔘 Total Buttons: {total_btns}",
        "style_emoji_map": "🗺 Emoji Map",
        "style_premium_toggle": "💎 Premium Emoji",
        "style_start_emoji": "✨ Start Emoji",
        "style_start_sticker": "🎯 Start Sticker",
        "style_reset_all": "🔄 Reset All Colors",
        "style_reset_ok": "🟢 Reset completed",
        "btns_hub": "🔘 Buttons Hub",
        "btns_title": "🔘 <b>Button Manager</b>\n\nTotal: {total}",
        "btns_user_menu": "👤 User Menu",
        "btns_admin_menu": "🛠 Admin Menu",
        "btns_custom": "🔘 Custom Buttons",
        "em_title": "💎 <b>Premium Emoji Map</b>\n\n🗺 Count: {count}\n📊 Status: {status}",
        "em_add": "➕ Add",
        "em_list": "📋 List",
        "em_clear": "🧹 Clear All",
        "em_step1": "💎 <b>Send premium emoji</b>\n\nTo add a mapping, first send the premium emojis:",
        "em_need_premium": "⚠️ No premium emoji found",
        "em_need_normal": "⚠️ No normal emoji found",
        "em_saved": "✅ Saved",
        "em_deleted": "🗑 Deleted",
        "em_cleared": "🧹 {count} items removed",
        "em_list_title": "📋 <b>Emoji List</b>",
        "em_list_empty": "📭 List is empty",
        "em_confirm_clear": "⚠️ Are you sure you want to delete {count} items?",
        "start_emoji_title": "✨ <b>Start Emoji</b>\n\nSend the desired emoji:",
        "start_emoji_saved_premium": "✅ Premium emoji saved",
        "start_emoji_saved_normal": "✅ Normal emoji saved",
        "start_emoji_ask": "⚠️ Send a valid emoji",
        "start_sticker_title": "🎯 <b>Start Sticker</b>\n\nStatus: {status}",
        "start_sticker_saved": "✅ Sticker saved",
        "start_sticker_removed": "🗑 Sticker removed",
        "start_sticker_bad": "⚠️ Please send a sticker",
        "start_sticker_not_set": "⚙️ No sticker set",

        "mn_edit_title": "🎛 <b>Edit Button</b>",
        "mn_edit_label": "📝 Change Label",
        "mn_set_emoji": "💎 Set Emoji",
        "mn_remove_emoji": "🗑 Remove Emoji",
        "mn_toggle_vis": "🔀 Show/Hide",
        "mn_reset": "♻️ Reset",
        "mn_move": "🔀 Move",
        "mn_cols": "📊 Columns",
        "mn_set_label_ask": "📝 Enter new label (use «-» for default):",
        "mn_set_emoji_ask": "💎 Send a premium emoji:",
        "mn_emoji_removed": "🗑 Emoji removed",
        "mn_emoji_saved": "✅ Emoji saved",
        "mn_label_saved": "✅ Label saved",
        "mn_reset_ok": "♻️ Reset completed",
        "mn_group_label": "Group",
        "mn_title_label": "Title",
        "mn_color_label": "Color",
        "mn_status_label": "Status",
        "mn_emoji_label": "Emoji",
        "mn_vis_active": "✅ Active",
        "mn_vis_hidden": "🚫 Hidden",
        "mn_color_default_lbl": "⚪ Default",
        "mn_color_success_lbl": "🟢 Green",
        "mn_color_danger_lbl": "🔴 Red",
        "mn_color_primary_lbl": "🔵 Blue",
        "mn_show_all": "👁 Show All",
        "mn_hide_all": "🚫 Hide All",
        "mn_reset_all": "🔄 Reset All",
        "mv_up": "⬆️ Up",
        "mv_down": "⬇️ Down",
        "mv_left": "⬅️ Left",
        "mv_right": "➡️ Right",
        "mv_top": "🔝 Top",
        "mv_bottom": "🔚 Bottom",
        "color_default": "⚪ Default",
        "color_success": "🟢 Green",
        "color_danger": "🔴 Red",
        "color_primary": "🔵 Blue",
        "color_set": "✅ Color {color} applied",
        "menu_user": "👤 User Menu",
        "menu_admin": "🛠 Admin Menu",

        "cbtn_title": "🔘 <b>Custom Buttons</b>",
        "cbtn_add": "➕ Add Button",
        "cbtn_ask_label": "✏️ Enter button label:",
        "cbtn_ask_cb": "🔗 Enter callback_data:",
        "cbtn_added": "✅ Button added",
        "cbtn_empty": "📭 No buttons found",
        "callback_data_prompt": "🔗 callback_data:",
        "normal_emojis_prompt": "📝 Normal emojis:",

        "texts_title": "📝 <b>Text Management</b>\n\nSelect a text to edit:",
        "texts_ask": "📝 New text for {key}:",
        "texts_current": "📝 <b>{key}</b>\n\nCurrent text:\n<code>{current}</code>\n\n✏️ Enter new text:",
        "texts_reset_btn": "♻️ Reset",
        "texts_reset_ok": "♻️ Reset to default",
        "texts_custom_status": "✏️ Custom",
        "texts_default_status": "⚙️ Default",
        "texts_ask_new": "✏️ Send new text:",
        "guide_title": "📖 <b>Guide</b>",
        "guide_ask": "✍️ Enter guide text for {lang}:",

        "admins_title": "👑 <b>Admins</b>",
        "admins_ask": "👑 Enter user numeric ID:",
        "admins_added": "✅ Admin added",
        "admins_exists": "⚠️ User is already admin",
        "cols_set": "✅ Columns: {n}",
        "ad_admins_title": "👑 <b>Admins</b> ({count})",
        "ad_admins_empty": "📭 No admins",
        "ad_admins_add": "➕ Add Admin",
        "ad_admins_ask": "👑 Enter user numeric ID:",
        "ad_admins_added": "✅ Admin added",
        "ad_admins_exists_owner": "⚠️ This user is the owner",
        "ad_admins_exists_admin": "⚠️ This user is already admin",
        "ad_admins_invalid": "⚠️ Invalid ID",
        "ad_admins_self": "⚠️ You cannot add yourself",
        "ad_admins_profile": "👑 <b>Admin Profile</b>\n\n🆔 ID: <code>{uid}</code>\n📛 Name: {name}\n🔗 Username: {username}\n🕐 Added: {date}\n📊 Status: {status}",
        "ad_admins_remove_btn": "🗑 Remove from Admins",
        "ad_admins_removed": "🗑 Removed",
        "ad_admins_not_found": "❌ Admin not found",
        "ad_admins_search": "🔍 Search",
        "ad_admins_search_ask": "🔍 Enter admin numeric ID:",
        "ad_admins_back": "◀️ Back",
        "nav_prev": "◀️",
        "nav_page": "📄 {page}",
        "nav_next": "▶️",
    },
}


TEXT_KEYS = [
    "welcome", "help_text", "dl_center", "dl_select_quality",
    "support_title", "support_menu_title", "hist_title",
    "fav_title", "stats_title",
]

TEXT_LABELS = {
    "fa": {
        "welcome": "خوش‌آمدگویی",
        "help_text": "راهنمای استفاده",
        "dl_center": "مرکز دانلود",
        "dl_select_quality": "انتخاب کیفیت",
        "support_title": "پشتیبانی",
        "support_menu_title": "منوی پشتیبانی",
        "hist_title": "تاریخچه دانلودها",
        "fav_title": "علاقه‌مندی‌ها",
        "stats_title": "آمار کاربر",
    },
    "en": {
        "welcome": "Welcome",
        "help_text": "Help Guide",
        "dl_center": "Download Center",
        "dl_select_quality": "Select Quality",
        "support_title": "Support",
        "support_menu_title": "Support Menu",
        "hist_title": "Download History",
        "fav_title": "Favorites",
        "stats_title": "User Stats",
    },
}


def text_label(lang: str, key: str) -> str:
    lang = lang if lang in TEXT_LABELS else "fa"
    return TEXT_LABELS[lang].get(key, key)


def audience_label(lang: str, key: str) -> str:
    lang = lang if lang in ("fa", "en") else "fa"
    return tr(lang, f"an_audience_lbl_{key}")


def tr(lang: str, key: str, **kw) -> str:
    lang = lang if lang in I18N else "fa"
    t = I18N[lang].get(key) or I18N["fa"].get(key)
    if t is None:
        return f"[{lang}:{key}]"
    try:
        return t.format(**kw) if kw else t
    except (KeyError, IndexError):
        return t


def tr_custom(lang: str, key: str, **kw) -> str:
    custom = db_get(f"custom_text_{key}", "")
    if custom:
        if kw:
            try:
                return custom.format(**kw)
            except (KeyError, IndexError, ValueError):
                return custom
        return custom
    return tr(lang, key, **kw)


# ══════════════════════════════════════════════════════════════
# RATE / COOLDOWN HELPERS
# ══════════════════════════════════════════════════════════════
_last_dl_req: dict = {}


def is_limit_exempt(uid: int) -> bool:
    if uid in OWNER_IDS:
        return db_get("limit_owner_unlimited", "1") == "1"
    if db_get("limit_vip_unlimited", "1") == "1":
        u = UserRepo.get(uid)
        if u and u.is_vip:
            return True
    return False


def cooldown_remaining(uid: int) -> int:
    if is_limit_exempt(uid):
        return 0
    try:
        cd = int(float(db_get("limit_cooldown_sec", "3") or 0))
    except (TypeError, ValueError):
        cd = 0
    if cd <= 0:
        return 0
    now = now_ts()
    last = _last_dl_req.get(uid, 0.0)
    if now - last < cd:
        return max(1, int(cd - (now - last) + 0.999))
    _last_dl_req[uid] = now
    if len(_last_dl_req) > 5000:
        _last_dl_req.clear()
    return 0


def user_lang(user) -> str:
    if user is None:
        return "fa"
    return user.lang if user.lang in I18N else "fa"


def user_has_chosen_lang(uid: int) -> bool:
    try:
        r = get_conn().execute(
            "SELECT lang_chosen FROM users WHERE user_id=?",
            (uid,)).fetchone()
        return bool(r and r["lang_chosen"])
    except Exception:
        return True


def mark_lang_chosen(uid: int, lang: str):
    with contextlib.suppress(Exception):
        get_conn().execute(
            "UPDATE users SET lang=?, lang_chosen=1, updated_at=? "
            "WHERE user_id=?", (lang, now_ts(), uid))


# ══════════════════════════════════════════════════════════════
# EMOJI MAP (PREMIUM)
# ══════════════════════════════════════════════════════════════
_emoji_cache: dict = {}
_emoji_cache_ts: float = 0.0
_EMOJI_TTL = 2.0


def invalidate_emoji_cache():
    global _emoji_cache_ts
    _emoji_cache_ts = 0.0


def get_emoji_map() -> dict:
    global _emoji_cache, _emoji_cache_ts
    now = now_ts()
    if now - _emoji_cache_ts > _EMOJI_TTL:
        try:
            rows = get_conn().execute(
                "SELECT * FROM emoji_map ORDER BY created_at DESC").fetchall()
            _emoji_cache = {r["normal_emoji"]: (r["premium_id"], r["fallback_emoji"])
                            for r in rows}
            _emoji_cache_ts = now
        except Exception:
            _emoji_cache = {}
    return _emoji_cache


def emoji_map_count() -> int:
    r = get_conn().execute("SELECT COUNT(*) AS c FROM emoji_map").fetchone()
    return int(r["c"] or 0)


def premiumize(text: str) -> str:
    if not text:
        return text
    if db_get("premium_emoji_enabled", "1") != "1":
        return text
    emap = get_emoji_map()
    if not emap:
        return text
    keys = sorted(emap.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in keys))

    def _sub(m):
        normal = m.group(0)
        pid, _ = emap[normal]
        return f'<tg-emoji emoji-id="{pid}">{normal}</tg-emoji>'

    def _replace(chunk):
        return pattern.sub(_sub, chunk)

    parts, last = [], 0
    for m in _TG_EMOJI_TAG_RE.finditer(text):
        parts.append(_replace(text[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(_replace(text[last:]))
    return "".join(parts)


def strip_premium(text: str) -> str:
    if not text:
        return text
    return _TG_EMOJI_STRIP_RE.sub(r'\1', text)


class PremiumEmojiRequestMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        try:
            pm = getattr(method, "parse_mode", None)
            html_mode = pm is not None and (
                (isinstance(pm, str) and pm.upper() == "HTML")
                or type(pm).__name__ == "Default")
            if html_mode:
                for attr, ent in (("text", "entities"),
                                  ("caption", "caption_entities")):
                    val = getattr(method, attr, None)
                    if isinstance(val, str) and val and \
                            not getattr(method, ent, None):
                        new = premiumize(val)
                        if new != val:
                            setattr(method, attr, new)
        except Exception as e:
            logging.debug(f"premium emoji middleware: {e}")
        return await make_request(bot, method)


# ══════════════════════════════════════════════════════════════
# CANCELLATION
# ══════════════════════════════════════════════════════════════
_cancelled: set = set()
_cancel_lock = threading.Lock()
_MAX_CANCEL = 5000


def mark_cancelled(jid):
    with _cancel_lock:
        if len(_cancelled) >= _MAX_CANCEL:
            half = list(_cancelled)[:_MAX_CANCEL // 2]
            for x in half:
                _cancelled.discard(x)
        _cancelled.add(jid)


def is_cancelled(jid):
    with _cancel_lock:
        return jid in _cancelled


def clear_cancelled(jid):
    with _cancel_lock:
        _cancelled.discard(jid)


# ══════════════════════════════════════════════════════════════
# CONTAINER
# ══════════════════════════════════════════════════════════════
@dataclass
class Container:
    bot: Optional[Bot] = None
    job_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    worker_tasks: list = field(default_factory=list)
    bg_tasks: list = field(default_factory=list)
    last_progress: dict = field(default_factory=dict)


CONTAINER: Optional[Container] = None


# ══════════════════════════════════════════════════════════════
# DOWNLOADER — CORE
# ══════════════════════════════════════════════════════════════
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)


@dataclass
class VideoInfo:
    title: str
    duration: int
    filesize: int
    uploader: Optional[str]
    site: Optional[str]
    thumbnail: Optional[str]
    available_qualities: set = field(
        default_factory=lambda: {"best", "audio"})
    max_height: int = 0


@dataclass
class DownloadResult:
    path: Path
    title: str
    duration: int
    filesize: int
    artist: Optional[str] = None
    thumbnail_path: Optional[Path] = None


class DownloadError(Exception):
    pass


class DownloadCancelled(DownloadError):
    pass


def _base_ydl_opts() -> dict:
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": 30, "nocheckcertificate": True,
        "geo_bypass": True, "age_limit": 99,
        "http_headers": {"User-Agent": random.choice(USER_AGENTS)},
    }
    if ImpersonateTarget is not None and HAS_CURL_CFFI:
        with contextlib.suppress(Exception):
            opts["impersonate"] = ImpersonateTarget(client="chrome")
    cookies_path = DATA_DIR / "cookies.txt"
    if cookies_path.exists():
        opts["cookiefile"] = str(cookies_path)
    return opts


def _quality_format(q: str) -> str:
    if is_audio_quality(q):
        return "bestaudio/best"
    if q == "best":
        return "bestvideo+bestaudio/best"
    h = QUALITY_HEIGHTS.get(q)
    if h:
        return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
    return "bestvideo+bestaudio/best"


def _extract_available_qualities(info: dict) -> set:
    available = {"best", "audio"}
    heights = set()
    has_video = False
    for f in (info.get("formats") or []):
        vcodec = (f.get("vcodec") or "none").lower()
        h = f.get("height") or 0
        if vcodec and vcodec != "none":
            has_video = True
            if h:
                heights.add(int(h))
    if not has_video:
        return {"best", "audio"}
    for qkey, qh in QUALITY_HEIGHTS.items():
        for h in heights:
            if h >= qh:
                available.add(qkey)
                break
    return available


def analyze_url(url: str) -> VideoInfo:
    opts = _base_ydl_opts()
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e
    if not info:
        raise DownloadError("empty info")

    best_size = 0
    max_h = 0
    for f in (info.get("formats") or []):
        sz = f.get("filesize") or f.get("filesize_approx") or 0
        if sz > best_size:
            best_size = sz
        h = f.get("height") or 0
        if h > max_h:
            max_h = int(h)

    avail = _extract_available_qualities(info)

    return VideoInfo(
        title=info.get("title") or "No Title",
        duration=int(info.get("duration") or 0),
        filesize=best_size or int(
            info.get("filesize") or info.get("filesize_approx") or 0),
        uploader=info.get("uploader"),
        site=info.get("extractor_key"),
        thumbnail=info.get("thumbnail"),
        available_qualities=avail,
        max_height=max_h,
    )


async def analyze_async(url: str) -> VideoInfo:
    try:
        return await asyncio.to_thread(analyze_url, url)
    except DownloadError:
        raise
    except Exception as e:
        raise DownloadError(f"analyze failed: {e}") from e


def _fmt_speed(b) -> str:
    try:
        b = float(b or 0)
    except (TypeError, ValueError):
        return "0 B/s"
    for u in ("B/s", "KB/s", "MB/s", "GB/s"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB/s"


def _fmt_eta(s) -> str:
    if s is None:
        return "--"
    try:
        m, x = divmod(int(s), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{x:02d}" if h else f"{m:02d}:{x:02d}"
    except (TypeError, ValueError):
        return "--"


def download_sync(job_id: str, url: str, quality: str,
                  loop: asyncio.AbstractEventLoop,
                  progress_cb, cancelled_cb) -> DownloadResult:
    jd = DOWNLOAD_DIR / job_id
    if jd.exists():
        shutil.rmtree(jd, ignore_errors=True)
    jd.mkdir(parents=True, exist_ok=True)

    def _schedule(p, sp, et):
        try:
            fut = asyncio.run_coroutine_threadsafe(progress_cb(p, sp, et), loop)
            fut.add_done_callback(lambda f: f.exception() and None)
        except Exception:
            pass

    def _hook(d):
        if cancelled_cb(job_id):
            raise DownloadCancelled("cancelled")
        st = d.get("status")
        if st == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            dn = d.get("downloaded_bytes") or 0
            if tot and tot > 0:
                p = dn / tot * 100
            else:
                fi = d.get("fragment_index") or 0
                fc = d.get("fragment_count") or 0
                p = (fi / fc * 100) if (fc and fc > 0) else 0.0
            _schedule(p, _fmt_speed(d.get("speed") or 0),
                      _fmt_eta(d.get("eta")))
        elif st == "finished":
            _schedule(100.0, "…", "00:00")

    opts = _base_ydl_opts()
    opts.update({
        "outtmpl": str(jd / "%(title).80s-%(id)s.%(ext)s"),
        "retries": 3, "fragment_retries": 3,
        "continuedl": True, "progress_hooks": [_hook],
    })

    if is_audio_quality(quality):
        if not shutil.which("ffmpeg"):
            raise DownloadError("FFmpeg not installed")
        opts["format"] = "bestaudio/best"
        if quality == "audio_best":
            opts["prefer_ffmpeg"] = True
        else:
            bitrate = {"audio_320": "320", "audio_128": "128"}.get(quality, "192")
            opts.update({
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }],
                "prefer_ffmpeg": True,
            })
    else:
        opts.update({
            "format": _quality_format(quality),
            "merge_output_format": "mp4",
        })
        if db_get("download_subtitles", "0") == "1":
            opts.update({
                "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": ["fa", "en"],
                "subtitlesformat": "srt/best",
            })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e
    if not info:
        raise DownloadError("empty info")

    final = None
    if is_audio_quality(quality):
        audios = [p for p in jd.rglob("*") if p.is_file()
                  and p.suffix.lower() in (".mp3", ".m4a", ".opus",
                                            ".ogg", ".webm", ".aac",
                                            ".flac", ".wav")]
        if audios:
            final = max(audios, key=lambda p: p.stat().st_size)
    if final is None:
        files = [p for p in jd.rglob("*") if p.is_file() and
                 p.suffix.lower() not in (".srt", ".vtt", ".ass", ".json")]
        if not files:
            raise DownloadError("No output file")
        files.sort(key=lambda p: p.stat().st_size, reverse=True)
        final = files[0]

    dur = int(info.get("duration") or 0)
    if dur <= 0:
        dur = _probe_duration(final)

    return DownloadResult(path=final,
                          title=info.get("title") or "No Title",
                          duration=dur,
                          filesize=final.stat().st_size)


def _gallery_dl_sync(url: str, jd: Path, want_video: bool) -> Optional[Path]:
    if not HAS_GALLERY_DL:
        return None
    try:
        import gallery_dl.job  # noqa: F401
        gallery_dl.config.load()
        gcfg = gallery_dl.config
        gcfg.set(("extractor",), "base-directory", str(jd))
        gcfg.set(("extractor",), "directory", ["."])
        gcfg.set(("extractor",), "filename", "{filename}.{extension}")
        cookies_path = DATA_DIR / "cookies.txt"
        if cookies_path.exists():
            gcfg.set(("extractor",), "cookies", str(cookies_path))
        gcfg.set(("extractor", "generic"), "enabled", True)
        gcfg.set(("output",), "mode", "null")
        gallery_dl.job.DownloadJob(url).run()
    except Exception as e:
        logging.info(f"[gallery-dl] failed: {e}")
        return None
    all_files = [f for f in jd.rglob("*") if f.is_file()]
    files = [f for f in all_files
             if f.suffix.lower() in (VIDEO_EXTS if want_video else IMAGE_EXTS)]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    return files[0]


async def download_photo_only(url: str, job_id: str) -> DownloadResult:
    import aiohttp
    jd = DOWNLOAD_DIR / job_id
    if jd.exists():
        shutil.rmtree(jd, ignore_errors=True)
    jd.mkdir(parents=True, exist_ok=True)
    try:
        max_mb = int(db_get("max_photo_size_mb", "2048"))
    except (TypeError, ValueError):
        max_mb = 2048
    max_bytes = max_mb * 1024 * 1024
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    timeout = aiohttp.ClientTimeout(total=600, connect=30)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(url, headers=headers, allow_redirects=True) as r:
                if r.status == 200:
                    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                    if ctype.startswith("image/"):
                        ext = _IMG_CTYPE_EXT.get(ctype, ".jpg")
                        path = jd / f"image_{job_id}{ext}"
                        written = 0
                        with open(path, "wb") as f:
                            async for chunk in r.content.iter_chunked(65536):
                                written += len(chunk)
                                if written > max_bytes:
                                    raise DownloadError("Image too large")
                                f.write(chunk)
                        if path.stat().st_size > 0:
                            return DownloadResult(path=path, title="Image",
                                                  duration=0,
                                                  filesize=path.stat().st_size)
    except DownloadError:
        raise
    except Exception as e:
        logging.info(f"[photo] direct failed: {e}")

    path = await asyncio.to_thread(_gallery_dl_sync, url, jd, False)
    if path and path.exists() and path.stat().st_size > 0:
        return DownloadResult(path=path, title=path.stem,
                              duration=0, filesize=path.stat().st_size)

    try:
        opts = _base_ydl_opts()
        opts["skip_download"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        thumb_url = info.get("thumbnail") if info else None
        if thumb_url:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(thumb_url, headers=headers) as r:
                    if r.status == 200:
                        path = jd / f"thumb_{job_id}.jpg"
                        with open(path, "wb") as f:
                            async for chunk in r.content.iter_chunked(65536):
                                f.write(chunk)
                        if path.stat().st_size > 0:
                            return DownloadResult(path=path, title="Thumbnail",
                                                  duration=0,
                                                  filesize=path.stat().st_size)
    except Exception as e:
        logging.info(f"[photo] yt-dlp thumb failed: {e}")

    raise DownloadError("No image found / عکسی پیدا نشد")


async def download_video_only(url: str, job_id: str) -> DownloadResult:
    jd = DOWNLOAD_DIR / job_id
    if jd.exists():
        shutil.rmtree(jd, ignore_errors=True)
    jd.mkdir(parents=True, exist_ok=True)
    try:
        loop = asyncio.get_running_loop()
        async def _noop_progress(p, s, e):
            return None

        result = await asyncio.to_thread(
            download_sync, job_id, url, "best", loop,
            _noop_progress, is_cancelled)
        if result.path.exists() and is_video_file(result.path):
            return result
    except Exception as e:
        logging.info(f"[video] yt-dlp failed: {e}")
    path = await asyncio.to_thread(_gallery_dl_sync, url, jd, True)
    if path and path.exists() and path.stat().st_size > 0:
        return DownloadResult(path=path, title=path.stem,
                              duration=0, filesize=path.stat().st_size)
    raise DownloadError("No video found / ویدئویی پیدا نشد")


async def download_music_only(url: str, job_id: str,
                              quality: str = "audio") -> DownloadResult:
    """دانلود آهنگ به صورت MP3 با متادیتا و کاور."""
    jd = DOWNLOAD_DIR / job_id
    if jd.exists():
        shutil.rmtree(jd, ignore_errors=True)
    jd.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        raise DownloadError("FFmpeg required for music download")

    def _sync() -> dict:
        opts = _base_ydl_opts()
        base_opts = {
            "outtmpl": str(jd / "%(title).80s.%(ext)s"),
            "format": "bestaudio/best",
            "prefer_ffmpeg": True,
            "writethumbnail": True,
        }
        if quality == "audio_best":
            opts.update(base_opts)
        else:
            bitrate = {"audio_320": "320", "audio_128": "128"}.get(quality, "192")
            base_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }]
            opts.update(base_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    try:
        info = await asyncio.to_thread(_sync)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e)) from e
    except DownloadError:
        raise
    except Exception as e:
        raise DownloadError(f"music failed: {e}") from e

    if not info:
        raise DownloadError("empty info")

    mp3s = [p for p in jd.glob("*.mp3") if p.is_file()]
    if not mp3s:
        audios = [p for p in jd.rglob("*") if p.is_file() and
                  p.suffix.lower() in (".mp3", ".m4a", ".opus",
                                       ".ogg", ".webm", ".aac",
                                       ".flac", ".wav")]
        if not audios:
            raise DownloadError("No audio output")
        mp3s = audios
    mp3 = max(mp3s, key=lambda p: p.stat().st_size)

    thumb_path: Optional[Path] = None
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        thumbs = [t for t in jd.glob(f"*{ext}") if t.is_file()]
        if thumbs:
            thumb_path = max(thumbs, key=lambda p: p.stat().st_size)
            break

    if thumb_path and thumb_path.suffix.lower() == ".webp" and HAS_PIL:
        try:
            with Image.open(thumb_path) as im:
                jpg_path = thumb_path.with_suffix(".jpg")
                im.convert("RGB").save(jpg_path, "JPEG", quality=88)
                thumb_path = jpg_path
        except Exception:
            pass

    title = str(info.get("title") or mp3.stem)
    artist = (info.get("artist") or info.get("uploader") or
              info.get("creator") or info.get("channel") or
              info.get("album_artist") or "Unknown")
    artist = str(artist).strip() or "Unknown"

    duration = int(info.get("duration") or 0)
    if duration <= 0:
        duration = _probe_duration(mp3)

    return DownloadResult(
        path=mp3,
        title=title,
        duration=duration,
        filesize=mp3.stat().st_size,
        artist=artist,
        thumbnail_path=thumb_path,
    )


# ══════════════════════════════════════════════════════════════
# KEYBOARD
# ══════════════════════════════════════════════════════════════
def build_menu(scope: str, lang: str,
               is_admin_flag: bool = False) -> InlineKeyboardMarkup:
    rows = list(MenuButtonRepo.by_scope(scope, visible_only=True))
    try:
        cols = int(db_get(f"menu_cols_{scope}", "2"))
    except ValueError:
        cols = 2
    if cols not in (1, 2, 3, 4):
        cols = 2

    valid_keys = (MenuButtonRepo.USER_KEYS if scope == "user"
                  else MenuButtonRepo.ADMIN_KEYS)
    buttons = []
    for r in rows:
        key = r["btn_key"]
        if key not in valid_keys:
            continue
        if db_get(key, "1") != "1":
            continue
        if scope == "user" and key == "menu_admin" and not is_admin_flag:
            continue
        if r["label"]:
            label = r["label"]
        else:
            if scope == "user":
                dk = MenuButtonRepo.DEFAULTS_USER.get(key, ("back", ""))[0]
            else:
                dk = MenuButtonRepo.DEFAULTS_ADMIN.get(key, ("ad_back", ""))[0]
            label = tr(lang, dk)
        try:
            if r["emoji_id"] and r["emoji_fb"] and \
                    not label.startswith(r["emoji_fb"]):
                label = f"{r['emoji_fb']} {label}"
        except Exception:
            pass
        if scope == "user":
            cb_data = MenuButtonRepo.DEFAULTS_USER.get(key, ("", "noop"))[1]
        else:
            cb_data = MenuButtonRepo.DEFAULTS_ADMIN.get(key, ("", "noop"))[1]
        color = (r["color"] if r["color"] in
                 ("primary", "success", "danger") else None)
        kwargs = {"text": label[:64], "callback_data": safe_cb(cb_data)}
        if color:
            with contextlib.suppress(Exception):
                kwargs["style"] = color
        try:
            buttons.append(InlineKeyboardButton(**kwargs))
        except Exception:
            kwargs.pop("style", None)
            kwargs["text"] = label[:64]
            with contextlib.suppress(Exception):
                buttons.append(InlineKeyboardButton(**kwargs))

    if not buttons:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="•", callback_data="noop")]])
    keyboard = [buttons[i:i + cols] for i in range(0, len(buttons), cols)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _load_custom_buttons() -> list:
    try:
        rows = get_conn().execute(
            "SELECT * FROM custom_buttons WHERE is_active=1 "
            "ORDER BY row_order, id LIMIT 10").fetchall()
        return [{"label": str(r["label"])[:40],
                 "callback": str(r["callback"])[:60]} for r in rows]
    except Exception as e:
        logging.warning(f"load custom_buttons failed: {e}")
        return []


def main_menu(user: User) -> InlineKeyboardMarkup:
    is_admin_flag = user.user_id in OWNER_IDS or is_admin(user.user_id)
    kb = build_menu("user", user_lang(user), is_admin_flag=is_admin_flag)

    if db_get("show_custom_buttons", "1") == "1":
        customs = _load_custom_buttons()
        if customs:
            rows = list(kb.inline_keyboard)
            for cbt in customs:
                rows.append([InlineKeyboardButton(
                    text=cbt["label"],
                    callback_data=safe_cb(cbt["callback"]))])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def admin_menu(lang: str) -> InlineKeyboardMarkup:
    kb = build_menu("admin", lang)
    rows = list(kb.inline_keyboard)
    rows.append([InlineKeyboardButton(text=tr(lang, "home_back"),
                                       callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quality_kb(job_id: str, lang: str, available: set = None,
               mode: str = "video") -> InlineKeyboardMarkup:
    admin_allowed = allowed_qualities()
    labels = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"])
    b = InlineKeyboardBuilder()

    if mode == "music":
        order = MUSIC_QUALITIES
        show = admin_allowed & set(MUSIC_QUALITIES)
        prefix = "mq"
    else:
        order = VIDEO_QUALITIES
        show = admin_allowed & set(VIDEO_QUALITIES)
        if available is not None and db_get("smart_quality", "1") == "1":
            show = show & (available | {"best"})
        prefix = "q"

    shown = [q for q in order if q in show]
    if not shown:
        shown = ["audio"] if mode == "music" else ["best"]

    for q in shown:
        b.row(InlineKeyboardButton(
            text=labels.get(q, q),
            callback_data=safe_cb(f"{prefix}:{job_id}:{q}")))

    b.row(InlineKeyboardButton(text=tr(lang, "cancel"),
                                callback_data=safe_cb(f"jback:{job_id}")))
    return b.as_markup()


def join_kb(channel: str, lang: str) -> InlineKeyboardMarkup:
    ch = channel.lstrip("@")
    b = InlineKeyboardBuilder()
    if ch and not ch.lstrip("-").isdigit():
        b.row(InlineKeyboardButton(text=f"📢 @{ch}", url=f"https://t.me/{ch}"))
    b.row(InlineKeyboardButton(text=tr(lang, "check_join"),
                                callback_data="check_join"))
    return b.as_markup()


# ══════════════════════════════════════════════════════════════
# FSM STATES
# ══════════════════════════════════════════════════════════════
class Flow(StatesGroup):
    dl_waiting_url = State()
    support_message = State()
    a_users_search = State()
    a_broadcast_content = State()
    a_broadcast_confirm = State()
    a_setting_value = State()
    a_setting_maint = State()
    a_limit_value = State()
    a_channel = State()
    a_ticket_reply = State()
    a_auto_backup_hours = State()
    a_up_zip = State()
    a_miniapp_url = State()
    emoji_add_premium = State()
    emoji_add_normal = State()
    start_emoji = State()
    start_sticker = State()
    mn_label = State()
    mn_emoji = State()
    cbtn_label = State()
    cbtn_callback = State()
    text_value = State()
    guide_text = State()
    admin_new_id = State()
    admin_search = State()

    a_announce_msg = State()
    a_announce_media = State()
    a_announce_confirm = State()
    a_announce_schedule_time = State()
    a_announce_test = State()
    a_announce_channel_id = State()
    a_anc_text = State()
    a_anc_media = State()
    a_anc_confirm = State()
    a_anc_test = State()


# ══════════════════════════════════════════════════════════════
# MIDDLEWARES
# ══════════════════════════════════════════════════════════════
class InjectMiddleware(BaseMiddleware):
    def __init__(self, container: Container):
        self.container = container
        super().__init__()

    async def __call__(self, handler, event, data):
        data["c"] = self.container
        return await handler(event, data)


class UserUpsertMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and not getattr(u, "is_bot", False):
            chat = getattr(event, "chat", None)
            if chat is None:
                msg = getattr(event, "message", None)
                if msg is not None:
                    chat = getattr(msg, "chat", None)
            chat_id = chat.id if chat else u.id
            with contextlib.suppress(Exception):
                UserRepo.upsert(u.id, chat_id, u.username, u.first_name)
        return await handler(event, data)


class BlockGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and u.id not in OWNER_IDS:
            try:
                user = UserRepo.get(u.id)
                if user and user.is_blocked:
                    with contextlib.suppress(Exception):
                        if isinstance(event, CallbackQuery):
                            await event.answer("🚫", show_alert=True)
                        elif isinstance(event, Message):
                            await event.answer("🚫")
                    return None
            except Exception:
                pass
        return await handler(event, data)


class MaintenanceGuard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if not u:
            return await handler(event, data)
        if u.id in OWNER_IDS:
            return await handler(event, data)
        try:
            user = UserRepo.get(u.id)
            if user and user.is_vip:
                return await handler(event, data)
        except Exception:
            pass
        if db_get("maintenance", "0") == "1":
            text = db_get("maintenance_text", "🔧")
            with contextlib.suppress(Exception):
                if isinstance(event, CallbackQuery):
                    await event.answer(text[:200], show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(text[:4000])
            return None
        return await handler(event, data)


class CallbackRateLimitMiddleware(BaseMiddleware):
    def __init__(self, per_sec: float = 0.6):
        self.per_sec = per_sec
        self._last: dict = {}
        super().__init__()

    async def __call__(self, handler, event, data):
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        u = getattr(event, "from_user", None)
        if u is None:
            return await handler(event, data)
        cb_data = event.data or ""
        if cb_data.startswith(("q:", "mq:", "redl:", "histview:", "favview:")):
            if u.id not in OWNER_IDS:
                now = now_ts()
                last = self._last.get(u.id, 0.0)
                if now - last < self.per_sec:
                    with contextlib.suppress(Exception):
                        await event.answer("⏳", show_alert=False)
                    return None
                self._last[u.id] = now
                if len(self._last) > 5000:
                    self._last.clear()
        return await handler(event, data)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
async def safe_edit(target, text: str, markup=None):
    try:
        await target.edit_text(text, reply_markup=markup)
        return True
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "not modified" in s:
            return True
        if "no text" in s or "caption" in s:
            with contextlib.suppress(Exception):
                await target.edit_caption(caption=text[:1024], reply_markup=markup)
                return True
        with contextlib.suppress(Exception):
            await target.answer(text, reply_markup=markup)
            return True
    except Exception:
        return False
    return False


async def send_text_safe(bot, chat_id, text, **kw):
    try:
        return await bot.send_message(chat_id, text, **kw)
    except TelegramBadRequest as e:
        low = str(e).lower()
        if "parse" in low or "entities" in low:
            return await bot.send_message(chat_id, text, parse_mode=None, **kw)
        raise


async def check_membership(uid: int) -> bool:
    if db_get("force_join", "0") != "1":
        return True
    if uid in OWNER_IDS:
        return True
    channel = db_get("channel_username", "").strip()
    if not channel:
        return True
    bot = CONTAINER.bot if CONTAINER else None
    if not bot:
        return True
    try:
        m = await bot.get_chat_member(channel, uid)
        return m.status not in ("left", "kicked")
    except Exception:
        return True


async def send_join_prompt(target, lang: str):
    channel = db_get("channel_username", "").strip()
    text = tr(lang, "please_join") + f"\n\n📢 <code>{esc(channel)}</code>"
    kb = join_kb(channel, lang)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    else:
        await safe_edit(target, text, kb)


async def send_home(target, user: User, edit: bool = True):
    lang = user_lang(user)
    text = tr_custom(lang, "welcome", name=esc(user.first_name or "User"))
    kb = main_menu(user)
    if isinstance(target, CallbackQuery):
        if edit:
            await safe_edit(target.message, text, kb)
        else:
            with contextlib.suppress(Exception):
                await target.message.answer(text, reply_markup=kb)
    elif isinstance(target, Message):
        await target.answer(text, reply_markup=kb)


async def send_start_media(chat_id: int, bot: Bot):
    if db_get("start_sticker_enabled", "1") == "1":
        sid = db_get("start_sticker_file_id", "").strip()
        if sid:
            try:
                await bot.send_sticker(chat_id=chat_id, sticker=sid)
                return
            except Exception:
                pass
    val = db_get("start_emoji_id", "").strip()
    if not val:
        return
    fb = db_get("start_emoji_fb", "✨") or "✨"
    with contextlib.suppress(Exception):
        if val.isdigit():
            await bot.send_message(
                chat_id=chat_id,
                text=f'<tg-emoji emoji-id="{val}">{fb}</tg-emoji>')
        else:
            await bot.send_message(chat_id=chat_id, text=val)


def _purge_job_files(rows):
    for r in rows:
        with contextlib.suppress(Exception):
            fp = r["file_path"]
            if fp:
                fpp = Path(fp)
                if fpp.exists():
                    fpp.unlink()
            jd = DOWNLOAD_DIR / str(r["job_id"])
            if jd.exists():
                shutil.rmtree(jd, ignore_errors=True)


def _effective_filesize(j: Job) -> int:
    if j.filesize and j.filesize > 0:
        return j.filesize
    if j.file_path:
        with contextlib.suppress(Exception):
            p = Path(j.file_path)
            if p.exists() and p.is_file():
                return p.stat().st_size
    return 0


def _effective_duration(j: Job) -> int:
    return j.duration if (j.duration and j.duration > 0) else 0


async def _send_photo_with_compression(
    bot: Bot, chat_id: int, image_path: Path,
    caption: str, job_id: str, lang: str,
) -> Optional[Message]:
    try:
        size = image_path.stat().st_size
    except Exception:
        return None
    if size <= PHOTO_TG_LIMIT:
        with contextlib.suppress(Exception):
            return await bot.send_photo(
                chat_id=chat_id, photo=FSInputFile(str(image_path)),
                caption=caption[:1024], request_timeout=1800)
    if db_get("compress_large_photos", "1") == "1" and HAS_PIL:
        with contextlib.suppress(Exception):
            compressed = await asyncio.to_thread(
                compress_image_for_tg, image_path, PHOTO_TG_LIMIT)
            if compressed and compressed.exists() and \
                    compressed.stat().st_size <= PHOTO_TG_LIMIT:
                with contextlib.suppress(Exception):
                    return await bot.send_photo(
                        chat_id=chat_id, photo=FSInputFile(str(compressed)),
                        caption=caption[:1024], request_timeout=1800)
    with contextlib.suppress(Exception):
        return await bot.send_document(
            chat_id=chat_id, document=FSInputFile(str(image_path)),
            caption=caption[:1024], request_timeout=1800)
    return None


async def _send_music_file(bot: Bot, chat_id: int, result: DownloadResult,
                            caption: str) -> Optional[Message]:
    as_audio = db_get("music_send_as_audio", "1") == "1"
    title = (result.title or "Audio")[:64]
    artist = (result.artist or "Unknown")[:64]
    duration = max(0, int(result.duration or 0))

    base_kwargs: dict = {
        "chat_id": chat_id,
        "caption": caption[:1024],
        "request_timeout": 1800,
    }

    if as_audio:
        kwargs = dict(base_kwargs)
        kwargs.update({
            "audio": FSInputFile(str(result.path)),
            "title": title,
            "performer": artist,
        })
        if duration > 0:
            kwargs["duration"] = duration
        if result.thumbnail_path and result.thumbnail_path.exists():
            try:
                kwargs["thumbnail"] = FSInputFile(str(result.thumbnail_path))
                return await bot.send_audio(**kwargs)
            except Exception:
                kwargs.pop("thumbnail", None)
        try:
            return await bot.send_audio(**kwargs)
        except Exception:
            pass

    try:
        return await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(str(result.path)),
            caption=caption[:1024],
            request_timeout=1800)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# JOB PIPELINE
# ══════════════════════════════════════════════════════════════
async def update_progress(c: Container, job_id: str, pct: float,
                          speed: str, eta: str):
    job = JobRepo.get(job_id)
    if not job or not job.msg_id:
        return
    now = now_ts()
    last = c.last_progress.get(job_id, 0)
    if pct < 100 and (now - last < 1.5):
        return
    if pct >= 100:
        c.last_progress.pop(job_id, None)
    else:
        c.last_progress[job_id] = now

    JobRepo.update(job_id, progress=pct, speed=speed, eta=eta)
    user = UserRepo.get(job.user_id)
    lang = user_lang(user)
    text = tr(lang, "dl_downloading",
              title=esc((job.title or "...")[:80]),
              pct=pct, bar=progress_bar(pct),
              speed=speed, eta=eta, id=job_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "cancel"),
                             callback_data=safe_cb(f"jcancel:{job_id}"))]])
    with contextlib.suppress(Exception):
        await c.bot.edit_message_text(
            chat_id=job.chat_id, message_id=job.msg_id,
            text=text, reply_markup=kb)


async def upload_result(c: Container, job_id: str, result: DownloadResult):
    job = JobRepo.get(job_id)
    if not job:
        return
    if is_cancelled(job_id):
        JobRepo.update(job_id, status=STATUS_CANCELLED, finished_at=now_ts())
        return
    if job.status == STATUS_COMPLETED:
        return

    path = result.path
    if not path.exists():
        raise DownloadError("File not found")

    max_mb = int(db_get("max_file_size_mb", "2048"))
    size = path.stat().st_size
    user = UserRepo.get(job.user_id)
    lang = user_lang(user)

    if size > max_mb * 1024 * 1024:
        JobRepo.update(job_id, status=STATUS_FAILED, error="too large",
                       finished_at=now_ts())
        UserRepo.bump(job.user_id, "failed_dl")
        with contextlib.suppress(Exception):
            await c.bot.send_message(job.chat_id, tr(lang, "dl_too_large"))
        return

    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(
        job.quality, job.quality)
    delay = int(db_get("delete_delay", "60"))

    duration_final = result.duration or job.duration or 0
    if duration_final <= 0:
        duration_final = await asyncio.to_thread(_probe_duration, path) or 0

    caption = tr(lang, "dl_completed",
                 title=esc(result.title[:120]), quality=esc(qn),
                 size=fmt_bytes(result.filesize),
                 duration=fmt_duration(duration_final),
                 id=job_id, delay=delay)

    sent = None
    is_audio = is_audio_quality(job.quality) or \
        path.suffix.lower() in (".mp3", ".m4a", ".opus",
                                ".ogg", ".flac", ".wav", ".aac")

    if is_image_file(path):
        cap_p = tr(lang, "dl_photo_completed",
                   size=fmt_bytes(size), id=job_id, delay=delay)
        sent = await _send_photo_with_compression(
            c.bot, job.chat_id, path, cap_p, job_id, lang)
        if sent:
            JobRepo.update(
                job_id, status=STATUS_COMPLETED, progress=100.0,
                msg_id=sent.message_id, delete_at=now_ts() + delay,
                finished_at=now_ts(), filesize=size, file_path=str(path),
                duration=duration_final or 0)
            UserRepo.bump(job.user_id, "success_dl")
            return

    if is_audio:
        artist_lbl = result.artist or "Arka Downloader"
        with contextlib.suppress(Exception):
            kwargs = {
                "chat_id": job.chat_id,
                "audio": FSInputFile(str(path)),
                "caption": caption[:1024],
                "title": (result.title or "Audio")[:60],
                "performer": str(artist_lbl)[:60],
                "duration": duration_final,
                "request_timeout": 1800,
            }
            if result.thumbnail_path and result.thumbnail_path.exists():
                try:
                    kwargs["thumbnail"] = FSInputFile(
                        str(result.thumbnail_path))
                    sent = await c.bot.send_audio(**kwargs)
                except Exception:
                    kwargs.pop("thumbnail", None)
                    sent = await c.bot.send_audio(**kwargs)
            else:
                sent = await c.bot.send_audio(**kwargs)

    if sent is None and not is_audio and size <= max_mb * 1024 * 1024:
        with contextlib.suppress(Exception):
            sent = await c.bot.send_video(
                chat_id=job.chat_id, video=FSInputFile(str(path)),
                caption=caption[:1024], supports_streaming=True,
                duration=duration_final, request_timeout=1800)

    if sent is None:
        try:
            sent = await c.bot.send_document(
                chat_id=job.chat_id, document=FSInputFile(str(path)),
                caption=caption[:1024], request_timeout=1800)
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                await asyncio.sleep(5)
                JobRepo.update(
                    job_id, status=STATUS_COMPLETED, progress=100.0,
                    delete_at=now_ts() + delay, finished_at=now_ts(),
                    filesize=result.filesize,
                    duration=duration_final or 0, file_path=str(path))
                UserRepo.bump(job.user_id, "success_dl")
                return
            JobRepo.update(job_id, status=STATUS_FAILED, error=str(e),
                           finished_at=now_ts())
            UserRepo.bump(job.user_id, "failed_dl")
            with contextlib.suppress(Exception):
                await c.bot.send_message(
                    job.chat_id, tr(lang, "dl_failed", id=job_id))
            return

    JobRepo.update(
        job_id, status=STATUS_COMPLETED, progress=100.0,
        msg_id=sent.message_id, delete_at=now_ts() + delay,
        finished_at=now_ts(), filesize=result.filesize,
        duration=duration_final or 0, file_path=str(path))
    UserRepo.bump(job.user_id, "success_dl")

    with contextlib.suppress(Exception):
        for sub in path.parent.glob("*.srt"):
            await c.bot.send_document(
                chat_id=job.chat_id, document=FSInputFile(str(sub)),
                caption=tr(lang, "subtitle_label"))
            break


async def process_job(c: Container, job_id: str):
    job = JobRepo.get(job_id)
    if not job or job.status in (STATUS_CANCELLED, STATUS_COMPLETED):
        return
    cur = get_conn().execute(
        "UPDATE jobs SET status=?, started_at=? WHERE job_id=? AND status=?",
        (STATUS_DOWNLOADING, now_ts(), job_id, STATUS_QUEUED))
    if cur.rowcount == 0:
        return
    clear_cancelled(job_id)
    max_retries = int(db_get("max_retries", "2"))
    quality = job.quality or "best"
    attempts = 0
    while attempts <= max_retries:
        if is_cancelled(job_id):
            JobRepo.update(job_id, status=STATUS_CANCELLED, finished_at=now_ts())
            return
        attempts += 1
        JobRepo.update(job_id, status=STATUS_DOWNLOADING, started_at=now_ts())

        async def progress_cb(p, s, e):
            await update_progress(c, job_id, p, s, e)

        try:
            loop = asyncio.get_running_loop()
            result = await asyncio.to_thread(
                download_sync, job_id, job.url, quality, loop,
                progress_cb, is_cancelled)
            if is_cancelled(job_id):
                JobRepo.update(job_id, status=STATUS_CANCELLED)
                return
            JobRepo.update(job_id, status=STATUS_UPLOADING,
                           progress=100.0, file_path=str(result.path))
            for up_try in range(max_retries + 1):
                try:
                    await upload_result(c, job_id, result)
                    break
                except DownloadCancelled:
                    JobRepo.update(job_id, status=STATUS_CANCELLED,
                                   finished_at=now_ts())
                    return
                except Exception as ue:
                    logging.error(
                        f"upload_result error (try {up_try + 1}): {ue}")
                    final = JobRepo.get(job_id)
                    if final and final.status in (
                            STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                        break
                    if up_try < max_retries:
                        await asyncio.sleep(2)
            final = JobRepo.get(job_id)
            if final and final.status in (STATUS_COMPLETED, STATUS_FAILED,
                                          STATUS_CANCELLED):
                return
            JobRepo.update(job_id, status=STATUS_FAILED, error="upload_failed",
                           finished_at=now_ts())
            UserRepo.bump(job.user_id, "failed_dl")
            user = UserRepo.get(job.user_id)
            lang = user_lang(user)
            with contextlib.suppress(Exception):
                await c.bot.send_message(
                    job.chat_id, tr(lang, "dl_failed", id=job_id))
            return
        except DownloadCancelled:
            JobRepo.update(job_id, status=STATUS_CANCELLED, finished_at=now_ts())
            return
        except Exception as e:
            logging.warning(f"Job {job_id} attempt {attempts} failed: {e}")
            if attempts > max_retries:
                final = JobRepo.get(job_id)
                if final and final.status == STATUS_COMPLETED:
                    return
                JobRepo.update(job_id, status=STATUS_FAILED, error=str(e),
                               finished_at=now_ts())
                UserRepo.bump(job.user_id, "failed_dl")
                user = UserRepo.get(job.user_id)
                lang = user_lang(user)
                with contextlib.suppress(Exception):
                    await c.bot.send_message(
                        job.chat_id, tr(lang, "dl_failed", id=job_id))
                return
            await asyncio.sleep(2)


async def worker(c: Container, worker_id: int):
    while not c.shutdown_event.is_set():
        try:
            job_id = await asyncio.wait_for(c.job_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        try:
            await process_job(c, job_id)
        except Exception as e:
            logging.error(f"Worker {worker_id} crashed: {e}")
        finally:
            with contextlib.suppress(Exception):
                c.job_queue.task_done()


# ══════════════════════════════════════════════════════════════
# ROUTER INIT
# ══════════════════════════════════════════════════════════════
_ANSWERED_CB: dict = {}
_orig_cb_answer = CallbackQuery.answer


async def _cb_answer_once(self, *args, **kwargs):
    qid = getattr(self, "id", None)
    if qid is not None:
        if qid in _ANSWERED_CB:
            return True
        _ANSWERED_CB[qid] = None
        if len(_ANSWERED_CB) > 5000:
            for k in list(_ANSWERED_CB)[:2500]:
                _ANSWERED_CB.pop(k, None)
    return await _orig_cb_answer(self, *args, **kwargs)


with contextlib.suppress(Exception):
    CallbackQuery.answer = _cb_answer_once

router = Router(name="main")


# ══════════════════════════════════════════════════════════════
# START & MAIN
# ══════════════════════════════════════════════════════════════
async def show_first_lang_picker(target, state: FSMContext = None):
    if state:
        await state.clear()
    text = ("🌐 <b>زبان خود را انتخاب کنید</b>\n"
            "<b>Select your language</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🇮🇷  فارسی\n"
            "🇬🇧  English")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇮🇷  فارسی",
                              callback_data="firstlang:fa")],
        [InlineKeyboardButton(text="🇬🇧  English",
                              callback_data="firstlang:en")],
    ])
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    elif isinstance(target, CallbackQuery):
        await safe_edit(target.message, text, kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, c: Container):
    await state.clear()
    u = message.from_user
    if not u:
        return
    UserRepo.upsert(u.id, message.chat.id, u.username, u.first_name)
    user = UserRepo.get(u.id)
    if not user:
        return
    if user.is_blocked and u.id not in OWNER_IDS:
        await message.answer(tr(user_lang(user), "blocked"))
        return
    if not await check_membership(u.id):
        await send_join_prompt(message, user_lang(user))
        return

    if not user_has_chosen_lang(u.id):
        await show_first_lang_picker(message, state)
        return

    await send_start_media(message.chat.id, c.bot)
    await send_home(message, user, edit=False)


@router.callback_query(F.data.startswith("firstlang:"))
async def cb_firstlang(cb: CallbackQuery, state: FSMContext, c: Container):
    lang = cb.data.split(":", 1)[1]
    if lang not in ("fa", "en"):
        await cb.answer()
        return
    mark_lang_chosen(cb.from_user.id, lang)
    await cb.answer(tr(lang, "saved"))
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    await send_home(cb, user, edit=True)


@router.message(Command("lang"))
async def cmd_lang(message: Message, c: Container):
    u = message.from_user
    if not u:
        return
    user = UserRepo.get(u.id)
    lang = user_lang(user)
    fa_mark = "✅ " if (user and user.lang == "fa") else ""
    en_mark = "✅ " if (user and user.lang == "en") else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{fa_mark}🇮🇷 فارسی",
                              callback_data="lang:set:fa")],
        [InlineKeyboardButton(text=f"{en_mark}🇬🇧 English",
                              callback_data="lang:set:en")],
        [InlineKeyboardButton(text=tr(lang, "back"),
                              callback_data="menu:home")],
    ])
    await message.answer(tr(lang, "lang_title"), reply_markup=kb)


# ⚠️ دستور /admin حذف شد
# ⚠️ دستور /cancel حذف شد


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "check_join")
async def cb_check_join(cb: CallbackQuery, c: Container):
    u = cb.from_user
    if await check_membership(u.id):
        user = UserRepo.get(u.id)
        if not user:
            await cb.answer()
            return
        await cb.answer(tr(user_lang(user), "join_ok"))
        await send_home(cb, user, edit=True)
    else:
        user = UserRepo.get(u.id)
        lang = user_lang(user)
        await cb.answer(tr(lang, "join_first"), show_alert=True)


@router.callback_query(F.data == "menu:home")
async def cb_home(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await state.clear()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    await send_home(cb, user, edit=True)


# ══════════════════════════════════════════════════════════════
# LANGUAGE
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("lang:set:"))
async def cb_lang_set(cb: CallbackQuery, c: Container):
    new_lang = cb.data.split(":")[-1]
    if new_lang not in ("fa", "en"):
        await cb.answer()
        return
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    if user.lang == new_lang and user_has_chosen_lang(user.user_id):
        await cb.answer(tr(user_lang(user), "lang_same"), show_alert=True)
        return
    mark_lang_chosen(user.user_id, new_lang)
    user = UserRepo.get(user.user_id)
    await cb.answer(tr(user_lang(user), "saved"))
    await send_home(cb, user, edit=True)


# ══════════════════════════════════════════════════════════════
# DOWNLOAD
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:download")
async def cb_download(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await state.clear()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    if not await check_membership(user.user_id):
        await send_join_prompt(cb.message, lang)
        return

    photo_enabled = db_get("photo_download_enabled", "1") == "1"
    video_enabled = db_get("video_download_enabled", "1") == "1"
    music_enabled = db_get("music_download_enabled", "1") == "1"

    available = []
    if photo_enabled: available.append("photo")
    if video_enabled: available.append("video")
    if music_enabled: available.append("music")

    if not available:
        await safe_edit(cb.message, "⚠️",
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=tr(lang, "back"),
                                     callback_data="menu:home")]]))
        return
    if len(available) == 1:
        return await _enter_download_mode(cb, state, c, available[0])

    rows = []
    if photo_enabled:
        rows.append([InlineKeyboardButton(
            text=tr(lang, "dl_btn_photo"), callback_data="dl:photo")])
    if video_enabled:
        rows.append([InlineKeyboardButton(
            text=tr(lang, "dl_btn_video"), callback_data="dl:video")])
    if music_enabled:
        rows.append([InlineKeyboardButton(
            text=tr(lang, "dl_btn_music"), callback_data="dl:music")])
    rows.append([InlineKeyboardButton(
        text=tr(lang, "back"), callback_data="menu:home")])

    await safe_edit(cb.message, tr(lang, "dl_choose_type"),
                    InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "dl:photo")
async def cb_dl_photo(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await _enter_download_mode(cb, state, c, "photo")


@router.callback_query(F.data == "dl:video")
async def cb_dl_video(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await _enter_download_mode(cb, state, c, "video")


@router.callback_query(F.data == "dl:music")
async def cb_dl_music(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await _enter_download_mode(cb, state, c, "music")


async def _enter_download_mode(cb: CallbackQuery, state: FSMContext,
                                c: Container, mode: str):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    if not await check_membership(user.user_id):
        await send_join_prompt(cb.message, lang)
        return
    await state.set_state(Flow.dl_waiting_url)
    await state.update_data(dl_mode=mode)

    if mode == "photo":
        text = tr(lang, "dl_photo_center")
    elif mode == "music":
        text = tr(lang, "dl_music_center")
    else:
        text = tr(lang, "dl_video_center")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "dl_back_to_types"),
                             callback_data="menu:download")]])
    await safe_edit(cb.message, text, kb)


@router.message(Flow.dl_waiting_url, F.text)
async def handle_url(message: Message, state: FSMContext, c: Container):
    u = message.from_user
    if not u:
        return
    user = UserRepo.get(u.id)
    if not user:
        return
    lang = user_lang(user)
    if not await check_membership(u.id):
        await send_join_prompt(message, lang)
        return
    data = await state.get_data()
    mode = data.get("dl_mode", "video")
    url = (message.text or "").strip()
    if not is_valid_url(url):
        await message.answer(tr(lang, "dl_invalid"))
        return

    cd_left = cooldown_remaining(u.id)
    if cd_left:
        await message.answer(tr(lang, "dl_cooldown", sec=cd_left))
        return

    max_concurrent = int(db_get("max_concurrent", "2"))
    if UserRepo.active_jobs(u.id) >= max_concurrent and not is_limit_exempt(u.id):
        await message.answer(tr(lang, "dl_concurrent", limit=max_concurrent))
        await state.clear()
        return

    if not is_limit_exempt(u.id):
        try:
            if mode == "photo":
                hl = int(db_get("max_photo_hour", "30"))
                dl = int(db_get("max_photo_day", "200"))
            elif mode == "music":
                hl = int(db_get("max_music_hour", "30"))
                dl = int(db_get("max_music_day", "200"))
            else:
                hl = int(db_get("max_dl_hour", "10"))
                dl = int(db_get("max_dl_day", "50"))
            RateRepo.check_and_consume(u.id, mode, hl, dl)
        except PermissionError as e:
            await message.answer(tr(lang, str(e)))
            await state.clear()
            return

    job = JobRepo.create(user_id=u.id, chat_id=message.chat.id, url=url,
                         status=STATUS_ANALYZING)
    UserRepo.bump(u.id, "downloads")
    await state.clear()

    if mode == "photo":
        notice = await message.answer(
            tr(lang, "dl_photo_downloading", id=job.job_id))
        try:
            result = await download_photo_only(url, job.job_id)
            delay = int(db_get("delete_delay", "60"))
            cap = tr(lang, "dl_photo_completed",
                     size=fmt_bytes(result.filesize),
                     id=job.job_id, delay=delay)
            sent = await _send_photo_with_compression(
                c.bot, message.chat.id, result.path, cap, job.job_id, lang)
            if sent is None:
                raise DownloadError("Failed to send image")
            with contextlib.suppress(Exception):
                await notice.delete()
            JobRepo.update(job.job_id, status=STATUS_COMPLETED, progress=100.0,
                           title="Image", filesize=result.filesize, duration=0,
                           file_path=str(result.path), msg_id=sent.message_id,
                           delete_at=now_ts() + delay, finished_at=now_ts())
            UserRepo.bump(u.id, "success_dl")
        except Exception as e:
            logging.warning(f"[photo] failed: {e}")
            JobRepo.update(job.job_id, status=STATUS_FAILED, error=str(e),
                           finished_at=now_ts())
            UserRepo.bump(u.id, "failed_dl")
            err_text = tr(lang, "dl_photo_failed",
                          error=esc(str(e))[:200], id=job.job_id)
            edited = False
            with contextlib.suppress(Exception):
                await notice.edit_text(err_text)
                edited = True
            if not edited:
                with contextlib.suppress(Exception):
                    await message.answer(err_text)
        if db_get("keep_state_after_download", "1") == "1":
            await state.set_state(Flow.dl_waiting_url)
            await state.update_data(dl_mode="photo")
        return

    if mode == "music":
        analyzing = await message.answer(
            f"{tr(lang, 'dl_music_analyzing', id=job.job_id)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=tr(lang, "cancel"),
                    callback_data=safe_cb(f"jback:{job.job_id}"))]]))
        JobRepo.update(job.job_id, msg_id=analyzing.message_id)

        info = None
        analyze_err = ""
        try:
            info = await analyze_async(url)
        except DownloadError as e:
            analyze_err = str(e)
        except Exception as e:
            analyze_err = str(e)
            logging.exception("music analyze crashed")

        if info is None:
            try:
                result = await download_music_only(url, job.job_id, "audio")
                with contextlib.suppress(Exception):
                    await analyzing.delete()
                delay = int(db_get("delete_delay", "60"))
                artist = result.artist or tr(lang, "artist_unknown")
                cap = tr(lang, "dl_music_completed",
                         title=esc(result.title[:80]),
                         artist=esc(artist[:60]),
                         size=fmt_bytes(result.filesize),
                         duration=fmt_duration(result.duration),
                         id=job.job_id, delay=delay)
                sent = await _send_music_file(c.bot, message.chat.id, result, cap)
                if sent is None:
                    raise DownloadError("Failed to send audio")
                JobRepo.update(job.job_id, status=STATUS_COMPLETED,
                               progress=100.0, title=result.title,
                               filesize=result.filesize, quality="audio",
                               duration=result.duration,
                               file_path=str(result.path),
                               msg_id=sent.message_id,
                               delete_at=now_ts() + delay,
                               finished_at=now_ts())
                UserRepo.bump(u.id, "success_dl")
            except Exception as e:
                JobRepo.update(job.job_id, status=STATUS_FAILED,
                               error=analyze_err or str(e),
                               finished_at=now_ts())
                UserRepo.bump(u.id, "failed_dl")
                with contextlib.suppress(Exception):
                    await analyzing.edit_text(
                        tr(lang, "dl_music_failed",
                           error=esc(analyze_err or str(e))[:200],
                           id=job.job_id),
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text=tr(lang, "back"),
                                                 callback_data="menu:home")]]))
            if db_get("keep_state_after_download", "1") == "1":
                await state.set_state(Flow.dl_waiting_url)
                await state.update_data(dl_mode="music")
            return

        current = JobRepo.get(job.job_id)
        if (is_cancelled(job.job_id) or not current
                or current.status == STATUS_CANCELLED):
            return
        JobRepo.update(job.job_id, title=info.title, duration=info.duration,
                       filesize=info.filesize, thumbnail=info.thumbnail,
                       status=STATUS_PENDING)
        with contextlib.suppress(Exception):
            await analyzing.delete()

        cap = (f"🎵 <b>{esc(info.title[:120])}</b>\n"
               f"⏱ {fmt_duration(info.duration)}\n"
               f"💾 {fmt_bytes(info.filesize)}\n")
        if info.uploader:
            cap += f"🎤 {esc(info.uploader[:80])}\n"
        cap += f"\n🎵 <code>{job.job_id}</code>"

        sent_p = False
        if db_get("send_thumbnail", "1") == "1" and info.thumbnail:
            try:
                await message.answer_photo(
                    photo=info.thumbnail, caption=cap[:1024])
                sent_p = True
            except Exception:
                pass
        if not sent_p:
            with contextlib.suppress(Exception):
                await message.answer(cap[:4096])

        q_msg = await message.answer(
            tr(lang, "dl_select_quality"),
            reply_markup=quality_kb(job.job_id, lang, mode="music"))
        JobRepo.update(job.job_id, msg_id=q_msg.message_id)
        return

    # VIDEO
    analyzing = await message.answer(
        f"{tr(lang, 'dl_analyzing')}\n\n🆔 <code>{job.job_id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=tr(lang, "cancel"),
                                 callback_data=safe_cb(f"jback:{job.job_id}"))]]))
    JobRepo.update(job.job_id, msg_id=analyzing.message_id)
    info = None
    analyze_err = ""
    try:
        info = await analyze_async(url)
    except DownloadError as e:
        analyze_err = str(e)
    except Exception as e:
        analyze_err = str(e)
        logging.exception("analyze crashed")

    if info is None:
        try:
            result = await download_video_only(url, job.job_id)
            with contextlib.suppress(Exception):
                await analyzing.delete()
            delay = int(db_get("delete_delay", "60"))
            dur = result.duration or 0
            if dur <= 0:
                dur = await asyncio.to_thread(
                    _probe_duration, result.path) or 0
            size = result.filesize
            try:
                mx = int(db_get("max_file_size_mb", "2048"))
            except (TypeError, ValueError):
                mx = 2048
            if size > mx * 1024 * 1024:
                raise DownloadError("File too large")
            cap = tr(lang, "dl_completed",
                     title=esc(result.title[:80]), quality="best",
                     size=fmt_bytes(size), duration=fmt_duration(dur),
                     id=job.job_id, delay=delay)
            sent = None
            with contextlib.suppress(Exception):
                sent = await c.bot.send_video(
                    chat_id=message.chat.id,
                    video=FSInputFile(str(result.path)),
                    caption=cap[:1024], supports_streaming=True,
                    duration=dur, request_timeout=1800)
            if sent is None:
                sent = await c.bot.send_document(
                    chat_id=message.chat.id,
                    document=FSInputFile(str(result.path)),
                    caption=cap[:1024], request_timeout=1800)
            JobRepo.update(job.job_id, status=STATUS_COMPLETED, progress=100.0,
                           title=result.title, filesize=size, duration=dur,
                           file_path=str(result.path), msg_id=sent.message_id,
                           delete_at=now_ts() + delay, finished_at=now_ts())
            UserRepo.bump(u.id, "success_dl")
            if db_get("keep_state_after_download", "1") == "1":
                await state.set_state(Flow.dl_waiting_url)
                await state.update_data(dl_mode="video")
            return
        except Exception as e:
            JobRepo.update(job.job_id, status=STATUS_FAILED,
                           error=analyze_err or str(e),
                           finished_at=now_ts())
            UserRepo.bump(u.id, "failed_dl")
            with contextlib.suppress(Exception):
                await analyzing.edit_text(
                    tr(lang, "dl_analyze_failed"),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=tr(lang, "back"),
                                             callback_data="menu:home")]]))
            return

    current = JobRepo.get(job.job_id)
    if (is_cancelled(job.job_id) or not current
            or current.status == STATUS_CANCELLED):
        return
    JobRepo.update(job.job_id, title=info.title, duration=info.duration,
                   filesize=info.filesize, thumbnail=info.thumbnail,
                   status=STATUS_PENDING)
    with contextlib.suppress(Exception):
        await analyzing.delete()

    cap = (f"<b>{esc(info.title[:120])}</b>\n"
           f"⏱ {fmt_duration(info.duration)}\n"
           f"💾 {fmt_bytes(info.filesize)}\n")
    if getattr(info, "max_height", 0) > 0:
        cap += tr(lang, "max_height_label", max=info.max_height) + "\n"
    if info.uploader:
        cap += f"👤 {esc(info.uploader[:80])}\n"
    cap += f"\n🆔 <code>{job.job_id}</code>"
    preview_sent = False
    if db_get("send_thumbnail", "1") == "1" and info.thumbnail:
        try:
            await message.answer_photo(photo=info.thumbnail, caption=cap[:1024])
            preview_sent = True
        except Exception:
            pass
    if not preview_sent:
        with contextlib.suppress(Exception):
            await message.answer(cap[:4096])
    if not allowed_qualities():
        await message.answer(tr(lang, "dl_no_quality"))
        JobRepo.update(job.job_id, status=STATUS_FAILED,
                       error="no_quality", finished_at=now_ts())
        return

    avail = getattr(info, "available_qualities", None) or {"best", "audio"}
    max_h = getattr(info, "max_height", 0)
    quality_hint = ""
    if max_h > 0:
        quality_hint = tr(lang, "qualities_available_hint", max=max_h)

    q_msg = await message.answer(
        tr(lang, "dl_select_quality") + quality_hint,
        reply_markup=quality_kb(job.job_id, lang, available=avail,
                                 mode="video"))
    JobRepo.update(job.job_id, msg_id=q_msg.message_id)


@router.callback_query(F.data.startswith("q:"))
async def cb_quality(cb: CallbackQuery, c: Container):
    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    _, job_id, quality = parts
    if quality not in VIDEO_QUALITIES:
        await cb.answer()
        return
    job = JobRepo.get(job_id)
    if not job or job.user_id != cb.from_user.id:
        await cb.answer("⛔", show_alert=True)
        return
    if job.status in (STATUS_CANCELLED, STATUS_COMPLETED):
        await cb.answer("⚠️", show_alert=True)
        return
    if quality not in allowed_qualities():
        await cb.answer("Not enabled", show_alert=True)
        return
    await cb.answer()
    clear_cancelled(job_id)
    JobRepo.update(job_id, quality=quality, status=STATUS_QUEUED, error=None)
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(quality, quality)
    await safe_edit(cb.message, tr(lang, "dl_queued", quality=esc(qn), id=job_id))
    await c.job_queue.put(job_id)


@router.callback_query(F.data.startswith("mq:"))
async def cb_music_quality(cb: CallbackQuery, c: Container):
    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    _, job_id, quality = parts
    if not is_audio_quality(quality):
        await cb.answer()
        return
    job = JobRepo.get(job_id)
    if not job or job.user_id != cb.from_user.id:
        await cb.answer("⛔", show_alert=True)
        return
    if job.status in (STATUS_CANCELLED, STATUS_COMPLETED):
        await cb.answer("⚠️", show_alert=True)
        return
    if quality not in allowed_qualities():
        await cb.answer("Not enabled", show_alert=True)
        return
    await cb.answer()
    clear_cancelled(job_id)
    JobRepo.update(job_id, quality=quality, status=STATUS_QUEUED, error=None)
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(quality, quality)
    await safe_edit(cb.message,
                    tr(lang, "dl_queued", quality=esc(qn), id=job_id))
    await c.job_queue.put(job_id)


@router.callback_query(F.data.startswith("jcancel:"))
async def cb_job_cancel(cb: CallbackQuery, c: Container):
    job_id = cb.data.split(":", 1)[1]
    job = JobRepo.get(job_id)
    if not job or job.user_id != cb.from_user.id:
        await cb.answer("⛔", show_alert=True)
        return
    await cb.answer()
    mark_cancelled(job_id)
    JobRepo.update(job_id, status=STATUS_CANCELLED, finished_at=now_ts())
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    await safe_edit(cb.message, tr(lang, "dl_cancelled"))


@router.callback_query(F.data.startswith("jback:"))
async def cb_job_back(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await state.clear()
    job_id = cb.data.split(":", 1)[1]
    job = JobRepo.get(job_id)
    if job and job.user_id == cb.from_user.id and job.status in (
            STATUS_QUEUED, STATUS_ANALYZING, STATUS_PENDING):
        mark_cancelled(job_id)
        JobRepo.update(job_id, status=STATUS_CANCELLED, finished_at=now_ts())
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    await send_home(cb, user, edit=True)


# ══════════════════════════════════════════════════════════════
# HISTORY
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:history")
async def cb_history(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await state.clear()
    await show_history(cb, 1)


@router.callback_query(F.data.startswith("histpg:"))
async def cb_history_page(cb: CallbackQuery, c: Container):
    await cb.answer()
    try:
        page = int(cb.data.split(":", 1)[1])
    except ValueError:
        page = 1
    await show_history(cb, page)


async def show_history(cb: CallbackQuery, page: int = 1):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    per = 10
    page = max(1, page)
    total = JobRepo.count_for_user(user.user_id)
    total_pages = max(1, (total + per - 1) // per)
    jobs = JobRepo.history(user.user_id, limit=per, offset=(page - 1) * per)
    if not jobs:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=tr(lang, "back"),
                                 callback_data="menu:home")]])
        await safe_edit(cb.message, tr(lang, "hist_empty"), kb)
        return
    text = tr(lang, "hist_page_title", page=page, total=total_pages)
    buttons = []
    for j in jobs:
        icon = {"completed": "✅", "failed": "❌", "cancelled": "⚪",
                "downloading": "⬇️", "uploading": "⬆️",
                "queued": "⏳", "analyzing": "🔍"}.get(j.status, "⚙️")
        fav_mark = "⭐ " if FavRepo.is_fav(user.user_id, j.job_id) else ""
        title = (j.title or j.job_id)[:26]
        size_str = fmt_bytes(_effective_filesize(j))
        dur = _effective_duration(j)
        dur_str = fmt_duration(dur) if dur else "—"
        buttons.append([InlineKeyboardButton(
            text=f"{fav_mark}{icon} {title}\n💾 {size_str} | ⏱ {dur_str}",
            callback_data=safe_cb(f"histview:{j.job_id}"))])
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"histpg:{page - 1}"))
    nav.button(text=f"📄 {page} / {total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"histpg:{page + 1}"))
    nav.adjust(3)
    kb_rows = buttons + nav.export()
    kb_rows.append([InlineKeyboardButton(
        text=tr(lang, "hist_clear_btn"),
        callback_data="histclearask")])
    kb_rows.append([InlineKeyboardButton(text=tr(lang, "back"),
                                          callback_data="menu:home")])
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("histview:"))
async def cb_history_view(cb: CallbackQuery, c: Container):
    with contextlib.suppress(Exception):
        await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    j = JobRepo.get(jid)
    if not j or j.user_id != user.user_id:
        with contextlib.suppress(Exception):
            await cb.answer("⛔", show_alert=True)
        return
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(
        j.quality, j.quality)
    icon = {"completed": "✅", "failed": "❌", "cancelled": "⚪",
            "downloading": "⬇️", "uploading": "⬆️",
            "queued": "⏳", "analyzing": "🔍"}.get(j.status, "⚙️")
    size = _effective_filesize(j)
    duration = _effective_duration(j)
    file_exists = bool(j.file_path and Path(j.file_path).exists())
    text = tr(lang, "hist_item_detail",
              title=esc((j.title or "-")[:80]), id=j.job_id,
              quality=esc(qn), status=f"{icon} {esc(j.status)}",
              size=fmt_bytes(size), duration=fmt_duration(duration),
              date=fmt_time(j.started_at or j.created_at or now_ts()))
    buttons = []
    if file_exists:
        buttons.append([InlineKeyboardButton(
            text=tr(lang, "resend"),
            callback_data=safe_cb(f"sendfile:{jid}"))])
    is_fav = FavRepo.is_fav(user.user_id, jid)
    fav_btn_text = (tr(lang, "fav_remove_btn") if is_fav
                    else tr(lang, "fav_add_btn"))
    fav_cb = f"histunfav:{jid}" if is_fav else f"histfav:{jid}"
    buttons.append([InlineKeyboardButton(
        text=fav_btn_text, callback_data=safe_cb(fav_cb))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "btn_redo"),
        callback_data=safe_cb(f"redl:{jid}"))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "hist_delete_btn"),
        callback_data=safe_cb(f"histdel:{jid}"))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "back_to_history"),
        callback_data="menu:history")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
        return
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "not modified" in s:
            return
        if "no text" in s or "caption" in s:
            with contextlib.suppress(Exception):
                await cb.message.edit_caption(caption=text[:1024], reply_markup=kb)
                return
    except Exception:
        pass
    with contextlib.suppress(Exception):
        await cb.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("sendfile:"))
async def cb_sendfile(cb: CallbackQuery, c: Container):
    jid = cb.data.split(":", 1)[1]
    j = JobRepo.get(jid)
    if not j or j.user_id != cb.from_user.id:
        await cb.answer("⛔", show_alert=True)
        return
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    if not j.file_path or not Path(j.file_path).exists():
        await cb.answer("⚠️", show_alert=True)
        return
    await cb.answer("📤...")
    path = Path(j.file_path)
    size = path.stat().st_size
    duration_final = _effective_duration(j)
    if duration_final <= 0:
        duration_final = await asyncio.to_thread(_probe_duration, path) or 0
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(
        j.quality, j.quality)
    delay = int(db_get("delete_delay", "60"))
    caption = tr(lang, "dl_completed",
                 title=esc((j.title or "Video")[:120]), quality=esc(qn),
                 size=fmt_bytes(size), duration=fmt_duration(duration_final),
                 id=j.job_id, delay=delay)
    is_audio = is_audio_quality(j.quality) or \
        path.suffix.lower() in (".mp3", ".m4a", ".opus",
                                ".ogg", ".flac", ".wav", ".aac")
    if is_image_file(path):
        cap_p = tr(lang, "dl_photo_completed", size=fmt_bytes(size),
                   id=j.job_id, delay=delay)
        with contextlib.suppress(Exception):
            await _send_photo_with_compression(
                c.bot, cb.message.chat.id, path, cap_p, j.job_id, lang)
        return
    try:
        if is_audio:
            await c.bot.send_audio(
                chat_id=cb.message.chat.id, audio=FSInputFile(str(path)),
                caption=caption[:1024], title=(j.title or "Audio")[:60],
                duration=duration_final, request_timeout=1800)
        else:
            await c.bot.send_video(
                chat_id=cb.message.chat.id, video=FSInputFile(str(path)),
                caption=caption[:1024], supports_streaming=True,
                duration=duration_final, request_timeout=1800)
    except Exception as e:
        with contextlib.suppress(Exception):
            await cb.message.answer(f"❌ {esc(str(e))}")


@router.callback_query(F.data.startswith("histfav:"))
async def cb_hist_add_fav(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    j = JobRepo.get(jid)
    if not j or j.user_id != user.user_id:
        await cb.answer("⛔", show_alert=True)
        return
    if FavRepo.is_fav(user.user_id, jid):
        await cb.answer(tr(lang, "fav_already"), show_alert=True)
        return
    FavRepo.add(user.user_id, jid)
    await cb.answer(tr(lang, "fav_add_ok"), show_alert=True)
    await cb_history_view(cb, c)


@router.callback_query(F.data.startswith("histunfav:"))
async def cb_hist_del_fav(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    if not FavRepo.is_fav(user.user_id, jid):
        await cb.answer(tr(lang, "fav_not_in"), show_alert=True)
        return
    FavRepo.remove(user.user_id, jid)
    await cb.answer(tr(lang, "fav_remove_ok"), show_alert=True)
    await cb_history_view(cb, c)


@router.callback_query(F.data.startswith("histdel:"))
async def cb_hist_delete(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    j = JobRepo.get(jid)
    if not j or j.user_id != user.user_id:
        await cb.answer("⛔", show_alert=True)
        return
    FavRepo.remove(user.user_id, jid)
    _purge_job_files(get_conn().execute(
        "SELECT job_id, file_path FROM jobs WHERE job_id=? AND user_id=? "
        "AND status NOT IN ('queued','analyzing','downloading','uploading')",
        (jid, user.user_id)).fetchall())
    get_conn().execute("DELETE FROM jobs WHERE job_id=? AND user_id=?",
                       (jid, user.user_id))
    await cb.answer(tr(lang, "hist_delete_ok"), show_alert=True)
    await show_history(cb, 1)


@router.callback_query(F.data == "histclearask")
async def cb_hist_clear_ask(cb: CallbackQuery, c: Container):
    await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "yes"),
                              callback_data="histclearyes")],
        [InlineKeyboardButton(text=tr(lang, "no"),
                              callback_data="menu:history")]])
    await safe_edit(cb.message, tr(lang, "hist_clear_confirm"), kb)


@router.callback_query(F.data == "histclearyes")
async def cb_hist_clear_yes(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    r = get_conn().execute("SELECT COUNT(*) AS c FROM jobs WHERE user_id=?",
                            (user.user_id,)).fetchone()
    count = int(r["c"] or 0)
    _purge_job_files(get_conn().execute(
        "SELECT job_id, file_path FROM jobs WHERE user_id=? "
        "AND status NOT IN ('queued','analyzing','downloading','uploading')",
        (user.user_id,)).fetchall())
    get_conn().execute("DELETE FROM jobs WHERE user_id=?", (user.user_id,))
    get_conn().execute("DELETE FROM favorites WHERE user_id=?",
                       (user.user_id,))
    await cb.answer(tr(lang, "hist_cleared", count=count), show_alert=True)
    await show_history(cb, 1)


# ══════════════════════════════════════════════════════════════
# RE-DOWNLOAD
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("redl:"))
async def cb_redownload(cb: CallbackQuery, c: Container):
    job_id = cb.data.split(":", 1)[1]
    old = JobRepo.get(job_id)
    if not old or old.user_id != cb.from_user.id:
        await cb.answer("⛔", show_alert=True)
        return
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)

    is_photo_mode = False
    if old.file_path:
        with contextlib.suppress(Exception):
            suf = Path(old.file_path).suffix.lower()
            if suf in IMAGE_EXTS:
                is_photo_mode = True
    if old.title in ("Image", "Thumbnail"):
        is_photo_mode = True
    if is_direct_image_url(old.url):
        is_photo_mode = True
    is_music_mode = (not is_photo_mode and is_audio_quality(old.quality))

    if not is_limit_exempt(cb.from_user.id):
        mc = int(db_get("max_concurrent", "2"))
        if UserRepo.active_jobs(cb.from_user.id) >= mc:
            await cb.answer(tr(lang, "dl_concurrent", limit=mc),
                            show_alert=True)
            return
        try:
            if is_photo_mode:
                RateRepo.check_and_consume(cb.from_user.id, "photo",
                    int(db_get("max_photo_hour", "30")),
                    int(db_get("max_photo_day", "200")))
            elif is_music_mode:
                RateRepo.check_and_consume(cb.from_user.id, "music",
                    int(db_get("max_music_hour", "30")),
                    int(db_get("max_music_day", "200")))
            else:
                RateRepo.check_and_consume(cb.from_user.id, "video",
                    int(db_get("max_dl_hour", "10")),
                    int(db_get("max_dl_day", "50")))
        except PermissionError as e:
            await cb.answer(tr(lang, str(e)), show_alert=True)
            return

    target_chat = cb.message.chat.id if cb.message else old.chat_id
    new_job = JobRepo.create(user_id=old.user_id, chat_id=target_chat,
                              url=old.url, status=STATUS_ANALYZING)
    clear_cancelled(new_job.job_id)
    UserRepo.bump(cb.from_user.id, "downloads")
    await cb.answer("✅")

    if is_photo_mode:
        try:
            notice = await c.bot.send_message(
                target_chat, tr(lang, "dl_photo_downloading", id=new_job.job_id))
        except Exception:
            return
        try:
            result = await download_photo_only(old.url, new_job.job_id)
            delay = int(db_get("delete_delay", "60"))
            cap = tr(lang, "dl_photo_completed",
                     size=fmt_bytes(result.filesize),
                     id=new_job.job_id, delay=delay)
            sent = await _send_photo_with_compression(
                c.bot, target_chat, result.path, cap, new_job.job_id, lang)
            if sent is None:
                raise DownloadError("Failed to send image")
            with contextlib.suppress(Exception):
                await notice.delete()
            JobRepo.update(new_job.job_id, status=STATUS_COMPLETED,
                           progress=100.0, title="Image",
                           filesize=result.filesize, duration=0,
                           file_path=str(result.path), msg_id=sent.message_id,
                           delete_at=now_ts() + delay, finished_at=now_ts())
            UserRepo.bump(old.user_id, "success_dl")
        except Exception as e:
            JobRepo.update(new_job.job_id, status=STATUS_FAILED, error=str(e),
                           finished_at=now_ts())
            UserRepo.bump(old.user_id, "failed_dl")
            err_text = tr(lang, "dl_photo_failed",
                          error=esc(str(e))[:200], id=new_job.job_id)
            with contextlib.suppress(Exception):
                await notice.edit_text(err_text)
        return

    if is_music_mode:
        try:
            notice = await c.bot.send_message(
                target_chat,
                tr(lang, "dl_music_analyzing", id=new_job.job_id))
        except Exception:
            return
        try:
            info = await analyze_async(old.url)
            JobRepo.update(new_job.job_id, title=info.title,
                           duration=info.duration, filesize=info.filesize,
                           thumbnail=info.thumbnail, status=STATUS_PENDING)
            with contextlib.suppress(Exception):
                await notice.delete()
            cap = (f"🎵 <b>{esc(info.title[:120])}</b>\n"
                   f"⏱ {fmt_duration(info.duration)}\n"
                   f"💾 {fmt_bytes(info.filesize)}\n")
            if info.uploader:
                cap += f"🎤 {esc(info.uploader[:80])}\n"
            cap += f"\n🎵 <code>{new_job.job_id}</code>"
            sp = False
            if db_get("send_thumbnail", "1") == "1" and info.thumbnail:
                try:
                    await c.bot.send_photo(chat_id=target_chat,
                                            photo=info.thumbnail,
                                            caption=cap[:1024])
                    sp = True
                except Exception:
                    pass
            if not sp:
                with contextlib.suppress(Exception):
                    await c.bot.send_message(target_chat, cap[:4096])
            q_msg = await c.bot.send_message(
                target_chat, tr(lang, "dl_select_quality"),
                reply_markup=quality_kb(new_job.job_id, lang, mode="music"))
            JobRepo.update(new_job.job_id, msg_id=q_msg.message_id)
        except DownloadError as e:
            JobRepo.update(new_job.job_id, status=STATUS_FAILED,
                           error=str(e), finished_at=now_ts())
            UserRepo.bump(old.user_id, "failed_dl")
            with contextlib.suppress(Exception):
                await notice.edit_text(
                    tr(lang, "dl_music_failed",
                       error=esc(str(e))[:200], id=new_job.job_id))
        return

    try:
        msg = await c.bot.send_message(
            target_chat,
            f"{tr(lang, 'dl_analyzing')}\n\n🆔 <code>{new_job.job_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=tr(lang, "cancel"),
                    callback_data=safe_cb(f"jback:{new_job.job_id}"))]]))
    except Exception:
        return
    JobRepo.update(new_job.job_id, msg_id=msg.message_id,
                   status=STATUS_ANALYZING)
    try:
        info = await analyze_async(old.url)
    except DownloadError as e:
        JobRepo.update(new_job.job_id, status=STATUS_FAILED, error=str(e),
                       finished_at=now_ts())
        UserRepo.bump(cb.from_user.id, "failed_dl")
        with contextlib.suppress(Exception):
            await msg.edit_text(tr(lang, "dl_analyze_failed"))
        return
    JobRepo.update(new_job.job_id, title=info.title, duration=info.duration,
                   filesize=info.filesize, thumbnail=info.thumbnail,
                   status=STATUS_PENDING)
    with contextlib.suppress(Exception):
        await msg.delete()
    cap = (f"<b>{esc(info.title[:120])}</b>\n"
           f"⏱ {fmt_duration(info.duration)}\n"
           f"💾 {fmt_bytes(info.filesize)}\n")
    if getattr(info, "max_height", 0) > 0:
        cap += tr(lang, "max_height_label", max=info.max_height) + "\n"
    if info.uploader:
        cap += f"👤 {esc(info.uploader[:80])}\n"
    cap += f"\n🆔 <code>{new_job.job_id}</code>"
    ps = False
    if db_get("send_thumbnail", "1") == "1" and info.thumbnail:
        try:
            await c.bot.send_photo(chat_id=target_chat, photo=info.thumbnail,
                                    caption=cap[:1024])
            ps = True
        except Exception:
            pass
    if not ps:
        with contextlib.suppress(Exception):
            await c.bot.send_message(target_chat, cap[:4096])
    if not allowed_qualities():
        JobRepo.update(new_job.job_id, status=STATUS_FAILED,
                       error="no_quality", finished_at=now_ts())
        with contextlib.suppress(Exception):
            await c.bot.send_message(target_chat, tr(lang, "dl_no_quality"))
        return

    avail = getattr(info, "available_qualities", None) or {"best", "audio"}
    q_msg = await c.bot.send_message(
        target_chat, tr(lang, "dl_select_quality"),
        reply_markup=quality_kb(new_job.job_id, lang, available=avail,
                                 mode="video"))
    JobRepo.update(new_job.job_id, msg_id=q_msg.message_id)


# ══════════════════════════════════════════════════════════════
# FAVORITES
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:favs")
async def cb_favs(cb: CallbackQuery, c: Container):
    await cb.answer()
    await show_favs(cb, 1)


@router.callback_query(F.data.startswith("favpg:"))
async def cb_favs_page(cb: CallbackQuery, c: Container):
    await cb.answer()
    try:
        page = int(cb.data.split(":", 1)[1])
    except ValueError:
        page = 1
    await show_favs(cb, page)


async def show_favs(cb: CallbackQuery, page: int = 1):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    per = 10
    page = max(1, page)
    total = FavRepo.count(user.user_id)
    total_pages = max(1, (total + per - 1) // per)
    jobs = FavRepo.list(user.user_id, limit=per, offset=(page - 1) * per)
    if not jobs:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=tr(lang, "back"),
                                 callback_data="menu:home")]])
        await safe_edit(cb.message, tr(lang, "fav_empty_new"), kb)
        return
    text = tr(lang, "fav_page_title", count=total) + \
           f"  — 📄 {page}/{total_pages}\n\n"
    buttons = []
    for j in jobs:
        icon = {"completed": "✅", "failed": "❌", "cancelled": "⚪",
                "downloading": "⬇️", "uploading": "⬆️",
                "queued": "⏳", "analyzing": "🔍"}.get(j.status, "⚙️")
        title = (j.title or j.job_id)[:22]
        size_str = fmt_bytes(_effective_filesize(j))
        dur = _effective_duration(j)
        dur_str = fmt_duration(dur) if dur else "—"
        text += f"⭐ {icon} <b>{title}</b>  💾 {size_str}  ⏱ {dur_str}\n"
        buttons.append([InlineKeyboardButton(
            text=f"⭐ {icon} {title[:18]}\n💾 {size_str} | ⏱ {dur_str}",
            callback_data=safe_cb(f"favview:{j.job_id}"))])
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"favpg:{page - 1}"))
    nav.button(text=f"📄 {page} / {total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"favpg:{page + 1}"))
    nav.adjust(3)
    kb_rows = buttons + nav.export()
    kb_rows.append([InlineKeyboardButton(text=tr(lang, "back"),
                                          callback_data="menu:home")])
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("favview:"))
async def cb_fav_view(cb: CallbackQuery, c: Container):
    with contextlib.suppress(Exception):
        await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    j = JobRepo.get(jid)
    if not j or not FavRepo.is_fav(user.user_id, jid):
        with contextlib.suppress(Exception):
            await cb.answer("⛔", show_alert=True)
        return
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(
        j.quality, j.quality)
    icon = {"completed": "✅", "failed": "❌", "cancelled": "⚪",
            "downloading": "⬇️", "uploading": "⬆️",
            "queued": "⏳", "analyzing": "🔍"}.get(j.status, "⚙️")
    size = _effective_filesize(j)
    duration = _effective_duration(j)
    text = tr(lang, "hist_item_detail",
              title=esc((j.title or "-")[:80]), id=j.job_id,
              quality=esc(qn), status=f"{icon} {esc(j.status)}",
              size=fmt_bytes(size), duration=fmt_duration(duration),
              date=fmt_time(j.started_at or j.created_at or now_ts()))
    buttons = []
    if j.file_path and Path(j.file_path).exists():
        buttons.append([InlineKeyboardButton(
            text=tr(lang, "resend"),
            callback_data=safe_cb(f"sendfile:{jid}"))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "fav_remove_btn"),
        callback_data=safe_cb(f"favrm:{jid}"))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "btn_redo"),
        callback_data=safe_cb(f"redl:{jid}"))])
    buttons.append([InlineKeyboardButton(
        text=tr(lang, "back_to_favs"),
        callback_data="menu:favs")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
        return
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "not modified" in s:
            return
        if "no text" in s or "caption" in s:
            with contextlib.suppress(Exception):
                await cb.message.edit_caption(caption=text[:1024], reply_markup=kb)
                return
    except Exception:
        pass
    with contextlib.suppress(Exception):
        await cb.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("favrm:"))
async def cb_fav_remove(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    jid = cb.data.split(":", 1)[1]
    if not FavRepo.is_fav(user.user_id, jid):
        await cb.answer(tr(lang, "fav_not_in"), show_alert=True)
        return
    FavRepo.remove(user.user_id, jid)
    await cb.answer(tr(lang, "fav_remove_ok"), show_alert=True)
    await show_favs(cb, 1)


# ══════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:stats")
async def cb_stats(cb: CallbackQuery, c: Container):
    await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    active = UserRepo.active_jobs(user.user_id)
    tier = tr(lang, "tier_vip") if user.is_vip else tr(lang, "tier_normal")
    text = tr(lang, "stats_title",
              name=esc(user.first_name or "User"), uid=user.user_id,
              total=user.downloads, success=user.success_dl,
              failed=user.failed_dl, active=active, tier=tier)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"), callback_data="menu:home")]])
    await safe_edit(cb.message, text, kb)


# ══════════════════════════════════════════════════════════════
# SUPPORT
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:support")
async def cb_support(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    await state.clear()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "support_new"),
                              callback_data="support:new")],
        [InlineKeyboardButton(text=tr(lang, "support_my"),
                              callback_data="support:my")],
        [InlineKeyboardButton(text=tr(lang, "back"),
                              callback_data="menu:home")]])
    await safe_edit(cb.message, tr(lang, "support_menu_title"), kb)


@router.callback_query(F.data == "support:new")
async def cb_support_new(cb: CallbackQuery, state: FSMContext, c: Container):
    await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    await state.set_state(Flow.support_message)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"),
                             callback_data="menu:support")]])
    await safe_edit(cb.message, tr(lang, "support_title"), kb)


@router.callback_query(F.data == "support:my")
async def cb_support_my(cb: CallbackQuery, c: Container):
    await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    rows = TicketRepo.by_user(user.user_id, limit=10)
    if not rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=tr(lang, "back"),
                                 callback_data="menu:support")]])
        await safe_edit(cb.message, tr(lang, "my_tickets_empty"), kb)
        return
    text = tr(lang, "my_tickets_title") + "\n\n"
    buttons = []
    for tk in rows:
        icon = {"open": "🟢", "answered": "🟡", "closed": "🔴"}.get(
            tk["status"], "⚪")
        preview = esc((tk["message"] or "")[:30])
        text += f"{icon} <b>#{tk['ticket_id']}</b> — {preview}\n"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} #{tk['ticket_id']}",
            callback_data=safe_cb(f"mytk:{tk['ticket_id']}"))])
    buttons.append([InlineKeyboardButton(text=tr(lang, "back"),
                                          callback_data="menu:support")])
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("mytk:"))
async def cb_my_ticket_view(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    if not user:
        await cb.answer()
        return
    lang = user_lang(user)
    try:
        tid = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    tk = TicketRepo.get(tid)
    if not tk or int(tk["user_id"]) != user.user_id:
        await cb.answer("⛔", show_alert=True)
        return
    await cb.answer()
    status_map = {"open": tr(lang, "ticket_status_open"),
                  "answered": tr(lang, "ticket_status_answered"),
                  "closed": tr(lang, "ticket_status_closed")}
    status = status_map.get(tk["status"], tk["status"])
    text = tr(lang, "ticket_detail_user", id=tk["ticket_id"], status=status,
              date=fmt_time(tk["created_at"]), msg=esc(tk["message"] or ""))
    if tk["answer"]:
        text += (f"\n\n{tr(lang, 'ticket_reply_label')}\n"
                 f"{esc(tk['answer'])}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"),
                             callback_data="support:my")]])
    await safe_edit(cb.message, text, kb)


@router.message(Flow.support_message, F.text)
async def msg_support(message: Message, state: FSMContext, c: Container):
    user = UserRepo.get(message.from_user.id)
    if not user:
        await state.clear()
        return
    lang = user_lang(user)
    text = (message.text or "").strip()
    if not text:
        await message.answer(tr(lang, "empty"))
        return
    await state.clear()
    tid = TicketRepo.create(user.user_id, text)
    await message.answer(tr(lang, "support_sent", id=tid))
    with contextlib.suppress(Exception):
        owner = UserRepo.get(OWNER_IDS[0]) if OWNER_IDS else None
        owner_lang = user_lang(owner) if owner else "fa"
        text_owner = tr(owner_lang, "ticket_admin_notify", id=tid,
                        uid=user.user_id, name=esc(user.first_name or "User"),
                        msg=esc(text[:3000]))
        await c.bot.send_message(
            OWNER_IDS[0], text_owner,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=tr(owner_lang, "ticket_view_btn"),
                    callback_data=safe_cb(f"ticket:view:{tid}"))]]))


# ══════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:help")
async def cb_help(cb: CallbackQuery, c: Container):
    await cb.answer()
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    custom = db_get(f"guide_{lang}", "") or db_get("custom_text_help_text", "")
    text = custom if custom else tr(lang, "help_text")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"), callback_data="menu:home")]])
    await safe_edit(cb.message, text, kb)


# ══════════════════════════════════════════════════════════════
# ADMIN HELPERS
# ══════════════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    if uid in OWNER_IDS:
        return True
    try:
        r = get_conn().execute(
            "SELECT 1 FROM extra_admins WHERE user_id=?", (uid,)).fetchone()
        return bool(r)
    except Exception:
        return False


async def require_admin(cb: CallbackQuery) -> bool:
    if not is_admin(cb.from_user.id):
        with contextlib.suppress(Exception):
            await cb.answer("⛔", show_alert=True)
        return False
    return True


async def _admin_lang(c, uid: int) -> str:
    user = UserRepo.get(uid)
    return user_lang(user)


def _restart_process(current_file):
    with contextlib.suppress(Exception):
        close_conn()
    try:
        sys.stdout.flush()
        os.execv(sys.executable,
                 [sys.executable, str(current_file)] + sys.argv[1:])
    except Exception:
        os._exit(0)


# ══════════════════════════════════════════════════════════════
# ADMIN — MAIN
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:home")
async def cb_admin_home(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    await safe_edit(cb.message, tr(lang, "ad_title"), admin_menu(lang))


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    us = UserRepo.stats()
    js = JobRepo.totals()
    active = JobRepo.count_active()
    try:
        db_size = fmt_bytes(DB_PATH.stat().st_size)
    except Exception:
        db_size = "—"
    text = tr(lang, "ad_rs_title", users=us["total"], vip=us["vip"],
              blocked=us["blocked"], total=js["total"],
              success=js["completed"], failed=js["failed"], active=active,
              tickets=TicketRepo.open_count(), db_size=db_size)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "refresh"),
                              callback_data="admin:stats")],
        [InlineKeyboardButton(text=tr(lang, "ad_back"),
                              callback_data="admin:home")]])
    await safe_edit(cb.message, text, kb)


# ══════════════════════════════════════════════════════════════
# ADMIN — DL TYPES
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:dl_types")
async def cb_admin_dl_types(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    photo_on = db_get("photo_download_enabled", "1") == "1"
    video_on = db_get("video_download_enabled", "1") == "1"
    music_on = db_get("music_download_enabled", "1") == "1"

    text = tr(lang, "ad_dlt_title",
              photo="✅" if photo_on else "❌",
              video="✅" if video_on else "❌",
              music="✅" if music_on else "❌")

    photo_lbl = tr(lang, "dl_btn_photo").replace("🖼", "").strip()
    video_lbl = tr(lang, "dl_btn_video").replace("🎬", "").strip()
    music_lbl = tr(lang, "dl_btn_music").replace("🎵", "").strip()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🖼 {'✅' if photo_on else '❌'} {photo_lbl}",
            callback_data="dlt:photo")],
        [InlineKeyboardButton(
            text=f"🎬 {'✅' if video_on else '❌'} {video_lbl}",
            callback_data="dlt:video")],
        [InlineKeyboardButton(
            text=f"🎵 {'✅' if music_on else '❌'} {music_lbl}",
            callback_data="dlt:music")],
        [InlineKeyboardButton(text=tr(lang, "ad_back"),
                              callback_data="admin:home")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data == "dlt:photo")
async def cb_dlt_photo(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("photo_download_enabled", "1")
    db_set("photo_download_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await cb_admin_dl_types(cb, c)


@router.callback_query(F.data == "dlt:video")
async def cb_dlt_video(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("video_download_enabled", "1")
    db_set("video_download_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await cb_admin_dl_types(cb, c)


@router.callback_query(F.data == "dlt:music")
async def cb_dlt_music(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("music_download_enabled", "1")
    db_set("music_download_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await cb_admin_dl_types(cb, c)


# ══════════════════════════════════════════════════════════════
# ADMIN — USERS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:users")
async def cb_admin_users(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_u_search"),
                             callback_data="users:search"),
        InlineKeyboardButton(text=tr(lang, "ad_u_recent"),
                             callback_data="users:recent:1"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_u_vip"),
                                callback_data="users:vip:1"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, tr(lang, "ad_u_title"), b.as_markup())


async def _render_users_list(cb, c, mode, page):
    lang = await _admin_lang(c, cb.from_user.id)
    per = 10
    page = max(1, page)
    if mode == "vip":
        total = UserRepo.count_vip()
        users = UserRepo.list_vip(limit=per, offset=(page - 1) * per)
        header = tr(lang, "ad_u_vip_title")
    else:
        total = UserRepo.count_all()
        users = UserRepo.list_recent(limit=per, offset=(page - 1) * per)
        header = tr(lang, "ad_u_recent_title")
    total_pages = max(1, (total + per - 1) // per)
    header += f"  — 📄 {page}/{total_pages}  ({total})"
    b = InlineKeyboardBuilder()
    for u in users:
        icon = "🚫" if u.is_blocked else ("💎" if u.is_vip else "👤")
        name = u.username or u.first_name or str(u.user_id)
        b.row(InlineKeyboardButton(
            text=f"{icon} {name[:35]}",
            callback_data=safe_cb(f"user:view:{u.user_id}")))
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"users:{mode}:{page-1}"))
    nav.button(text=f"📄 {page}/{total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"users:{mode}:{page+1}"))
    nav.adjust(3)
    rows = b.export() + nav.export()
    rows.append([InlineKeyboardButton(text=tr(lang, "ad_back"),
                                        callback_data="admin:users")])
    await safe_edit(cb.message, header,
                    InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("users:recent:"))
async def cb_users_recent(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    try:
        page = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        page = 1
    await _render_users_list(cb, c, "recent", page)


@router.callback_query(F.data.startswith("users:vip:"))
async def cb_users_vip(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    try:
        page = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        page = 1
    await _render_users_list(cb, c, "vip", page)


@router.callback_query(F.data == "users:search")
async def cb_users_search(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_users_search)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:users")]])
    await safe_edit(cb.message, tr(lang, "ad_u_search_ask"), kb)


@router.message(Flow.a_users_search, F.text)
async def msg_users_search(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    q = (message.text or "").strip()
    clean = q.lstrip("@")
    rows = get_conn().execute(
        """SELECT * FROM users WHERE
           CAST(user_id AS TEXT)=? OR username LIKE ? OR first_name LIKE ?
           LIMIT 20""", (q, f"%{clean}%", f"%{q}%")).fetchall()
    await state.clear()
    if not rows:
        await message.answer(tr(lang, "ad_u_not_found"))
        return
    b = InlineKeyboardBuilder()
    for r in rows:
        u = User.from_row(r)
        name = u.username or u.first_name or str(u.user_id)
        b.row(InlineKeyboardButton(
            text=f"{name[:35]}",
            callback_data=safe_cb(f"user:view:{u.user_id}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:users"))
    header = tr(lang, "ad_u_search_title") + f"  ({len(rows)})"
    await message.answer(header, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("user:view:"))
async def cb_user_view(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    try:
        uid = int(cb.data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await cb.answer()
        return
    u = UserRepo.get(uid)
    if not u:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    status = (tr(lang, "status_blocked") if u.is_blocked
              else tr(lang, "status_active"))
    tier = tr(lang, "tier_vip") if u.is_vip else tr(lang, "tier_normal")
    text = tr(lang, "ad_u_profile", uid=u.user_id,
              name=esc(u.first_name or "-"),
              username=esc("@" + u.username) if u.username else "-",
              total=u.downloads, success=u.success_dl, failed=u.failed_dl,
              status=status, tier=tier)
    block_btn = (tr(lang, "ad_u_unblock") if u.is_blocked
                 else tr(lang, "ad_u_block"))
    block_cb = f"user:unblock:{uid}" if u.is_blocked else f"user:block:{uid}"
    vip_btn = (tr(lang, "ad_u_vip_off") if u.is_vip
               else tr(lang, "ad_u_vip_on"))
    vip_cb = f"user:unvip:{uid}" if u.is_vip else f"user:setvip:{uid}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=block_btn,
                              callback_data=safe_cb(block_cb)),
         InlineKeyboardButton(text=vip_btn,
                              callback_data=safe_cb(vip_cb))],
        [InlineKeyboardButton(text=tr(lang, "ad_back"),
                              callback_data="admin:users")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data.startswith("user:block:"))
async def cb_user_block(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    uid = int(cb.data.rsplit(":", 1)[1])
    UserRepo.set_blocked(uid, True)
    db_log(cb.from_user.id, "user_block", str(uid))
    await cb.answer("🚫", show_alert=True)
    await cb_user_view(cb, c)


@router.callback_query(F.data.startswith("user:unblock:"))
async def cb_user_unblock(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    uid = int(cb.data.rsplit(":", 1)[1])
    UserRepo.set_blocked(uid, False)
    db_log(cb.from_user.id, "user_unblock", str(uid))
    await cb.answer("✅", show_alert=True)
    await cb_user_view(cb, c)


@router.callback_query(F.data.startswith("user:setvip:"))
async def cb_user_setvip(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    uid = int(cb.data.rsplit(":", 1)[1])
    UserRepo.set_vip(uid, True)
    db_log(cb.from_user.id, "user_vip", str(uid))
    await cb.answer("💎", show_alert=True)
    await cb_user_view(cb, c)


@router.callback_query(F.data.startswith("user:unvip:"))
async def cb_user_unvip(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    uid = int(cb.data.rsplit(":", 1)[1])
    UserRepo.set_vip(uid, False)
    db_log(cb.from_user.id, "user_unvip", str(uid))
    await cb.answer("💔", show_alert=True)
    await cb_user_view(cb, c)


# ══════════════════════════════════════════════════════════════
# ADMIN — JOBS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:jobs")
async def cb_admin_jobs(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await render_jobs(cb, c, "active", 1)


@router.callback_query(F.data.startswith("jobs:filter:"))
async def cb_jobs_filter(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) == 4:
        status = parts[2]
        try:
            page = int(parts[3])
        except ValueError:
            page = 1
    else:
        status, page = "active", 1
    await render_jobs(cb, c, status, page)


async def render_jobs(cb, c, status, page=1):
    lang = await _admin_lang(c, cb.from_user.id)
    per = 10
    page = max(1, page)
    total = JobRepo.count_for_filter(status)
    total_pages = max(1, (total + per - 1) // per)
    jobs = JobRepo.list_paginated(status, limit=per, offset=(page - 1) * per)
    labels = {"active": tr(lang, "ad_j_active"),
              "completed": tr(lang, "ad_j_completed"),
              "failed": tr(lang, "ad_j_failed"),
              "recent": tr(lang, "ad_j_recent")}
    label = labels.get(status, tr(lang, "ad_j_active"))
    b = InlineKeyboardBuilder()
    if not jobs:
        b.row(InlineKeyboardButton(text=tr(lang, "ad_j_empty"),
                                    callback_data="noop"))
    else:
        for j in jobs:
            icon = {"completed": "✅", "failed": "❌", "cancelled": "⚪",
                    "downloading": "⬇️", "uploading": "⬆️",
                    "queued": "⏳", "analyzing": "🔍"}.get(j.status, "⚙️")
            title = (j.title or j.job_id)[:26]
            size = _effective_filesize(j)
            dur = _effective_duration(j)
            b.row(InlineKeyboardButton(
                text=f"{icon} {title}\n💾 {fmt_bytes(size)} | ⏱ {fmt_duration(dur)}",
                callback_data=safe_cb(f"admin:job:{j.job_id}")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_j_active"),
                              callback_data="jobs:filter:active:1"),
        InlineKeyboardButton(text=tr(lang, "ad_j_completed"),
                              callback_data="jobs:filter:completed:1"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_j_failed"),
                              callback_data="jobs:filter:failed:1"),
        InlineKeyboardButton(text=tr(lang, "ad_j_recent"),
                              callback_data="jobs:filter:recent:1"))
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"jobs:filter:{status}:{page-1}"))
    nav.button(text=f"📄 {page}/{total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"jobs:filter:{status}:{page+1}"))
    nav.adjust(3)
    rows = b.export() + nav.export()
    rows.append([InlineKeyboardButton(text=tr(lang, "ad_back"),
                                        callback_data="admin:home")])
    text = tr(lang, "ad_j_title", status=label, count=total)
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("admin:job:retry:"))
async def cb_job_retry(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    jid = cb.data.rsplit(":", 1)[1]
    if not JobRepo.get(jid):
        await cb.answer()
        return
    clear_cancelled(jid)
    JobRepo.update(jid, status=STATUS_QUEUED, error=None)
    await c.job_queue.put(jid)
    await cb.answer("✅", show_alert=True)


@router.callback_query(F.data.startswith("admin:job:cancel:"))
async def cb_job_cancel_admin(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    jid = cb.data.rsplit(":", 1)[1]
    mark_cancelled(jid)
    JobRepo.update(jid, status=STATUS_CANCELLED, finished_at=now_ts())
    await cb.answer("🚫", show_alert=True)


@router.callback_query(F.data.startswith("admin:job:delete:"))
async def cb_job_delete_file(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    jid = cb.data.rsplit(":", 1)[1]
    j = JobRepo.get(jid)
    if j and j.file_path:
        with contextlib.suppress(Exception):
            p = Path(j.file_path)
            parent = p.parent
            if p.exists():
                p.unlink()
            cleanup_empty_dir(parent)
        JobRepo.update(jid, file_path=None)
    await cb.answer("🗑", show_alert=True)


@router.callback_query(F.data.startswith("admin:job:"))
async def cb_job_detail(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    tail = cb.data[len("admin:job:"):]
    if tail.startswith(("retry:", "cancel:", "delete:")):
        return
    j = JobRepo.get(tail)
    if not j:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    qn = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"]).get(
        j.quality, j.quality)
    text = tr(lang, "ad_j_detail", id=j.job_id, uid=j.user_id,
              title=esc(j.title or "-"), quality=esc(qn),
              status=esc(j.status), size=fmt_bytes(_effective_filesize(j)),
              duration=fmt_duration(_effective_duration(j)),
              url=esc(j.url[:200]))
    b = InlineKeyboardBuilder()
    if j.status in (STATUS_QUEUED, STATUS_ANALYZING, STATUS_PENDING,
                    STATUS_DOWNLOADING):
        b.row(InlineKeyboardButton(
            text=tr(lang, "ad_j_cancel"),
            callback_data=safe_cb(f"admin:job:cancel:{j.job_id}")))
    else:
        b.row(InlineKeyboardButton(
            text=tr(lang, "ad_j_retry"),
            callback_data=safe_cb(f"admin:job:retry:{j.job_id}")))
        if j.file_path and Path(j.file_path).exists():
            b.row(InlineKeyboardButton(
                text=tr(lang, "ad_j_delete_file"),
                callback_data=safe_cb(f"admin:job:delete:{j.job_id}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:jobs"))
    await safe_edit(cb.message, text, b.as_markup())


# ══════════════════════════════════════════════════════════════
# ADMIN — BROADCAST
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_broadcast_content)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:home")]])
    await safe_edit(cb.message, tr(lang, "ad_bc_title"), kb)


@router.message(Flow.a_broadcast_content)
async def msg_broadcast_content(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    content_data = {}
    if message.text:
        content_data = {"type": "text", "text": message.text}
    elif message.photo:
        content_data = {"type": "photo",
                        "file_id": message.photo[-1].file_id,
                        "caption": message.caption or ""}
    elif message.video:
        content_data = {"type": "video", "file_id": message.video.file_id,
                        "caption": message.caption or ""}
    elif message.document:
        content_data = {"type": "document",
                        "file_id": message.document.file_id,
                        "caption": message.caption or ""}
    else:
        await message.answer(tr(lang, "ad_bc_no_content"))
        return
    await state.update_data(bc_content=content_data)
    await state.set_state(Flow.a_broadcast_confirm)
    preview = (content_data.get("caption") or content_data.get("text") or "")[:200]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "yes"), callback_data="bc:confirm")],
        [InlineKeyboardButton(text=tr(lang, "no"), callback_data="bc:cancel")]])
    await message.answer(tr(lang, "ad_bc_preview", preview=esc(preview)),
                          reply_markup=kb)


@router.callback_query(F.data == "bc:cancel")
async def cb_bc_cancel(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    await safe_edit(cb.message, tr(lang, "ad_title"), admin_menu(lang))


@router.callback_query(F.data == "bc:confirm")
async def cb_bc_confirm(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    data = await state.get_data()
    content_data = data.get("bc_content", {})
    await state.clear()
    if not content_data:
        await safe_edit(cb.message, tr(lang, "ad_bc_no_content"),
                        admin_menu(lang))
        return
    rows = get_conn().execute(
        "SELECT user_id FROM users WHERE is_blocked=0").fetchall()
    uids = [r["user_id"] for r in rows]
    await safe_edit(cb.message, tr(lang, "ad_bc_sending", count=len(uids)))
    delay = float(db_get("broadcast_delay", "0.05"))
    sent = failed = 0
    t = content_data.get("type")
    for uid in uids:
        try:
            if t == "text":
                await send_text_safe(c.bot, uid, content_data["text"])
            elif t == "photo":
                await c.bot.send_photo(uid, content_data["file_id"],
                                        caption=content_data.get("caption", "")[:1024])
            elif t == "video":
                await c.bot.send_video(uid, content_data["file_id"],
                                        caption=content_data.get("caption", "")[:1024])
            elif t == "document":
                await c.bot.send_document(uid, content_data["file_id"],
                                           caption=content_data.get("caption", "")[:1024])
            sent += 1
        except TelegramForbiddenError:
            failed += 1
            UserRepo.set_blocked(uid, True)
        except Exception:
            failed += 1
        if delay > 0:
            await asyncio.sleep(delay)
    db_log(cb.from_user.id, "broadcast", f"sent={sent} failed={failed}")
    with contextlib.suppress(Exception):
        await c.bot.edit_message_text(
            chat_id=cb.message.chat.id, message_id=cb.message.message_id,
            text=tr(lang, "ad_bc_done", sent=sent, failed=failed),
            reply_markup=admin_menu(lang))


# ══════════════════════════════════════════════════════════════
# ADMIN — TICKETS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:tickets")
async def cb_admin_tickets(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await render_tickets(cb, c, "open", 1)


@router.callback_query(F.data.startswith("tk:filter:"))
async def cb_tickets_filter(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) == 4:
        status = parts[2]
        try:
            page = int(parts[3])
        except ValueError:
            page = 1
    else:
        status, page = "open", 1
    await render_tickets(cb, c, status, page)


async def render_tickets(cb, c, status="open", page=1):
    lang = await _admin_lang(c, cb.from_user.id)
    per = 10
    page = max(1, page)
    total = TicketRepo.count_by_status(status)
    total_pages = max(1, (total + per - 1) // per)
    rows = TicketRepo.by_status(status, limit=per, offset=(page - 1) * per)
    label = {"open": tr(lang, "ad_tk_open"),
             "closed": tr(lang, "ad_tk_closed"),
             "all": tr(lang, "ad_tk_all")}.get(status, "?")
    b = InlineKeyboardBuilder()
    if not rows:
        b.row(InlineKeyboardButton(text=tr(lang, "empty"), callback_data="noop"))
    else:
        for tk in rows:
            icon = {"open": "🟢", "closed": "🔴", "answered": "🟡"}.get(
                tk["status"], "⚪")
            preview = esc((tk["message"] or "")[:26])
            b.row(InlineKeyboardButton(
                text=f"{icon} #{tk['ticket_id']} | {tk['user_id']} | {preview}",
                callback_data=safe_cb(f"ticket:view:{tk['ticket_id']}")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_tk_open"),
                              callback_data="tk:filter:open:1"),
        InlineKeyboardButton(text=tr(lang, "ad_tk_closed"),
                              callback_data="tk:filter:closed:1"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_tk_all"),
                                callback_data="tk:filter:all:1"))
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"tk:filter:{status}:{page-1}"))
    nav.button(text=f"📄 {page}/{total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"tk:filter:{status}:{page+1}"))
    nav.adjust(3)
    rows_kb = b.export() + nav.export()
    rows_kb.append([InlineKeyboardButton(text=tr(lang, "ad_back"),
                                           callback_data="admin:home")])
    text = tr(lang, "ad_tk_title", status=label, count=total)
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=rows_kb))


@router.callback_query(F.data.startswith("ticket:view:"))
async def cb_ticket_view(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    try:
        tid = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        return
    tk = TicketRepo.get(tid)
    if not tk:
        await safe_edit(cb.message, tr(lang, "empty"))
        return
    text = tr(lang, "ad_tk_detail", id=tk["ticket_id"], uid=tk["user_id"],
              status=esc(tk["status"]), msg=esc(tk["message"]),
              date=fmt_time(tk["created_at"]))
    if tk["answer"]:
        text += f"\n\n💬 {esc(tk['answer'])}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "ad_tk_reply"),
                              callback_data=safe_cb(f"ticket:reply:{tid}")),
         InlineKeyboardButton(text=tr(lang, "ad_tk_close"),
                              callback_data=safe_cb(f"ticket:close:{tid}"))],
        [InlineKeyboardButton(text=tr(lang, "ad_back"),
                              callback_data="admin:tickets")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data.startswith("ticket:reply:"))
async def cb_ticket_reply(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    tid = int(cb.data.rsplit(":", 1)[1])
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_ticket_reply)
    await state.update_data(ticket_id=tid)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:tickets")]])
    await safe_edit(cb.message, tr(lang, "ad_tk_ask_reply"), kb)


@router.message(Flow.a_ticket_reply, F.text)
async def msg_ticket_reply(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tid = data.get("ticket_id")
    lang = await _admin_lang(c, message.from_user.id)
    if not tid:
        await state.clear()
        return
    tk = TicketRepo.get(tid)
    if not tk:
        await state.clear()
        return
    answer = (message.text or "").strip()
    if not answer:
        await message.answer(tr(lang, "empty"))
        return
    TicketRepo.answer(tid, answer)
    await state.clear()
    with contextlib.suppress(Exception):
        await c.bot.send_message(
            tk["user_id"],
            tr(lang, "ad_tk_reply_prefix", id=tid) + esc(answer))
    await message.answer(tr(lang, "ad_tk_reply_sent"))


@router.callback_query(F.data.startswith("ticket:close:"))
async def cb_ticket_close(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer("🔒", show_alert=True)
    tid = int(cb.data.rsplit(":", 1)[1])
    TicketRepo.close(tid)
    await render_tickets(cb, c, "open", 1)


# ══════════════════════════════════════════════════════════════
# ADMIN — SETTINGS
# ══════════════════════════════════════════════════════════════
async def _render_settings_panel(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    thumb = "✅" if db_get("send_thumbnail", "1") == "1" else "❌"
    subs = "✅" if db_get("download_subtitles", "0") == "1" else "❌"
    maint = "✅" if db_get("maintenance", "0") == "1" else "❌"
    photo = "✅" if db_get("photo_download_enabled", "1") == "1" else "❌"
    video = "✅" if db_get("video_download_enabled", "1") == "1" else "❌"
    compress = "✅" if db_get("compress_large_photos", "1") == "1" else "❌"
    smart = "✅" if db_get("smart_quality", "1") == "1" else "❌"
    text = tr(lang, "ad_set_title",
              maxsize=db_get("max_file_size_mb", "2048"),
              delay=db_get("delete_delay", "60"),
              retry=db_get("max_retries", "2"),
              thumb=thumb, subs=subs, maint=maint,
              photo=photo, video=video, compress=compress)
    text += f"\n{tr(lang, 'smart_quality_lbl')}: {smart}"
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_set_maxsize"),
                              callback_data="set:maxsize"),
        InlineKeyboardButton(text=tr(lang, "ad_set_delay"),
                              callback_data="set:delay"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_set_retry"),
                              callback_data="set:retry"),
        InlineKeyboardButton(text=tr(lang, "ad_set_thumb"),
                              callback_data="set:thumb"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_set_subs"),
                              callback_data="set:subs"),
        InlineKeyboardButton(text=tr(lang, "ad_set_maint"),
                              callback_data="set:maint"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_set_compress"),
                                callback_data="set:compress"))
    b.row(InlineKeyboardButton(
        text=f"{tr(lang, 'smart_quality_lbl')}: {smart}",
        callback_data="set:smart"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_set_maint_text"),
                                callback_data="set:maint_text"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_set_dl_types"),
                                callback_data="admin:dl_types"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:settings")
async def cb_admin_settings(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:smart")
async def cb_set_smart(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("smart_quality", "1")
    db_set("smart_quality", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:thumb")
async def cb_set_thumb(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("send_thumbnail", "1")
    db_set("send_thumbnail", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:subs")
async def cb_set_subs(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("download_subtitles", "0")
    db_set("download_subtitles", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:maint")
async def cb_set_maint(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("maintenance", "0")
    db_set("maintenance", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:compress")
async def cb_set_compress(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("compress_large_photos", "1")
    db_set("compress_large_photos", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_settings_panel(cb, c)


@router.callback_query(F.data == "set:maint_text")
async def cb_set_maint_text(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_setting_maint)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:settings")]])
    await safe_edit(cb.message, tr(lang, "ad_set_ask_maint"), kb)


@router.message(Flow.a_setting_maint, F.text)
async def msg_set_maint(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    lang = await _admin_lang(c, message.from_user.id)
    if not val:
        await message.answer(tr(lang, "empty"))
        return
    db_set("maintenance_text", val)
    await state.clear()
    await message.answer(tr(lang, "saved"))


@router.callback_query(F.data.startswith("set:"))
async def cb_set_value(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    key = cb.data.split(":", 1)[1]
    mapping = {"maxsize": ("max_file_size_mb", "ad_set_maxsize"),
               "delay": ("delete_delay", "ad_set_delay"),
               "retry": ("max_retries", "ad_set_retry")}
    if key not in mapping:
        return
    await cb.answer()
    setting_key, label_key = mapping[key]
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_setting_value)
    await state.update_data(setting_key=setting_key)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:settings")]])
    await safe_edit(cb.message,
                    tr(lang, "ad_set_ask", label=tr(lang, label_key)), kb)


@router.message(Flow.a_setting_value, F.text)
async def msg_set_value(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("setting_key")
    lang = await _admin_lang(c, message.from_user.id)
    if not key:
        await state.clear()
        return
    val = (message.text or "").strip()
    if not val.isdigit():
        await message.answer(tr(lang, "invalid"))
        return
    db_set(key, val)
    await state.clear()
    await message.answer(tr(lang, "saved"))


# ══════════════════════════════════════════════════════════════
# ADMIN — LIMITS
# ══════════════════════════════════════════════════════════════
async def _render_limits_panel(cb: CallbackQuery, c: Container,
                                tab: str = "video"):
    if tab not in ("video", "photo", "music", "adv"):
        tab = "video"
    lang = await _admin_lang(c, cb.from_user.id)
    hour = db_get("max_dl_hour", "10")
    day = db_get("max_dl_day", "50")
    concurrent = db_get("max_concurrent", "2")
    phour = db_get("max_photo_hour", "30")
    pday = db_get("max_photo_day", "200")
    mhour = db_get("max_music_hour", "30")
    mday = db_get("max_music_day", "200")
    cooldown = db_get("limit_cooldown_sec", "3")
    vip_u = "✅" if db_get("limit_vip_unlimited", "1") == "1" else "❌"
    owner_u = "✅" if db_get("limit_owner_unlimited", "1") == "1" else "❌"

    title_txt = tr(lang, "ad_lm_title")
    video_txt = f"🎬 {tr(lang, 'ad_lm_video_tab')}"
    photo_txt = f"🖼 {tr(lang, 'ad_lm_photo_tab')}"
    music_txt = f"🎵 {tr(lang, 'ad_lm_music_tab')}"
    hour_lbl = tr(lang, "ad_lm_hour")
    day_lbl = tr(lang, "ad_lm_day")
    conc_lbl = tr(lang, "ad_lm_concurrent")

    text = (
        f"{title_txt}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{video_txt}:\n  {hour_lbl}: {hour}  |  {day_lbl}: {day}\n\n"
        f"{photo_txt}:\n  {hour_lbl}: {phour}  |  {day_lbl}: {pday}\n\n"
        f"{music_txt}:\n  {hour_lbl}: {mhour}  |  {day_lbl}: {mday}\n\n"
        f"{conc_lbl}: <b>{concurrent}</b>\n"
        f"{tr(lang, 'cooldown_lbl')}: <b>{cooldown}s</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tr(lang, 'vip_unlimited_lbl')}: {vip_u}  |  "
        f"{tr(lang, 'owner_unlimited_lbl')}: {owner_u}"
    )

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_lm_video_tab"),
                              callback_data="limits:tab:video"),
        InlineKeyboardButton(text=tr(lang, "ad_lm_photo_tab"),
                              callback_data="limits:tab:photo"),
        InlineKeyboardButton(text=tr(lang, "ad_lm_music_tab"),
                              callback_data="limits:tab:music"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_lm_advanced"),
                                callback_data="limits:tab:adv"))

    if tab == "video":
        b.row(InlineKeyboardButton(
            text=f"{hour_lbl}: {hour}",
            callback_data="limit:max_dl_hour:video"))
        b.row(InlineKeyboardButton(
            text=f"{day_lbl}: {day}",
            callback_data="limit:max_dl_day:video"))
        b.row(InlineKeyboardButton(
            text=f"{conc_lbl}: {concurrent}",
            callback_data="limit:max_concurrent:video"))
    elif tab == "photo":
        b.row(InlineKeyboardButton(
            text=f"{hour_lbl}: {phour}",
            callback_data="limit:max_photo_hour:photo"))
        b.row(InlineKeyboardButton(
            text=f"{day_lbl}: {pday}",
            callback_data="limit:max_photo_day:photo"))
        b.row(InlineKeyboardButton(
            text=f"{conc_lbl}: {concurrent}",
            callback_data="limit:max_concurrent:photo"))
    elif tab == "music":
        b.row(InlineKeyboardButton(
            text=f"{hour_lbl}: {mhour}",
            callback_data="limit:max_music_hour:music"))
        b.row(InlineKeyboardButton(
            text=f"{day_lbl}: {mday}",
            callback_data="limit:max_music_day:music"))
        b.row(InlineKeyboardButton(
            text=f"{conc_lbl}: {concurrent}",
            callback_data="limit:max_concurrent:music"))
    else:
        b.row(InlineKeyboardButton(
            text=f"{tr(lang, 'cooldown_lbl')}: {cooldown}s",
            callback_data="limit:limit_cooldown_sec:adv"))
        b.row(InlineKeyboardButton(
            text=f"{tr(lang, 'vip_unlimited_lbl')}: {vip_u}",
            callback_data="limit:toggle_vip:adv"))
        b.row(InlineKeyboardButton(
            text=f"{tr(lang, 'owner_unlimited_lbl')}: {owner_u}",
            callback_data="limit:toggle_owner:adv"))

    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:limits")
async def cb_admin_limits(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_limits_panel(cb, c, "video")


@router.callback_query(F.data.startswith("limits:tab:"))
async def cb_limits_tab(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    tab = cb.data.rsplit(":", 1)[1]
    await _render_limits_panel(cb, c, tab)


@router.callback_query(F.data.startswith("limit:toggle_"))
async def cb_limit_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    which = cb.data.rsplit(":", 1)[1]
    if which == "toggle_vip":
        cur = db_get("limit_vip_unlimited", "1")
        db_set("limit_vip_unlimited", "0" if cur == "1" else "1")
    elif which == "toggle_owner":
        cur = db_get("limit_owner_unlimited", "1")
        db_set("limit_owner_unlimited", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_limits_panel(cb, c, "adv")


@router.callback_query(F.data.startswith("limit:"))
async def cb_limit_value(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    _, setting_key, tab = parts
    valid_keys = {"max_dl_hour", "max_dl_day", "max_photo_hour",
                  "max_photo_day", "max_music_hour", "max_music_day",
                  "max_concurrent", "limit_cooldown_sec"}
    if setting_key not in valid_keys:
        await cb.answer()
        return
    if tab not in ("video", "photo", "music", "adv"):
        tab = "video"
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_limit_value)
    await state.update_data(setting_key=setting_key, return_tab=tab)
    labels = {
        "max_dl_hour": "⏱ Video/Hour",
        "max_dl_day": "📅 Video/Day",
        "max_photo_hour": "⏱ Photo/Hour",
        "max_photo_day": "📅 Photo/Day",
        "max_music_hour": "⏱ Music/Hour",
        "max_music_day": "📅 Music/Day",
        "max_concurrent": "⚡ Concurrent",
        "limit_cooldown_sec": "⏸ Cooldown",
    }
    label = labels.get(setting_key, setting_key)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_lm_back_to_limits"),
                             callback_data=safe_cb(f"limits:tab:{tab}"))]])
    await safe_edit(cb.message, tr(lang, "ad_lm_ask", label=label), kb)


@router.message(Flow.a_limit_value, F.text)
async def msg_limit_value(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("setting_key")
    tab = data.get("return_tab", "video")
    lang = await _admin_lang(c, message.from_user.id)
    if not key:
        await state.clear()
        return
    val = (message.text or "").strip()
    if not val.isdigit():
        await message.answer(tr(lang, "invalid"))
        return
    db_set(key, val)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_lm_back_to_limits"),
                             callback_data=safe_cb(f"limits:tab:{tab}"))]])
    await message.answer(tr(lang, "saved"), reply_markup=kb)


# ══════════════════════════════════════════════════════════════
# ADMIN — CHANNEL
# ══════════════════════════════════════════════════════════════
async def _render_channel_panel(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    status = (tr(lang, "active") if db_get("force_join", "0") == "1"
              else tr(lang, "disabled"))
    channel = db_get("channel_username", "") or "-"
    text = tr(lang, "ad_ch_title", status=status, channel=esc(channel))
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "ad_ch_toggle"),
                                callback_data="ch:toggle"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_ch_set"),
                                callback_data="ch:set"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:channel")
async def cb_admin_channel(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_channel_panel(cb, c)


@router.callback_query(F.data == "ch:toggle")
async def cb_ch_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("force_join", "0")
    db_set("force_join", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_channel_panel(cb, c)


@router.callback_query(F.data == "ch:set")
async def cb_ch_set(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_channel)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:channel")]])
    await safe_edit(cb.message, tr(lang, "ad_ch_ask"), kb)


@router.message(Flow.a_channel, F.text)
async def msg_channel(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    lang = await _admin_lang(c, message.from_user.id)
    if not val:
        await message.answer(tr(lang, "empty"))
        return
    if not val.startswith("@") and not val.lstrip("-").isdigit():
        val = "@" + val
    db_set("channel_username", val)
    await state.clear()
    await message.answer(tr(lang, "saved"))


# ══════════════════════════════════════════════════════════════
# ADMIN — QUALITY
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:quality")
async def cb_admin_quality(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    allowed = allowed_qualities()
    labels = QUALITY_LABELS.get(lang, QUALITY_LABELS["fa"])
    b = InlineKeyboardBuilder()
    for q in ALL_QUALITIES:
        icon = "✅" if q in allowed else "❌"
        b.row(InlineKeyboardButton(
            text=f"{icon} {labels[q]}",
            callback_data=safe_cb(f"admq:toggle:{q}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    en = ", ".join(labels[q] for q in ALL_QUALITIES if q in allowed) or "-"
    di = ", ".join(labels[q] for q in ALL_QUALITIES if q not in allowed) or "-"
    text = tr(lang, "ad_q_title", enabled=esc(en), disabled=esc(di))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data.startswith("admq:toggle:"))
async def cb_quality_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    q = cb.data.rsplit(":", 1)[1]
    if q not in ALL_QUALITIES:
        await cb.answer()
        return
    allowed = allowed_qualities()
    if q in allowed:
        allowed.discard(q)
    else:
        allowed.add(q)
    db_set("allowed_quality", ",".join(sorted(allowed)))
    await cb.answer("✅")
    await cb_admin_quality(cb, c)


# ══════════════════════════════════════════════════════════════
# ADMIN — LOGS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:logs")
async def cb_admin_logs(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    rows = get_conn().execute(
        "SELECT * FROM logs ORDER BY created_at DESC LIMIT 20").fetchall()
    text = tr(lang, "ad_logs_title") + "\n\n"
    if not rows:
        text += tr(lang, "ad_logs_empty")
    else:
        for r in rows:
            text += (f"<code>{r['admin_id']}</code> | {esc(r['action'])} | "
                     f"{esc(str(r['details'] or '')[:50])} | "
                     f"{fmt_time(r['created_at'])}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:home")]])
    await safe_edit(cb.message, text, kb)


# ══════════════════════════════════════════════════════════════
# ADMIN — TOOLS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:tools")
async def cb_admin_tools(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    try:
        db_size = fmt_bytes(DB_PATH.stat().st_size)
    except Exception:
        db_size = "—"
    r = get_conn().execute("SELECT COUNT(*) AS c FROM backups").fetchone()
    backups = int(r["c"] or 0)
    text = tr(lang, "ad_tools_title", db_size=db_size, backups=backups)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "ad_tools_backup"),
                                callback_data="tools:backup"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_tools_vacuum"),
                                callback_data="tools:vacuum"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_tools_clear_logs"),
                              callback_data="tools:clear_logs"),
        InlineKeyboardButton(text=tr(lang, "ad_tools_clear_dl"),
                              callback_data="tools:clear_dl"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_tools_auto_backup"),
                                callback_data="tools:auto_backup"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "tools:backup")
async def cb_tools_backup(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    try:
        name = f"backup_{fmt_dt_short(now_ts())}.db"
        dst = BACKUP_DIR / name
        checkpoint_db()
        shutil.copy2(DB_PATH, dst)
        size = dst.stat().st_size
        get_conn().execute(
            "INSERT INTO backups(path, size, created_at) VALUES (?, ?, ?)",
            (str(dst), size, now_ts()))
        db_log(cb.from_user.id, "backup", name)
        await c.bot.send_document(chat_id=cb.from_user.id,
                                    document=FSInputFile(str(dst)),
                                    caption=tr(lang, "ad_tools_backup_ok", name=name))
    except Exception as e:
        with contextlib.suppress(Exception):
            await cb.message.answer(f"❌ {esc(str(e))}")


@router.callback_query(F.data == "tools:vacuum")
async def cb_tools_vacuum(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer("⚡", show_alert=True)
    with contextlib.suppress(Exception):
        get_conn().execute("VACUUM")


@router.callback_query(F.data == "tools:clear_logs")
async def cb_tools_clear_logs(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    n = 0
    for f in LOG_DIR.glob("*.log*"):
        with contextlib.suppress(Exception):
            f.unlink()
            n += 1
    await cb.answer(f"🗑 {n}", show_alert=True)


@router.callback_query(F.data == "tools:clear_dl")
async def cb_tools_clear_dl(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    n = 0
    if DOWNLOAD_DIR.exists():
        for d in DOWNLOAD_DIR.iterdir():
            with contextlib.suppress(Exception):
                if d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)
                else:
                    d.unlink()
                n += 1
    await cb.answer(f"🧹 {n}", show_alert=True)


@router.callback_query(F.data == "tools:auto_backup")
async def cb_auto_backup_menu(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    enabled = db_get("auto_backup_enabled", "0") == "1"
    hours = db_get("auto_backup_hours", "24")
    try:
        last_ts = float(db_get("auto_backup_last", "0") or "0")
    except ValueError:
        last_ts = 0.0
    last_str = fmt_time(last_ts) if last_ts else "—"
    status = tr(lang, "active") if enabled else tr(lang, "disabled")
    text = tr(lang, "ad_auto_backup_title", status=status, hours=hours,
              last=last_str)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "ad_auto_backup_toggle"),
                                callback_data="auto_backup:toggle"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_auto_backup_hours"),
                                callback_data="auto_backup:hours"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:tools"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "auto_backup:toggle")
async def cb_auto_backup_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("auto_backup_enabled", "0")
    db_set("auto_backup_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await cb_auto_backup_menu(cb, c)


@router.callback_query(F.data == "auto_backup:hours")
async def cb_auto_backup_hours(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_auto_backup_hours)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="tools:auto_backup")]])
    await safe_edit(cb.message, tr(lang, "ad_auto_backup_ask"), kb)


@router.message(Flow.a_auto_backup_hours, F.text)
async def msg_auto_backup_hours(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    if not val.replace(".", "").isdigit():
        await message.answer("⚠️")
        return
    db_set("auto_backup_hours", val)
    await state.clear()
    await message.answer("✅")


# ══════════════════════════════════════════════════════════════
# ADMIN — UPDATE
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:update")
async def cb_admin_update(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    version = db_get("bot_version", FILE_VERSION)
    writable = "✅" if os.access(BASE_DIR, os.W_OK) else "❌"
    text = tr(lang, "ad_up_title", version=esc(version),
              run_file=esc(Path(__file__).name), writable=writable)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_up_apply"),
                              callback_data="up:apply"),
        InlineKeyboardButton(text=tr(lang, "ad_up_fetch"),
                              callback_data="up:fetch"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "ad_up_history"),
                              callback_data="up:history"),
        InlineKeyboardButton(text=tr(lang, "ad_up_rollback"),
                              callback_data="up:rollback"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "up:apply")
async def cb_up_apply(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_up_zip)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:update")]])
    await safe_edit(cb.message, tr(lang, "ad_up_ask_zip"), kb)


@router.message(Flow.a_up_zip, F.document)
async def msg_up_zip(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id) or not c.bot:
        return
    doc = message.document
    lang = await _admin_lang(c, message.from_user.id)
    if not doc or not doc.file_name:
        return
    fname = doc.file_name.lower()
    if not (fname.endswith(".zip") or fname.endswith(".py")):
        await message.answer(tr(lang, "ad_up_invalid_file"))
        return
    try:
        ts = fmt_dt_short(now_ts())
        current_file = Path(__file__).resolve()
        backup_code = BACKUP_DIR / f"pre_update_{ts}_DownVip.py"
        shutil.copy2(current_file, backup_code)
        new_version = "unknown"
        prev = db_get("bot_version", FILE_VERSION)
        if fname.endswith(".py"):
            tmp = UPDATE_DIR / f"update_{ts}.py"
            await download_tg_file(c.bot, doc.file_id, tmp)
            content = tmp.read_text(encoding="utf-8", errors="ignore")
            compile(content, "update.py", "exec")
            shutil.copy2(tmp, current_file)
            with contextlib.suppress(Exception):
                tmp.unlink()
            m = re.search(r'Version\s+([\d]+\.[\d]+(?:\.[\d]+)?)', content)
            new_version = m.group(1) if m else f"unknown_{ts}"
        else:
            dst = UPDATE_DIR / f"update_{ts}.zip"
            await download_tg_file(c.bot, doc.file_id, dst)
            extract_dir = UPDATE_DIR / f"extract_{ts}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dst, "r") as zf:
                base = extract_dir.resolve()
                for zi in zf.infolist():
                    tgt = (extract_dir / zi.filename).resolve()
                    if tgt != base and base not in tgt.parents:
                        raise ValueError("unsafe path in zip")
                zf.extractall(extract_dir)
            candidates = list(extract_dir.rglob("bot.py"))
            if not candidates:
                await state.clear()
                await message.answer(tr(lang, "ad_up_no_botpy"))
                return
            new_file = candidates[0]
            content = new_file.read_text(encoding="utf-8", errors="ignore")
            compile(content, "bot.py", "exec")
            shutil.copy2(new_file, current_file)
            with contextlib.suppress(Exception):
                shutil.rmtree(extract_dir, ignore_errors=True)
                dst.unlink()
            m = re.search(r'Version\s+([\d]+\.[\d]+(?:\.[\d]+)?)', content)
            new_version = m.group(1) if m else f"unknown_{ts}"
        with contextlib.suppress(Exception):
            get_conn().execute(
                "INSERT INTO update_history(version, prev_version, applied, "
                "backup_path, note, created_at) VALUES (?, ?, 1, ?, ?, ?)",
                (new_version, prev, str(backup_code), fname, now_ts()))
        db_set("bot_version", new_version)
        db_set("prev_version", prev)
        await state.clear()
        await message.answer(
            f"✅ {new_version}\n{tr(lang, 'ad_up_restart_msg')}")
        await asyncio.sleep(3)
        _restart_process(current_file)
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ {esc(str(e))}")


@router.callback_query(F.data == "up:fetch")
async def cb_up_fetch(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    try:
        name = f"source_{fmt_dt_short(now_ts())}.zip"
        dst = UPDATE_DIR / name
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in BASE_DIR.glob("*.py"):
                zf.write(f, f.name)
        await c.bot.send_document(chat_id=cb.from_user.id,
                                    document=FSInputFile(str(dst)),
                                    caption=name)
    except Exception as e:
        with contextlib.suppress(Exception):
            await cb.message.answer(f"❌ {esc(str(e))}")


@router.callback_query(F.data == "up:history")
async def cb_up_history(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    rows = get_conn().execute(
        "SELECT * FROM update_history ORDER BY created_at DESC LIMIT 15"
    ).fetchall()
    text = tr(lang, "ad_up_history_title") + "\n\n"
    if not rows:
        text += tr(lang, "ad_up_history_empty")
    else:
        for r in rows:
            text += f"<code>{esc(r['version'])}</code> {fmt_time(r['created_at'])}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:update")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data == "up:rollback")
async def cb_up_rollback(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    backups = sorted(BACKUP_DIR.glob("pre_update_*_DownVip.py"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        await cb.answer("⚠️", show_alert=True)
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="up:rollback_yes")],
        [InlineKeyboardButton(text="❌", callback_data="admin:update")]])
    await safe_edit(
        cb.message,
        f"{tr(lang, 'rollback_title')}\n"
        f"<code>{esc(backups[0].name)}</code>\n\n"
        f"{tr(lang, 'rollback_confirm_text')}",
        kb)


@router.callback_query(F.data == "up:rollback_yes")
async def cb_up_rollback_yes(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    backups = sorted(BACKUP_DIR.glob("pre_update_*_DownVip.py"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        await cb.answer("⚠️", show_alert=True)
        return
    await cb.answer("♻️")
    try:
        src = backups[0]
        content = src.read_text(encoding="utf-8", errors="ignore")
        compile(content, src.name, "exec")
        current_file = Path(__file__).resolve()
        shutil.copy2(current_file, BACKUP_DIR /
                     f"pre_rollback_{fmt_dt_short(now_ts())}_DownVip.py")
        shutil.copy2(src, current_file)
        m = re.search(r'Version\s+([\d]+\.[\d]+(?:\.[\d]+)?)', content)
        ver = m.group(1) if m else "unknown"
        prev = db_get("bot_version", FILE_VERSION)
        with contextlib.suppress(Exception):
            get_conn().execute(
                "INSERT INTO update_history(version, prev_version, applied, "
                "backup_path, note, created_at) VALUES (?, ?, 0, ?, ?, ?)",
                (ver, prev, str(src), "rollback", now_ts()))
        db_set("bot_version", ver)
        db_set("prev_version", prev)
        lang = await _admin_lang(c, cb.from_user.id)
        await cb.message.answer(
            f"↩️ {esc(ver)}\n{tr(lang, 'rollback_restarting')}")
        await asyncio.sleep(3)
        _restart_process(current_file)
    except Exception as e:
        with contextlib.suppress(Exception):
            await cb.message.answer(f"❌ {esc(str(e))}")


# ══════════════════════════════════════════════════════════════
# ANNOUNCE — HELPERS
# ══════════════════════════════════════════════════════════════
def _audience_count() -> int:
    try:
        a = db_get("announce_audience", "all")
        q = {
            "vip": "SELECT COUNT(*) AS c FROM users WHERE is_blocked=0 AND is_vip=1",
            "active": "SELECT COUNT(*) AS c FROM users WHERE is_blocked=0 AND downloads>0",
            "inactive": "SELECT COUNT(*) AS c FROM users WHERE is_blocked=0 AND downloads=0",
        }.get(a, "SELECT COUNT(*) AS c FROM users WHERE is_blocked=0")
        r = get_conn().execute(q).fetchone()
        return int(r["c"] or 0)
    except Exception:
        return 0


def _audience_uids() -> list:
    a = db_get("announce_audience", "all")
    q = {
        "vip": "SELECT user_id FROM users WHERE is_blocked=0 AND is_vip=1",
        "active": "SELECT user_id FROM users WHERE is_blocked=0 AND downloads>0",
        "inactive": "SELECT user_id FROM users WHERE is_blocked=0 AND downloads=0",
    }.get(a, "SELECT user_id FROM users WHERE is_blocked=0")
    try:
        rows = get_conn().execute(q).fetchall()
        return [int(r["user_id"]) for r in rows]
    except Exception:
        return []


async def _auto_delete_msg(bot, chat_id, msg_id, delay):
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


def _spawn_auto_delete(c: Container, bot, chat_id, msg_id, delay):
    task = asyncio.create_task(_auto_delete_msg(bot, chat_id, msg_id, delay))
    if c and hasattr(c, 'bg_tasks'):
        c.bg_tasks.append(task)

        def _cleanup(t):
            with contextlib.suppress(Exception):
                if t in c.bg_tasks:
                    c.bg_tasks.remove(t)

        task.add_done_callback(_cleanup)
    return task


# ══════════════════════════════════════════════════════════════
# ADMIN — ANNOUNCE MAIN
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:announce")
async def cb_admin_announce(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    st = tr(lang, "active") if db_get("announce_enabled", "0") == "1" else tr(lang, "disabled")

    a = db_get("announce_audience", "all")
    a_label = audience_label(lang, a)
    count = _audience_count()

    try:
        ts_total = int(db_get("announce_total_sent", "0") or "0")
        tf_total = int(db_get("announce_total_failed", "0") or "0")
    except Exception:
        ts_total = tf_total = 0

    ch_id = db_get("announce_channel_id", "") or "—"
    try:
        ch_total = int(db_get("announce_channel_total", "0") or "0")
    except Exception:
        ch_total = 0

    text = tr(lang, "an_main_title", status=st, audience=a_label,
              count=count, sent=ts_total, failed=tf_total,
              channel=esc(ch_id), ch_total=ch_total)

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_users"),
                              callback_data="an:users_menu"),
        InlineKeyboardButton(text=tr(lang, "an_btn_channel"),
                              callback_data="an:channel_menu"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_stats"),
                              callback_data="an:stats"),
        InlineKeyboardButton(text=tr(lang, "an_btn_history"),
                              callback_data="an:history"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


# ══════════════════════════════════════════════════════════════
# ANNOUNCE — USERS
# ══════════════════════════════════════════════════════════════
async def _render_an_users(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    st = tr(lang, "active") if db_get("announce_enabled", "0") == "1" else tr(lang, "disabled")
    pin = "✅" if db_get("announce_pin", "0") == "1" else "❌"
    silent = "✅" if db_get("announce_silent", "0") == "1" else "❌"
    preview = "✅" if db_get("announce_preview", "1") == "1" else "❌"
    autodel = "✅" if db_get("announce_auto_delete", "0") == "1" else "❌"
    a = db_get("announce_audience", "all")
    a_label = audience_label(lang, a)
    count = _audience_count()

    text = tr(lang, "an_users_title", status=st, audience=a_label,
              count=count, pin=pin, silent=silent,
              preview=preview, autodel=autodel)

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=tr(lang, "an_btn_audience", label=a_label, count=count),
        callback_data="an:audience"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_text"),
                              callback_data="an:send_text"),
        InlineKeyboardButton(text=tr(lang, "an_btn_media"),
                              callback_data="an:send_media"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_forward"),
                              callback_data="an:send_forward"),
        InlineKeyboardButton(text=tr(lang, "an_btn_test"),
                              callback_data="an:test"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_pin", v=pin),
                              callback_data="an:pin"),
        InlineKeyboardButton(text=tr(lang, "an_btn_silent", v=silent),
                              callback_data="an:silent"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_preview", v=preview),
                              callback_data="an:preview"),
        InlineKeyboardButton(text=tr(lang, "an_btn_autodel", v=autodel),
                              callback_data="an:auto_delete"))
    b.row(InlineKeyboardButton(text=tr(lang, "an_btn_schedule"),
                                callback_data="an:schedule_menu"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_enable"),
                              callback_data="an:toggle"),
        InlineKeyboardButton(text=tr(lang, "an_btn_reset"),
                              callback_data="an:reset_stats"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:announce"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "an:users_menu")
async def cb_an_users_menu(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:audience")
async def cb_an_audience(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    cur = db_get("announce_audience", "all")
    try:
        total = UserRepo.count_all()
        vip = UserRepo.count_vip()
        active = int(get_conn().execute(
            "SELECT COUNT(*) AS c FROM users WHERE downloads>0").fetchone()["c"] or 0)
        inactive = int(get_conn().execute(
            "SELECT COUNT(*) AS c FROM users WHERE downloads=0").fetchone()["c"] or 0)
    except Exception:
        total = vip = active = inactive = 0

    text = tr(lang, "an_audience_title",
              total=total, vip=vip, active=active, inactive=inactive)

    def mark(k): return "✅ " if cur == k else ""
    b = InlineKeyboardBuilder()
    for k in ("all", "vip", "active", "inactive"):
        b.row(InlineKeyboardButton(
            text=f"{mark(k)}{audience_label(lang, k)}",
            callback_data=f"an:set_aud:{k}"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="an:users_menu"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data.startswith("an:set_aud:"))
async def cb_an_set_aud(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    val = cb.data.rsplit(":", 1)[1]
    if val not in ("all", "vip", "active", "inactive"):
        await cb.answer()
        return
    db_set("announce_audience", val)
    await cb.answer("✅")
    await cb_an_audience(cb, c)


@router.callback_query(F.data == "an:toggle")
async def cb_an_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_enabled", "0")
    db_set("announce_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:pin")
async def cb_an_pin(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_pin", "0")
    db_set("announce_pin", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:silent")
async def cb_an_silent(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_silent", "0")
    db_set("announce_silent", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:preview")
async def cb_an_preview(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_preview", "1")
    db_set("announce_preview", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:auto_delete")
async def cb_an_autodel(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_auto_delete", "0")
    db_set("announce_auto_delete", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:send_text")
async def cb_an_send_text(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_msg)
    await state.update_data(announce_kind="text", announce_text=None,
                            announce_media=None, announce_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="an:users_menu")]])
    await safe_edit(cb.message, tr(lang, "an_text_ask"), kb)


@router.message(Flow.a_announce_msg, F.text)
async def msg_an_text(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    text = (message.text or "").strip()
    if not text:
        await message.answer("⚠️")
        return
    await state.update_data(announce_text=text)
    await state.set_state(Flow.a_announce_confirm)
    await _show_user_preview(message, c, lang, text=text)


@router.callback_query(F.data == "an:send_media")
async def cb_an_send_media(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_media)
    await state.update_data(announce_kind="media", announce_text=None,
                            announce_media=None, announce_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="an:users_menu")]])
    await safe_edit(cb.message, tr(lang, "an_media_ask"), kb)


@router.message(Flow.a_announce_media)
async def msg_an_media(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    data = await state.get_data()
    kind = data.get("announce_kind", "media")
    if kind == "forward":
        fwd = {"from_chat_id": message.chat.id,
               "message_id": message.message_id}
        await state.update_data(announce_forward=fwd)
        await state.set_state(Flow.a_announce_confirm)
        await _show_user_preview(message, c, lang,
                                  text=tr(lang, "an_btn_forward"))
        return
    media = None
    if message.photo:
        media = {"type": "photo", "file_id": message.photo[-1].file_id,
                 "caption": message.caption or ""}
    elif message.video:
        media = {"type": "video", "file_id": message.video.file_id,
                 "caption": message.caption or ""}
    elif message.document:
        media = {"type": "document", "file_id": message.document.file_id,
                 "caption": message.caption or ""}
    elif message.audio:
        media = {"type": "audio", "file_id": message.audio.file_id,
                 "caption": message.caption or ""}
    elif message.animation:
        media = {"type": "animation", "file_id": message.animation.file_id,
                 "caption": message.caption or ""}
    else:
        await message.answer("⚠️")
        return
    await state.update_data(announce_media=media)
    await state.set_state(Flow.a_announce_confirm)
    await _show_user_preview(message, c, lang, media=media)


@router.callback_query(F.data == "an:send_forward")
async def cb_an_send_forward(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_media)
    await state.update_data(announce_kind="forward", announce_text=None,
                            announce_media=None, announce_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="an:users_menu")]])
    await safe_edit(cb.message, tr(lang, "an_forward_ask"), kb)


async def _show_user_preview(target, c: Container, lang: str,
                              text=None, media=None):
    preview_on = db_get("announce_preview", "1") == "1"
    a = db_get("announce_audience", "all")
    a_label = audience_label(lang, a)
    count = _audience_count()
    body = (tr(lang, "an_preview_title", channel="—") +
            f"\n{tr(lang, 'an_preview_audience', label=a_label, count=count)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n")
    if text:
        p = text[:800] if preview_on else "🔒"
        body += f"📝 <blockquote>{esc(p)}</blockquote>\n"
    if media:
        body += f"📎 {media.get('type', '?')}\n"
        if media.get("caption") and preview_on:
            body += f"💬 <blockquote>{esc(media['caption'][:400])}</blockquote>\n"
    body += f"━━━━━━━━━━━━━━━━━━━━━\n{tr(lang, 'an_send_confirm')}"
    b = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "an_send_btn"),
                              callback_data="an:confirm_send")],
        [InlineKeyboardButton(text=tr(lang, "an_cancel_btn"),
                              callback_data="an:abort")]])
    if isinstance(target, Message):
        await target.answer(body, reply_markup=b)
    else:
        await safe_edit(target, body, b)


@router.callback_query(F.data == "an:abort")
async def cb_an_abort(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer("❌")
    await state.clear()
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:confirm_send")
async def cb_an_confirm_send(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    data = await state.get_data()
    text = data.get("announce_text") or ""
    media = data.get("announce_media") or {}
    forward = data.get("announce_forward") or None
    uids = _audience_uids()
    if not uids:
        await cb.answer("⚠️", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    try:
        sched_ts = float(db_get("announce_schedule_ts", "0") or 0)
    except ValueError:
        sched_ts = 0.0
    if sched_ts > now_ts():
        import json
        db_set("announce_scheduled_payload", json.dumps({
            "text": text, "media": media, "forward": forward,
            "chat_id": cb.message.chat.id, "admin_id": cb.from_user.id},
            ensure_ascii=False))
        with contextlib.suppress(Exception):
            await cb.message.answer(
                f"⏰ {esc(db_get('announce_schedule', ''))}")
        return
    asyncio.create_task(_do_user_broadcast(c, cb, uids, text, media, forward))


async def _do_user_broadcast(c, cb, uids, text, media, forward):
    silent = db_get("announce_silent", "0") == "1"
    autodel = db_get("announce_auto_delete", "0") == "1"
    del_after = int(db_get("announce_delete_after", "3600") or "3600")
    delay = float(db_get("broadcast_delay", "0.05") or 0.05)
    total = len(uids)
    sent = failed = 0
    last_update = 0.0
    lang = "fa"
    with contextlib.suppress(Exception):
        user = UserRepo.get(cb.from_user.id)
        if user:
            lang = user_lang(user)
    try:
        progress = await c.bot.send_message(
            cb.message.chat.id,
            f"{tr(lang, 'bc_progress')}\n"
            f"{tr(lang, 'wc_users', total=total)}")
    except Exception:
        progress = None

    for idx, uid in enumerate(uids, 1):
        try:
            sent_msg = None
            if forward:
                with contextlib.suppress(Exception):
                    sent_msg = await c.bot.copy_message(
                        chat_id=uid, from_chat_id=forward["from_chat_id"],
                        message_id=forward["message_id"],
                        disable_notification=silent)
            elif media:
                t = media.get("type")
                cap = (media.get("caption") or "")[:1024]
                if t == "photo":
                    sent_msg = await c.bot.send_photo(
                        uid, media["file_id"], caption=cap,
                        disable_notification=silent)
                elif t == "video":
                    sent_msg = await c.bot.send_video(
                        uid, media["file_id"], caption=cap,
                        disable_notification=silent)
                elif t == "document":
                    sent_msg = await c.bot.send_document(
                        uid, media["file_id"], caption=cap,
                        disable_notification=silent)
                elif t == "audio":
                    sent_msg = await c.bot.send_audio(
                        uid, media["file_id"], caption=cap,
                        disable_notification=silent)
                elif t == "animation":
                    sent_msg = await c.bot.send_animation(
                        uid, media["file_id"], caption=cap,
                        disable_notification=silent)
            else:
                sent_msg = await send_text_safe(
                    c.bot, uid, text, disable_notification=silent)
            if sent_msg:
                sent += 1
                if autodel:
                    _spawn_auto_delete(c, c.bot, uid,
                                       sent_msg.message_id, del_after)
            else:
                failed += 1
        except TelegramForbiddenError:
            failed += 1
            with contextlib.suppress(Exception):
                UserRepo.set_blocked(uid, True)
        except Exception:
            failed += 1

        now = now_ts()
        if progress and now - last_update > 2.5:
            last_update = now
            with contextlib.suppress(Exception):
                await c.bot.edit_message_text(
                    chat_id=cb.message.chat.id,
                    message_id=progress.message_id,
                    text=(f"{tr(lang, 'bc_progress')}\n"
                          f"{tr(lang, 'wc_users', total=total)}\n"
                          f"{tr(lang, 'wc_sent', sent=sent)}\n"
                          f"{tr(lang, 'wc_failed', failed=failed)}\n"
                          f"{tr(lang, 'wc_progress', idx=idx, total=total)}"))
        if delay > 0:
            await asyncio.sleep(delay)

    db_log(cb.from_user.id, "announce_sent",
           f"sent={sent} failed={failed} audience={db_get('announce_audience', 'all')}")
    db_set("announce_last_ts", str(now_ts()))
    try:
        ps = int(db_get("announce_total_sent", "0") or "0")
        pf = int(db_get("announce_total_failed", "0") or "0")
        db_set("announce_total_sent", str(ps + sent))
        db_set("announce_total_failed", str(pf + failed))
    except Exception:
        pass

    if progress:
        with contextlib.suppress(Exception):
            await c.bot.edit_message_text(
                chat_id=cb.message.chat.id, message_id=progress.message_id,
                text=(f"{tr(lang, 'wc_complete')}\n"
                      f"{tr(lang, 'wc_users', total=total)}\n"
                      f"✔️ {sent}\n✖️ {failed}"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️", callback_data="admin:announce")]]))


@router.callback_query(F.data == "an:schedule_menu")
async def cb_an_schedule_menu(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    cur = db_get("announce_schedule", "") or "—"
    text = f"⏰ <b>{tr(lang, 'an_btn_schedule')}</b>\n\n🕐 {esc(cur)}"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✏️", callback_data="an:set_schedule"))
    b.row(InlineKeyboardButton(text="🗑", callback_data="an:clear_schedule"))
    b.row(InlineKeyboardButton(text="◀️", callback_data="an:users_menu"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "an:set_schedule")
async def cb_an_set_schedule(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_schedule_time)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:schedule_menu")]])
    await safe_edit(cb.message, tr(lang, "an_schedule_ask"), kb)


@router.message(Flow.a_announce_schedule_time, F.text)
async def msg_an_sched_time(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    val = (message.text or "").strip()
    try:
        ts = time.mktime(time.strptime(val, "%Y-%m-%d %H:%M"))
        if ts < now_ts():
            await message.answer(tr(lang, "schedule_future_required"))
            return
    except Exception:
        await message.answer(tr(lang, "schedule_format"))
        return
    db_set("announce_schedule", val)
    db_set("announce_schedule_ts", str(ts))
    await state.clear()
    await message.answer(f"✅ {esc(val)}")


@router.callback_query(F.data == "an:clear_schedule")
async def cb_an_clear_sched(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    db_set("announce_schedule", "")
    db_set("announce_schedule_ts", "0")
    db_set("announce_scheduled_payload", "")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:test")
async def cb_an_test(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_test)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:users_menu")]])
    await safe_edit(cb.message, tr(lang, "an_test_ask"), kb)


@router.message(Flow.a_announce_test, F.text)
async def msg_an_test(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    txt = (message.text or "").strip()
    with contextlib.suppress(Exception):
        await c.bot.send_message(message.chat.id, f"🧪 {esc(txt)}")
    await state.clear()


@router.callback_query(F.data == "an:reset_stats")
async def cb_an_reset_stats(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    db_set("announce_total_sent", "0")
    db_set("announce_total_failed", "0")
    await cb.answer("✅")
    await _render_an_users(cb, c)


@router.callback_query(F.data == "an:stats")
async def cb_an_stats(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    try:
        ts = int(db_get("announce_total_sent", "0") or "0")
        tf = int(db_get("announce_total_failed", "0") or "0")
        ct = int(db_get("announce_channel_total", "0") or "0")
    except Exception:
        ts = tf = ct = 0
    try:
        total = UserRepo.count_all()
        vip = UserRepo.count_vip()
        active = int(get_conn().execute(
            "SELECT COUNT(*) AS c FROM users WHERE downloads>0").fetchone()["c"] or 0)
        inactive = int(get_conn().execute(
            "SELECT COUNT(*) AS c FROM users WHERE downloads=0").fetchone()["c"] or 0)
    except Exception:
        total = vip = active = inactive = 0
    text = tr(lang, "an_stats_title", sent=ts, failed=tf, ch_sent=ct,
              total=total, vip=vip, active=active, inactive=inactive)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="admin:announce")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data == "an:history")
async def cb_an_history(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    rows = get_conn().execute(
        "SELECT * FROM logs WHERE action IN "
        "('announce_sent', 'announce_channel') "
        "ORDER BY created_at DESC LIMIT 25").fetchall()
    text = "📜\n\n"
    if not rows:
        text += "📭"
    else:
        for r in rows:
            text += f"• {fmt_time(r['created_at'])}\n<code>{esc(str(r['details'] or '')[:80])}</code>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="admin:announce")]])
    await safe_edit(cb.message, text, kb)


# ══════════════════════════════════════════════════════════════
# ANNOUNCE — CHANNEL
# ══════════════════════════════════════════════════════════════
async def _render_an_channel(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    ch_id = db_get("announce_channel_id", "") or "—"
    enabled = db_get("announce_channel_enabled", "0") == "1"
    pin = "✅" if db_get("announce_channel_pin", "0") == "1" else "❌"
    silent = "✅" if db_get("announce_channel_silent", "0") == "1" else "❌"
    st = tr(lang, "active") if enabled else tr(lang, "disabled")
    try:
        total = int(db_get("announce_channel_total", "0") or "0")
    except Exception:
        total = 0
    last_ts = db_get("announce_channel_last_ts", "0")
    try:
        last_str = fmt_time(float(last_ts)) if float(last_ts or 0) > 0 else "—"
    except Exception:
        last_str = "—"

    text = tr(lang, "an_channel_title", status=st, channel=esc(ch_id),
              pin=pin, silent=silent, total=total, last=last_str)

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_set"),
                              callback_data="anc:set"),
        InlineKeyboardButton(text=tr(lang, "an_btn_enable"),
                              callback_data="anc:toggle"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_pin", v=pin),
                              callback_data="anc:pin"),
        InlineKeyboardButton(text=tr(lang, "an_btn_silent", v=silent),
                              callback_data="anc:silent"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_text"),
                              callback_data="anc:send_text"),
        InlineKeyboardButton(text=tr(lang, "an_btn_media"),
                              callback_data="anc:send_media"))
    b.row(
        InlineKeyboardButton(text=tr(lang, "an_btn_forward"),
                              callback_data="anc:send_forward"),
        InlineKeyboardButton(text=tr(lang, "an_btn_test"),
                              callback_data="anc:test"))
    b.row(InlineKeyboardButton(text=tr(lang, "an_btn_reset"),
                                callback_data="anc:reset_stats"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:announce"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "an:channel_menu")
async def cb_an_channel_menu(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:set")
async def cb_anc_set(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_announce_channel_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:channel_menu")]])
    await safe_edit(cb.message, tr(lang, "an_set_ch_ask"), kb)


@router.message(Flow.a_announce_channel_id, F.text)
async def msg_anc_set(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    val = (message.text or "").strip()
    if not val:
        await message.answer("⚠️")
        return
    try:
        if val.lstrip("-").isdigit():
            target = int(val)
        else:
            target = "@" + val.lstrip("@")
        chat = await c.bot.get_chat(target)
        me = await c.bot.get_me()
        member = await c.bot.get_chat_member(chat.id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(tr(lang, "an_bot_not_admin"))
            return
        db_set("announce_channel_id", str(chat.id))
        db_set("announce_channel_enabled", "1")
        await state.clear()
        await message.answer(
            f"✅ <b>{esc(chat.title or '')}</b>\n<code>{chat.id}</code>")
    except Exception as e:
        await message.answer(f"❌ <code>{esc(str(e)[:200])}</code>")


@router.callback_query(F.data == "anc:toggle")
async def cb_anc_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_channel_enabled", "0")
    db_set("announce_channel_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:pin")
async def cb_anc_pin(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_channel_pin", "0")
    db_set("announce_channel_pin", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:silent")
async def cb_anc_silent(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("announce_channel_silent", "0")
    db_set("announce_channel_silent", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:send_text")
async def cb_anc_send_text(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    lang = await _admin_lang(c, cb.from_user.id)
    if not db_get("announce_channel_id", ""):
        await cb.answer(tr(lang, "an_ch_empty"), show_alert=True)
        return
    await cb.answer()
    await state.set_state(Flow.a_anc_text)
    await state.update_data(anc_text=None, anc_media=None, anc_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:channel_menu")]])
    await safe_edit(cb.message, tr(lang, "an_text_ask"), kb)


@router.message(Flow.a_anc_text, F.text)
async def msg_anc_text(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    text = (message.text or "").strip()
    if not text:
        await message.answer("⚠️")
        return
    await state.update_data(anc_text=text, anc_kind="text")
    await state.set_state(Flow.a_anc_confirm)
    await _show_channel_preview(message, c, lang, text=text)


@router.callback_query(F.data == "anc:send_media")
async def cb_anc_send_media(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    lang = await _admin_lang(c, cb.from_user.id)
    if not db_get("announce_channel_id", ""):
        await cb.answer(tr(lang, "an_ch_empty"), show_alert=True)
        return
    await cb.answer()
    await state.set_state(Flow.a_anc_media)
    await state.update_data(anc_kind="media", anc_text=None,
                            anc_media=None, anc_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:channel_menu")]])
    await safe_edit(cb.message, tr(lang, "an_media_ask"), kb)


@router.message(Flow.a_anc_media)
async def msg_anc_media(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    data = await state.get_data()
    kind = data.get("anc_kind", "media")
    if kind == "forward":
        fwd = {"from_chat_id": message.chat.id,
               "message_id": message.message_id}
        await state.update_data(anc_forward=fwd)
        await state.set_state(Flow.a_anc_confirm)
        await _show_channel_preview(message, c, lang,
                                     text=tr(lang, "an_btn_forward"))
        return
    media = None
    if message.photo:
        media = {"type": "photo", "file_id": message.photo[-1].file_id,
                 "caption": message.caption or ""}
    elif message.video:
        media = {"type": "video", "file_id": message.video.file_id,
                 "caption": message.caption or ""}
    elif message.document:
        media = {"type": "document", "file_id": message.document.file_id,
                 "caption": message.caption or ""}
    elif message.audio:
        media = {"type": "audio", "file_id": message.audio.file_id,
                 "caption": message.caption or ""}
    elif message.animation:
        media = {"type": "animation", "file_id": message.animation.file_id,
                 "caption": message.caption or ""}
    else:
        await message.answer("⚠️")
        return
    await state.update_data(anc_media=media)
    await state.set_state(Flow.a_anc_confirm)
    await _show_channel_preview(message, c, lang, media=media)


@router.callback_query(F.data == "anc:send_forward")
async def cb_anc_forward(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    lang = await _admin_lang(c, cb.from_user.id)
    if not db_get("announce_channel_id", ""):
        await cb.answer(tr(lang, "an_ch_empty"), show_alert=True)
        return
    await cb.answer()
    await state.set_state(Flow.a_anc_media)
    await state.update_data(anc_kind="forward", anc_text=None,
                            anc_media=None, anc_forward=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:channel_menu")]])
    await safe_edit(cb.message, tr(lang, "an_forward_ask"), kb)


async def _show_channel_preview(target, c, lang, text=None, media=None):
    ch = db_get("announce_channel_id", "—")
    pin = "✅" if db_get("announce_channel_pin", "0") == "1" else "❌"
    silent = "✅" if db_get("announce_channel_silent", "0") == "1" else "❌"
    body = (tr(lang, "an_preview_title", channel=esc(ch)) + "\n")
    if text:
        body += f"📝 <blockquote>{esc(text[:600])}</blockquote>\n"
    if media:
        body += f"📎 {media.get('type', '?')}\n"
        if media.get("caption"):
            body += f"💬 <blockquote>{esc(media['caption'][:400])}</blockquote>\n"
    body += (f"━━━━━━━━━━━━━━━━━━━━━\n📌 {pin}  |  🔇 {silent}\n"
             f"{tr(lang, 'an_send_confirm')}")
    b = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "an_send_btn"),
                              callback_data="anc:confirm")],
        [InlineKeyboardButton(text=tr(lang, "an_cancel_btn"),
                              callback_data="anc:abort")]])
    if isinstance(target, Message):
        await target.answer(body, reply_markup=b)
    else:
        await safe_edit(target, body, b)


@router.callback_query(F.data == "anc:abort")
async def cb_anc_abort(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer("❌")
    await state.clear()
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:confirm")
async def cb_anc_confirm(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    data = await state.get_data()
    text = data.get("anc_text") or ""
    media = data.get("anc_media") or {}
    forward = data.get("anc_forward") or None
    await state.clear()
    ch = db_get("announce_channel_id", "")
    if not ch:
        await cb.answer("⚠️", show_alert=True)
        return
    await cb.answer("📤...")
    silent = db_get("announce_channel_silent", "0") == "1"
    pin = db_get("announce_channel_pin", "0") == "1"
    try:
        target = int(ch) if ch.lstrip("-").isdigit() else ch
        sent_msg = None
        if forward:
            sent_msg = await c.bot.copy_message(
                chat_id=target, from_chat_id=forward["from_chat_id"],
                message_id=forward["message_id"],
                disable_notification=silent)
        elif media:
            t = media.get("type")
            cap = (media.get("caption") or "")[:1024]
            if t == "photo":
                sent_msg = await c.bot.send_photo(
                    target, media["file_id"], caption=cap,
                    disable_notification=silent)
            elif t == "video":
                sent_msg = await c.bot.send_video(
                    target, media["file_id"], caption=cap,
                    disable_notification=silent)
            elif t == "document":
                sent_msg = await c.bot.send_document(
                    target, media["file_id"], caption=cap,
                    disable_notification=silent)
            elif t == "audio":
                sent_msg = await c.bot.send_audio(
                    target, media["file_id"], caption=cap,
                    disable_notification=silent)
            elif t == "animation":
                sent_msg = await c.bot.send_animation(
                    target, media["file_id"], caption=cap,
                    disable_notification=silent)
        else:
            sent_msg = await send_text_safe(
                c.bot, target, text, disable_notification=silent)

        if pin and sent_msg:
            with contextlib.suppress(Exception):
                await c.bot.pin_chat_message(
                    target, sent_msg.message_id, disable_notification=True)

        db_set("announce_channel_last_ts", str(now_ts()))
        try:
            prev = int(db_get("announce_channel_total", "0") or "0")
            db_set("announce_channel_total", str(prev + 1))
        except Exception:
            pass
        db_log(cb.from_user.id, "announce_channel", f"ch={ch}")
        lang = await _admin_lang(c, cb.from_user.id)
        await safe_edit(cb.message,
            f"{tr(lang, 'an_sent_ok')}\n📢 <code>{esc(ch)}</code>")
    except Exception as e:
        await safe_edit(cb.message,
            f"❌ <code>{esc(str(e)[:300])}</code>")


@router.callback_query(F.data == "anc:reset_stats")
async def cb_anc_reset_stats(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    db_set("announce_channel_total", "0")
    await cb.answer("✅")
    await _render_an_channel(cb, c)


@router.callback_query(F.data == "anc:test")
async def cb_anc_test(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    lang = await _admin_lang(c, cb.from_user.id)
    if not db_get("announce_channel_id", ""):
        await cb.answer(tr(lang, "an_ch_empty"), show_alert=True)
        return
    await cb.answer()
    await state.set_state(Flow.a_anc_test)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️", callback_data="an:channel_menu")]])
    await safe_edit(cb.message, tr(lang, "an_test_ask"), kb)


@router.message(Flow.a_anc_test, F.text)
async def msg_anc_test(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    txt = (message.text or "").strip()
    if not txt:
        await message.answer("⚠️")
        return
    ch = db_get("announce_channel_id", "")
    try:
        target = int(ch) if ch.lstrip("-").isdigit() else ch
        await c.bot.send_message(target, f"🧪 <b>...</b>\n\n{esc(txt)}")
        await message.answer("✅")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ {esc(str(e)[:200])}")


# ══════════════════════════════════════════════════════════════
# ADMIN — MINIAPP
# ══════════════════════════════════════════════════════════════
async def _render_miniapp_panel(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    st = tr(lang, "active") if db_get("miniapp_enabled", "0") == "1" else tr(lang, "disabled")
    url = db_get("miniapp_url", "") or "-"
    text = tr(lang, "ad_ma_title", status=st, url=esc(url))
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "ad_ma_set_url"),
                                callback_data="ma:set"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_ma_toggle"),
                                callback_data="ma:toggle"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:miniapp")
async def cb_admin_miniapp(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await _render_miniapp_panel(cb, c)


@router.callback_query(F.data == "ma:set")
async def cb_ma_set(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.a_miniapp_url)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:miniapp")]])
    await safe_edit(cb.message, tr(lang, "ad_ma_ask_url"), kb)


@router.message(Flow.a_miniapp_url, F.text)
async def msg_ma_url(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    val = (message.text or "").strip()
    if not val.startswith("http"):
        await message.answer("⚠️")
        return
    db_set("miniapp_url", val)
    await state.clear()
    await message.answer("✅")


@router.callback_query(F.data == "ma:toggle")
async def cb_ma_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("miniapp_enabled", "0")
    db_set("miniapp_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    await _render_miniapp_panel(cb, c)


# ══════════════════════════════════════════════════════════════
# ADMIN — STYLE
# ══════════════════════════════════════════════════════════════
async def _render_style_panel(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    premium_yn = "✅" if db_get("premium_emoji_enabled", "1") == "1" else "❌"
    map_count = emoji_map_count()
    text = tr(lang, "style_title", premium=premium_yn,
              map_count=map_count, total_btns=MenuButtonRepo.count_all())
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=f"{tr(lang, 'style_emoji_map')} ({map_count})",
        callback_data="style:emoji_map"))
    b.row(InlineKeyboardButton(
        text=f"{tr(lang, 'style_premium_toggle')}: {premium_yn}",
        callback_data="style:premium_toggle"))
    b.row(InlineKeyboardButton(text=tr(lang, "style_start_emoji"),
                                callback_data="style:start_emoji"))
    b.row(InlineKeyboardButton(text=tr(lang, "style_start_sticker"),
                                callback_data="style:start_sticker"))
    b.row(InlineKeyboardButton(text=tr(lang, "style_reset_all"),
                                callback_data="style:reset_colors"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:style")
async def cb_admin_style(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    await _render_style_panel(cb, c)


@router.callback_query(F.data == "style:premium_toggle")
async def cb_style_premium_toggle(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("premium_emoji_enabled", "1")
    db_set("premium_emoji_enabled", "0" if cur == "1" else "1")
    invalidate_emoji_cache()
    await cb.answer("✅")
    await _render_style_panel(cb, c)


@router.callback_query(F.data == "style:reset_colors")
async def cb_style_reset_colors(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    get_conn().execute("UPDATE menu_buttons SET color='default'")
    await cb.answer("✅", show_alert=True)
    await _render_style_panel(cb, c)


# ══════════════════════════════════════════════════════════════
# EMOJI MAP
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "style:emoji_map")
async def cb_style_emoji_map(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await render_emoji_map(cb, c)


async def render_emoji_map(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    count = emoji_map_count()
    enabled = db_get("premium_emoji_enabled", "1") == "1"
    status = tr(lang, "active") if enabled else tr(lang, "disabled")
    text = tr(lang, "em_title", count=count, status=status)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "em_add"),
                                callback_data="em:add"))
    b.row(InlineKeyboardButton(text=tr(lang, "em_list"),
                                callback_data="em:list"))
    b.row(InlineKeyboardButton(text=tr(lang, "em_clear"),
                                callback_data="em:clear"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:style"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "em:add")
async def cb_em_add(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.emoji_add_premium)
    await state.update_data(premium_list=[])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "cancel"),
                             callback_data="style:emoji_map")]])
    await safe_edit(cb.message, tr(lang, "em_step1"), kb)


@router.message(Flow.emoji_add_premium)
async def msg_em_premium(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    prems = extract_premium_emojis(message)
    if not prems:
        await message.answer(tr(lang, "em_need_premium"))
        return
    await state.update_data(premium_list=prems)
    await state.set_state(Flow.emoji_add_normal)
    preview = "\n".join(
        f"{i+1}. <tg-emoji emoji-id=\"{eid}\">{fb}</tg-emoji>"
        for i, (eid, fb) in enumerate(prems[:20]))
    await message.answer(
        f"✅ {len(prems)}\n\n{preview}\n\n"
        f"{tr(lang, 'normal_emojis_prompt')}")


@router.message(Flow.emoji_add_normal, F.text)
async def msg_em_normal(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    prems = data.get("premium_list") or []
    if not prems:
        await state.clear()
        return
    norms = extract_normal_emojis(message.text or "")
    if not norms:
        await message.answer("⚠️")
        return
    count = min(len(prems), len(norms))
    for i in range(count):
        eid, fb = prems[i]
        get_conn().execute(
            """INSERT INTO emoji_map(normal_emoji, premium_id,
               fallback_emoji, created_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(normal_emoji) DO UPDATE SET
                 premium_id=excluded.premium_id,
                 fallback_emoji=excluded.fallback_emoji,
                 created_at=excluded.created_at""",
            (norms[i], eid, fb, now_ts()))
    invalidate_emoji_cache()
    await state.clear()
    await message.answer(f"✅ {count}")


@router.callback_query(F.data == "em:list")
async def cb_em_list(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    rows = get_conn().execute(
        "SELECT * FROM emoji_map ORDER BY created_at DESC LIMIT 30").fetchall()
    text = "📋\n\n"
    for r in rows:
        text += (f"{r['normal_emoji']} → "
                 f"<tg-emoji emoji-id=\"{r['premium_id']}\">"
                 f"{r['fallback_emoji']}</tg-emoji>\n")
    if not rows:
        text += "📭"
    b = InlineKeyboardBuilder()
    for r in rows[:15]:
        b.row(InlineKeyboardButton(
            text=f"🗑 {r['normal_emoji']}",
            callback_data=safe_cb(f"em:del:{r['normal_emoji']}")))
    b.row(InlineKeyboardButton(text="◀️", callback_data="style:emoji_map"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data.startswith("em:del:"))
async def cb_em_del(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    normal = cb.data[len("em:del:"):]
    get_conn().execute("DELETE FROM emoji_map WHERE normal_emoji=?", (normal,))
    invalidate_emoji_cache()
    await cb.answer("🗑", show_alert=True)
    await cb_em_list(cb, c)


@router.callback_query(F.data == "em:clear")
async def cb_em_clear(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    count = emoji_map_count()
    if count == 0:
        await cb.answer("📭", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="em:clear:yes")],
        [InlineKeyboardButton(text="❌", callback_data="style:emoji_map")]])
    await safe_edit(cb.message, f"⚠️ {count}", kb)
    await cb.answer()


@router.callback_query(F.data == "em:clear:yes")
async def cb_em_clear_yes(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    count = emoji_map_count()
    get_conn().execute("DELETE FROM emoji_map")
    invalidate_emoji_cache()
    await cb.answer(f"🧹 {count}", show_alert=True)
    await cb_style_emoji_map(cb, c)


# ══════════════════════════════════════════════════════════════
# START EMOJI / STICKER
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "style:start_emoji")
async def cb_style_start_emoji(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.start_emoji)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "cancel"),
                             callback_data="admin:style")]])
    await safe_edit(cb.message, tr(lang, "start_emoji_title"), kb)


@router.message(Flow.start_emoji)
async def msg_start_emoji(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    prems = extract_premium_emojis(message)
    if prems:
        eid, fb = prems[0]
        db_set("start_emoji_id", eid)
        db_set("start_emoji_fb", fb)
        db_set("start_emoji_kind", "premium")
        await state.clear()
        await message.answer("✅")
        return
    txt = message.text or message.caption or ""
    norms = extract_normal_emojis(txt)
    if norms:
        db_set("start_emoji_id", norms[0])
        db_set("start_emoji_fb", norms[0])
        db_set("start_emoji_kind", "normal")
        await state.clear()
        await message.answer("✅")
        return
    await message.answer("⚠️")


def _build_sticker_panel(lang):
    sid = db_get("start_sticker_file_id", "")
    enabled = db_get("start_sticker_enabled", "1") == "1"
    status = tr(lang, "active") if enabled else tr(lang, "disabled")
    text = tr(lang, "start_sticker_title", status=status)
    if sid:
        text += f"\n\n📎 <code>{sid[:60]}...</code>"
    else:
        text += f"\n\n{tr(lang, 'start_sticker_not_set')}"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "toggle"),
                                callback_data="sticker:toggle"))
    b.row(InlineKeyboardButton(text=tr(lang, "delete"),
                                callback_data="sticker:delete"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:style"))
    return text, b.as_markup()


@router.callback_query(F.data == "style:start_sticker")
async def cb_style_start_sticker(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.start_sticker)
    text, kb = _build_sticker_panel(lang)
    await safe_edit(cb.message, text, kb)


@router.message(Flow.start_sticker, F.sticker)
async def msg_start_sticker(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    db_set("start_sticker_file_id", message.sticker.file_id)
    db_set("start_sticker_enabled", "1")
    await state.clear()
    await message.answer("✅")


@router.message(Flow.start_sticker)
async def msg_start_sticker_bad(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️")


@router.callback_query(F.data == "sticker:toggle")
async def cb_sticker_toggle(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    cur = db_get("start_sticker_enabled", "1")
    db_set("start_sticker_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅")
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.start_sticker)
    text, kb = _build_sticker_panel(lang)
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data == "sticker:delete")
async def cb_sticker_delete(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    db_set("start_sticker_file_id", "")
    await cb.answer("🗑", show_alert=True)
    await _render_style_panel(cb, c)


# ══════════════════════════════════════════════════════════════
# BUTTONS — HUB
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:buttons")
async def cb_admin_buttons(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    total = MenuButtonRepo.count_all()
    text = tr(lang, "btns_title", total=total)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "btns_user_menu"),
                                callback_data="style:menu:user"))
    b.row(InlineKeyboardButton(text=tr(lang, "btns_admin_menu"),
                                callback_data="style:menu:admin"))
    b.row(InlineKeyboardButton(text=tr(lang, "btns_custom"),
                                callback_data="admin:custom_buttons"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, text, b.as_markup())


# ══════════════════════════════════════════════════════════════
# BUTTONS — MENU EDITOR
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("style:menu:"))
async def cb_style_menu(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    scope = cb.data.rsplit(":", 1)[1]
    if scope not in ("user", "admin"):
        return
    await render_menu_editor(cb, c, scope)


async def render_menu_editor(cb: CallbackQuery, c: Container, scope: str):
    lang = await _admin_lang(c, cb.from_user.id)
    rows = MenuButtonRepo.by_scope(scope, visible_only=False)
    try:
        cols = int(db_get(f"menu_cols_{scope}", "2"))
    except ValueError:
        cols = 2
    if cols not in (1, 2, 3, 4):
        cols = 2

    group_label = (tr(lang, "menu_user") if scope == "user"
                   else tr(lang, "menu_admin"))
    text = (
        f"🎛 <b>{tr(lang, 'mn_edit_label')}</b>\n"
        f"📂 {group_label}\n"
        f"🔢 {len(rows)}  |  📊 {cols}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    b = InlineKeyboardBuilder()
    for r in rows:
        vis = "✅" if r["is_visible"] else "🚫"
        ci = {"default": "⚪", "success": "🟢",
              "danger": "🔴", "primary": "🔵"}.get(r["color"] or "default", "⚪")
        ei = "💎" if r["emoji_id"] else ""
        if r["label"]:
            label = r["label"]
        else:
            key = r["btn_key"]
            lk = (MenuButtonRepo.DEFAULTS_USER if scope == "user"
                  else MenuButtonRepo.DEFAULTS_ADMIN).get(key, ("back", ""))[0]
            label = tr(lang, lk)
        b.row(InlineKeyboardButton(
            text=f"{vis}{ci}{ei} {label[:40]}",
            callback_data=safe_cb(f"mn:edit:{scope}:{r['btn_key']}")))

    col_row = []
    for n in (1, 2, 3, 4):
        mark = " ✅" if cols == n else ""
        col_row.append(InlineKeyboardButton(
            text=f"{n}{mark}",
            callback_data=safe_cb(f"mn:setcols:{scope}:{n}")))
    b.row(*col_row)

    b.row(
        InlineKeyboardButton(text=tr(lang, "mn_show_all"),
                              callback_data=safe_cb(f"mn:allvis:{scope}")),
        InlineKeyboardButton(text=tr(lang, "mn_hide_all"),
                              callback_data=safe_cb(f"mn:allhide:{scope}")))
    b.row(InlineKeyboardButton(text=tr(lang, "mn_reset_all"),
                                callback_data=safe_cb(f"mn:resetall:{scope}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:buttons"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data.startswith("mn:setcols:"))
async def cb_mn_setcols(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer()
        return
    _, _, scope, n = parts
    if scope not in ("user", "admin") or n not in ("1", "2", "3", "4"):
        await cb.answer()
        return
    db_set(f"menu_cols_{scope}", n)
    await cb.answer("✅")
    await render_menu_editor(cb, c, scope)


@router.callback_query(F.data.startswith("mn:allvis:"))
async def cb_mn_allvis(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    scope = cb.data.rsplit(":", 1)[1]
    get_conn().execute("UPDATE menu_buttons SET is_visible=1 WHERE scope=?",
                        (scope,))
    await cb.answer("✅")
    await render_menu_editor(cb, c, scope)


@router.callback_query(F.data.startswith("mn:allhide:"))
async def cb_mn_allhide(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    scope = cb.data.rsplit(":", 1)[1]
    get_conn().execute("UPDATE menu_buttons SET is_visible=0 WHERE scope=?",
                        (scope,))
    await cb.answer("✅")
    await render_menu_editor(cb, c, scope)


@router.callback_query(F.data.startswith("mn:resetall:"))
async def cb_mn_resetall(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    scope = cb.data.rsplit(":", 1)[1]
    get_conn().execute(
        """UPDATE menu_buttons SET label=NULL, color='default',
           emoji_id=NULL, emoji_fb=NULL, is_visible=1
           WHERE scope=?""", (scope,))
    await cb.answer("✅")
    await render_menu_editor(cb, c, scope)


@router.callback_query(F.data.startswith("mn:edit:"))
async def cb_menu_edit(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    await state.update_data(scope=scope, key=key)
    await render_edit_panel(cb, c, scope, key)


async def render_edit_panel(cb, c, scope, key):
    lang = await _admin_lang(c, cb.from_user.id)
    row = MenuButtonRepo.get(scope, key)
    if not row:
        return
    if row["label"]:
        label = row["label"]
    else:
        lk = (MenuButtonRepo.DEFAULTS_USER if scope == "user"
              else MenuButtonRepo.DEFAULTS_ADMIN).get(key, ("back", ""))[0]
        label = tr(lang, lk)
    group_label = tr(lang, "menu_user") if scope == "user" else tr(lang, "menu_admin")
    cmap = {"default": tr(lang, "mn_color_default_lbl"),
            "success": tr(lang, "mn_color_success_lbl"),
            "danger": tr(lang, "mn_color_danger_lbl"),
            "primary": tr(lang, "mn_color_primary_lbl")}
    color_text = cmap.get(row["color"] or "default", tr(lang, "mn_color_default_lbl"))
    vis_text = tr(lang, "mn_vis_active") if row["is_visible"] else tr(lang, "mn_vis_hidden")
    emoji_text = "—"
    if row["emoji_id"]:
        emoji_text = (f'<tg-emoji emoji-id="{row["emoji_id"]}">'
                      f'{row["emoji_fb"] or "✨"}</tg-emoji>')
    text = (
        f"✏️ <b>{tr(lang, 'mn_edit_label')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 {tr(lang, 'mn_group_label')}: <b>{group_label}</b>\n"
        f"🔑 <code>{esc(key)}</code>\n"
        f"📝 {tr(lang, 'mn_title_label')}: {esc(label[:60])}\n"
        f"🎨 {tr(lang, 'mn_color_label')}: {color_text}\n"
        f"👁 {tr(lang, 'mn_status_label')}: {vis_text}\n"
        f"💎 {tr(lang, 'mn_emoji_label')}: {emoji_text}"
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=tr(lang, "mv_up"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:up")),
        InlineKeyboardButton(text=tr(lang, "mv_down"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:down")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "mv_left"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:left")),
        InlineKeyboardButton(text=tr(lang, "mv_right"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:right")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "mv_top"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:top")),
        InlineKeyboardButton(text=tr(lang, "mv_bottom"),
                              callback_data=safe_cb(f"mn:mv:{scope}:{key}:bottom")))
    b.row(InlineKeyboardButton(text=tr(lang, "mn_edit_label"),
                                callback_data=safe_cb(f"mn:lbl:{scope}:{key}")))
    b.row(InlineKeyboardButton(text=tr(lang, "mn_set_emoji"),
                                callback_data=safe_cb(f"mn:emoji:{scope}:{key}")),
          InlineKeyboardButton(text=tr(lang, "mn_remove_emoji"),
                                callback_data=safe_cb(f"mn:emoji_del:{scope}:{key}")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "mn_color_success_lbl"),
                              callback_data=safe_cb(f"mn:color:{scope}:{key}:success")),
        InlineKeyboardButton(text=tr(lang, "mn_color_danger_lbl"),
                              callback_data=safe_cb(f"mn:color:{scope}:{key}:danger")))
    b.row(
        InlineKeyboardButton(text=tr(lang, "mn_color_primary_lbl"),
                              callback_data=safe_cb(f"mn:color:{scope}:{key}:primary")),
        InlineKeyboardButton(text=tr(lang, "mn_color_default_lbl"),
                              callback_data=safe_cb(f"mn:color:{scope}:{key}:default")))
    b.row(InlineKeyboardButton(text=tr(lang, "mn_toggle_vis"),
                                callback_data=safe_cb(f"mn:vis:{scope}:{key}")))
    b.row(InlineKeyboardButton(text=tr(lang, "mn_reset"),
                                callback_data=safe_cb(f"mn:reset:{scope}:{key}")))
    b.row(InlineKeyboardButton(text=tr(lang, "back"),
                                callback_data=safe_cb(f"style:menu:{scope}")))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data.startswith("mn:mv:"))
async def cb_mn_move(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 5:
        await cb.answer()
        return
    _, _, scope, key, direction = parts
    ok = MenuButtonRepo.move(scope, key, direction)
    await cb.answer("✅" if ok else "❌")
    await render_edit_panel(cb, c, scope, key)


@router.callback_query(F.data.startswith("mn:lbl:"))
async def cb_menu_label(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.mn_label)
    await state.update_data(scope=scope, key=key)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"),
                             callback_data=safe_cb(f"mn:edit:{scope}:{key}"))]])
    await safe_edit(cb.message, tr(lang, "mn_set_label_ask"), kb)


@router.message(Flow.mn_label, F.text)
async def msg_mn_label(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    scope = data.get("scope")
    key = data.get("key")
    if not scope or not key:
        await state.clear()
        return
    val = (message.text or "").strip()
    if val == "-":
        MenuButtonRepo.update(scope, key, label=None)
    else:
        MenuButtonRepo.update(scope, key, label=val)
    await state.clear()
    await message.answer("✅")


@router.callback_query(F.data.startswith("mn:emoji_del:"))
async def cb_menu_emoji_del(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    MenuButtonRepo.update(scope, key, emoji_id=None, emoji_fb=None)
    await cb.answer("🗑", show_alert=True)
    await render_edit_panel(cb, c, scope, key)


@router.callback_query(F.data.startswith("mn:emoji:"))
async def cb_menu_emoji(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.mn_emoji)
    await state.update_data(scope=scope, key=key)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"),
                             callback_data=safe_cb(f"mn:edit:{scope}:{key}"))]])
    await safe_edit(cb.message, tr(lang, "mn_set_emoji_ask"), kb)


@router.message(Flow.mn_emoji)
async def msg_mn_emoji(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    scope = data.get("scope")
    key = data.get("key")
    if not scope or not key:
        await state.clear()
        return
    prems = extract_premium_emojis(message)
    if not prems:
        await message.answer("⚠️")
        return
    eid, fb = prems[0]
    MenuButtonRepo.update(scope, key, emoji_id=eid, emoji_fb=fb)
    await state.clear()
    await message.answer("✅")


@router.callback_query(F.data.startswith("mn:color:"))
async def cb_menu_color(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 5:
        return
    _, _, scope, key, color = parts
    MenuButtonRepo.set_color(scope, key, color)
    await cb.answer("✅")
    await render_edit_panel(cb, c, scope, key)


@router.callback_query(F.data.startswith("mn:vis:"))
async def cb_menu_vis(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    MenuButtonRepo.toggle_visible(scope, key)
    await cb.answer("✅")
    await render_edit_panel(cb, c, scope, key)


@router.callback_query(F.data.startswith("mn:reset:"))
async def cb_menu_reset(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    parts = cb.data.split(":")
    if len(parts) != 4:
        return
    _, _, scope, key = parts
    MenuButtonRepo.reset(scope, key)
    await cb.answer("♻️", show_alert=True)
    await render_edit_panel(cb, c, scope, key)


# ══════════════════════════════════════════════════════════════
# CUSTOM BUTTONS
# ══════════════════════════════════════════════════════════════
async def _render_custom_buttons(cb: CallbackQuery, c: Container):
    lang = await _admin_lang(c, cb.from_user.id)
    rows = get_conn().execute(
        "SELECT * FROM custom_buttons WHERE is_active=1 ORDER BY row_order, id"
    ).fetchall()
    text = tr(lang, "cbtn_title") + "\n\n"
    if not rows:
        text += tr(lang, "cbtn_empty")
    else:
        for i, r in enumerate(rows, 1):
            text += f"{i}. {esc(r['label'])} → <code>{esc(r['callback'])}</code>\n"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "cbtn_add"),
                                callback_data="cbtn:add"))
    for r in rows[:10]:
        b.row(InlineKeyboardButton(
            text=f"🗑 {r['label'][:25]}",
            callback_data=safe_cb(f"cbtn:del:{r['id']}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:buttons"))
    await safe_edit(cb.message, text, b.as_markup())


@router.callback_query(F.data == "admin:custom_buttons")
async def cb_admin_custom_buttons(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    await _render_custom_buttons(cb, c)


@router.callback_query(F.data == "cbtn:add")
async def cb_cbtn_add(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.cbtn_label)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_back"),
                             callback_data="admin:custom_buttons")]])
    await safe_edit(cb.message, tr(lang, "cbtn_ask_label"), kb)


@router.message(Flow.cbtn_label, F.text)
async def msg_cbtn_label(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    val = (message.text or "").strip()
    if not val:
        await message.answer("⚠️")
        return
    await state.update_data(cbtn_label=val)
    await state.set_state(Flow.cbtn_callback)
    await message.answer(tr(lang, "callback_data_prompt"))


@router.message(Flow.cbtn_callback, F.text)
async def msg_cbtn_cb(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    label = data.get("cbtn_label")
    cb_data = (message.text or "").strip()
    if not label or not cb_data:
        await state.clear()
        return
    get_conn().execute(
        """INSERT INTO custom_buttons(label, callback, is_active, created_at)
           VALUES (?, ?, 1, ?)""", (label, cb_data, now_ts()))
    await state.clear()
    await message.answer("✅")


@router.callback_query(F.data.startswith("cbtn:del:"))
async def cb_cbtn_del(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    try:
        bid = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    get_conn().execute("DELETE FROM custom_buttons WHERE id=?", (bid,))
    await cb.answer("🗑", show_alert=True)
    await _render_custom_buttons(cb, c)


# ══════════════════════════════════════════════════════════════
# TEXTS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:texts")
async def cb_admin_texts(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await state.clear()
    lang = await _admin_lang(c, cb.from_user.id)
    b = InlineKeyboardBuilder()
    for key in TEXT_KEYS:
        current = db_get(f"custom_text_{key}", "")
        marker = "✅" if current else "⚪"
        label = text_label(lang, key)
        b.row(InlineKeyboardButton(
            text=f"{marker} {label}",
            callback_data=safe_cb(f"txt:edit:{key}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    await safe_edit(cb.message, tr(lang, "texts_title"), b.as_markup())


@router.callback_query(F.data.startswith("txt:edit:"))
async def cb_txt_edit(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    key = cb.data[len("txt:edit:"):]
    if not key:
        await cb.answer()
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    custom = db_get(f"custom_text_{key}", "")
    current = custom if custom else tr(lang, key)
    label = text_label(lang, key)
    status = tr(lang, "texts_custom_status") if custom else tr(lang, "texts_default_status")

    await state.set_state(Flow.text_value)
    await state.update_data(text_key=key)

    info = (f"📝 <b>{esc(label)}</b>  <i>({status})</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{esc(current[:600])}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tr(lang, 'texts_ask_new')}")

    b = InlineKeyboardBuilder()
    if custom:
        b.row(InlineKeyboardButton(
            text=tr(lang, "texts_reset_btn"),
            callback_data=safe_cb(f"txt:reset:{key}")))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:texts"))
    await safe_edit(cb.message, info, b.as_markup())


@router.callback_query(F.data.startswith("txt:reset:"))
async def cb_txt_reset(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    key = cb.data[len("txt:reset:"):]
    lang = await _admin_lang(c, cb.from_user.id)
    get_conn().execute("DELETE FROM settings WHERE key=?",
                       (f"custom_text_{key}",))
    await cb.answer(tr(lang, "texts_reset_ok"), show_alert=True)
    await state.clear()
    await cb_admin_texts(cb, state, c)


@router.message(Flow.text_value, F.text)
async def msg_txt_edit(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("text_key")
    if not key:
        await state.clear()
        return
    val = (message.text or "").strip()
    if not val:
        await message.answer("⚠️")
        return
    if val == "-":
        get_conn().execute("DELETE FROM settings WHERE key=?",
                           (f"custom_text_{key}",))
        await state.clear()
        await message.answer("♻️")
        return
    db_set(f"custom_text_{key}", val)
    await state.clear()
    await message.answer("✅")


# ══════════════════════════════════════════════════════════════
# GUIDE
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:guide")
async def cb_admin_guide(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🇮🇷 فارسی / Persian",
        callback_data="guide:fa"))
    b.row(InlineKeyboardButton(
        text="🇬🇧 English / انگلیسی",
        callback_data="guide:en"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_back"),
                                callback_data="admin:home"))
    title = ("📖 <b>راهنما / Guide</b>\n\n"
             "زبان مورد نظر را انتخاب کنید:\n"
             "Choose your preferred language:")
    await safe_edit(cb.message, title, b.as_markup())


@router.callback_query(F.data.in_({"guide:fa", "guide:en"}))
async def cb_guide_edit(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    lang_code = cb.data.split(":")[1]
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.guide_text)
    await state.update_data(guide_lang=lang_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "back"),
                             callback_data="admin:guide")]])
    await safe_edit(cb.message, tr(lang, "guide_ask", lang=lang_code), kb)


@router.message(Flow.guide_text, F.text)
async def msg_guide_text(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    lang_code = data.get("guide_lang")
    val = (message.text or "").strip()
    if not lang_code or not val:
        await state.clear()
        return
    db_set(f"guide_{lang_code}", val)
    await state.clear()
    await message.answer("✅")


# ══════════════════════════════════════════════════════════════
# SUB-ADMINS
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:admins")
async def cb_admin_admins(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    await render_admins(cb, c, 1)


async def render_admins(cb, c, page=1):
    lang = await _admin_lang(c, cb.from_user.id)
    per = 10
    page = max(1, page)
    total = int(get_conn().execute(
        "SELECT COUNT(*) AS c FROM extra_admins").fetchone()["c"] or 0)
    total_pages = max(1, (total + per - 1) // per)
    rows = get_conn().execute(
        "SELECT * FROM extra_admins ORDER BY added_at DESC LIMIT ? OFFSET ?",
        (per, (page - 1) * per)).fetchall()

    text = tr(lang, "ad_admins_title", count=total)
    text += f"\n📄 {page}/{total_pages}\n\n"

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=tr(lang, "ad_admins_add"),
                                callback_data="adm:add"))
    b.row(InlineKeyboardButton(text=tr(lang, "ad_admins_search"),
                                callback_data="adm:search"))
    if not rows:
        text += tr(lang, "ad_admins_empty")
    else:
        for r in rows:
            uid = int(r["user_id"])
            u = UserRepo.get(uid)
            name = (u.username or u.first_name) if u else str(uid)
            b.row(InlineKeyboardButton(
                text=f"👑 {name[:35]}",
                callback_data=safe_cb(f"adm:view:{uid}")))
            text += f"👑 <code>{uid}</code> — {esc(str(name)[:30])}\n"
    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="◀️", callback_data=safe_cb(f"adm:pg:{page - 1}"))
    nav.button(text=f"📄 {page}/{total_pages}", callback_data="noop")
    if page < total_pages:
        nav.button(text="▶️", callback_data=safe_cb(f"adm:pg:{page + 1}"))
    nav.adjust(3)
    rows_kb = b.export() + nav.export()
    rows_kb.append([InlineKeyboardButton(text=tr(lang, "ad_admins_back"),
                                           callback_data="admin:home")])
    await safe_edit(cb.message, text,
                    InlineKeyboardMarkup(inline_keyboard=rows_kb))


@router.callback_query(F.data.startswith("adm:pg:"))
async def cb_adm_pg(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    try:
        page = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        page = 1
    await render_admins(cb, c, page)


@router.callback_query(F.data == "adm:add")
async def cb_adm_add(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.admin_new_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_admins_back"),
                             callback_data="admin:admins")]])
    await safe_edit(cb.message, tr(lang, "ad_admins_ask"), kb)


@router.message(Flow.admin_new_id, F.text)
async def msg_adm_add(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    val = (message.text or "").strip()
    if not val.lstrip("-").isdigit():
        await message.answer(tr(lang, "ad_admins_invalid"))
        return
    uid = int(val)
    if uid == message.from_user.id:
        await message.answer(tr(lang, "ad_admins_self"))
        await state.clear()
        return
    if uid in OWNER_IDS:
        await message.answer(tr(lang, "ad_admins_exists_owner"))
        await state.clear()
        return
    existing = get_conn().execute(
        "SELECT 1 FROM extra_admins WHERE user_id=?", (uid,)).fetchone()
    if existing:
        await message.answer(tr(lang, "ad_admins_exists_admin"))
        await state.clear()
        return
    get_conn().execute(
        "INSERT INTO extra_admins(user_id, added_by, added_at) VALUES (?, ?, ?)",
        (uid, message.from_user.id, now_ts()))
    await state.clear()
    await message.answer(tr(lang, "ad_admins_added"))
    with contextlib.suppress(Exception):
        await c.bot.send_message(uid, "👑")


@router.callback_query(F.data == "adm:search")
async def cb_adm_search(cb: CallbackQuery, state: FSMContext, c: Container):
    if not await require_admin(cb):
        return
    await cb.answer()
    lang = await _admin_lang(c, cb.from_user.id)
    await state.set_state(Flow.admin_search)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "ad_admins_back"),
                             callback_data="admin:admins")]])
    await safe_edit(cb.message, tr(lang, "ad_admins_search_ask"), kb)


@router.message(Flow.admin_search, F.text)
async def msg_adm_search(message: Message, state: FSMContext, c: Container):
    if not is_admin(message.from_user.id):
        return
    lang = await _admin_lang(c, message.from_user.id)
    val = (message.text or "").strip()
    if not val.lstrip("-").isdigit():
        await message.answer(tr(lang, "ad_admins_invalid"))
        return
    uid = int(val)
    row = get_conn().execute(
        "SELECT * FROM extra_admins WHERE user_id=?", (uid,)).fetchone()
    await state.clear()
    if not row:
        await message.answer(tr(lang, "ad_admins_not_found"))
        return
    u = UserRepo.get(uid)
    name = (u.first_name if u and u.first_name else "—")
    username = ("@" + u.username) if (u and u.username) else "—"
    text = f"👑 <code>{uid}</code>\n📛 {esc(name)}\n🔗 {esc(username)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "ad_admins_remove_btn"),
                              callback_data=safe_cb(f"adm:rm:{uid}"))],
        [InlineKeyboardButton(text=tr(lang, "ad_admins_back"),
                              callback_data="admin:admins")]])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:view:"))
async def cb_adm_view(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    lang = await _admin_lang(c, cb.from_user.id)
    try:
        uid = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    row = get_conn().execute(
        "SELECT * FROM extra_admins WHERE user_id=?", (uid,)).fetchone()
    if not row:
        await cb.answer(tr(lang, "ad_admins_not_found"), show_alert=True)
        return
    await cb.answer()
    u = UserRepo.get(uid)
    name = (u.first_name if u and u.first_name else "—")
    username = ("@" + u.username) if (u and u.username) else "—"
    status = tr(lang, "active")
    text = tr(lang, "ad_admins_profile", uid=uid, name=esc(name),
              username=esc(username),
              date=fmt_time(row["added_at"]), status=status)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "ad_admins_remove_btn"),
                              callback_data=safe_cb(f"adm:rm:{uid}"))],
        [InlineKeyboardButton(text=tr(lang, "ad_admins_back"),
                              callback_data="admin:admins")]])
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data.startswith("adm:rm:"))
async def cb_adm_remove(cb: CallbackQuery, c: Container):
    if not await require_admin(cb):
        return
    try:
        uid = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    get_conn().execute("DELETE FROM extra_admins WHERE user_id=?", (uid,))
    await cb.answer("🗑", show_alert=True)
    await render_admins(cb, c, 1)


# ══════════════════════════════════════════════════════════════
# CUSTOM BUTTON CALLBACK FALLBACK
# ══════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("custom:"))
async def cb_custom_button(cb: CallbackQuery, c: Container):
    await cb.answer("✅")
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    with contextlib.suppress(Exception):
        await cb.message.answer(tr(lang, "fallback_info"),
                                 reply_markup=main_menu(user))


# ══════════════════════════════════════════════════════════════
# MINI APP — WebAppData
# ══════════════════════════════════════════════════════════════
@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, c: Container):
    user = UserRepo.get(message.from_user.id)
    if not user:
        return
    lang = user_lang(user)
    data = message.web_app_data.data if message.web_app_data else ""
    logging.info(f"web_app_data from {user.user_id}: {data[:200]}")
    with contextlib.suppress(Exception):
        await message.answer(
            f"{tr(lang, 'received_data')}\n<code>{esc(data[:500])}</code>")


# ══════════════════════════════════════════════════════════════
# FALLBACK — CALLBACK ناشناخته
# ══════════════════════════════════════════════════════════════
@router.callback_query()
async def cb_unknown(cb: CallbackQuery, c: Container):
    user = UserRepo.get(cb.from_user.id)
    lang = user_lang(user)
    with contextlib.suppress(Exception):
        await cb.answer(tr(lang, "button_inactive"), show_alert=False)
    if not user:
        return
    with contextlib.suppress(Exception):
        await cb.message.answer(
            tr(lang, "fallback_info"),
            reply_markup=main_menu(user))


# ══════════════════════════════════════════════════════════════
# FALLBACK — پیام
# ══════════════════════════════════════════════════════════════
@router.message()
async def fallback(message: Message, state: FSMContext, c: Container):
    if await state.get_state() is not None:
        return
    u = message.from_user
    if not u:
        return
    user = UserRepo.get(u.id)
    lang = user_lang(user)
    with contextlib.suppress(Exception):
        await message.answer(tr(lang, "fallback_info"))


# ══════════════════════════════════════════════════════════════
# BACKGROUND LOOPS
# ══════════════════════════════════════════════════════════════
async def auto_delete_loop(c: Container):
    while not c.shutdown_event.is_set():
        try:
            await asyncio.wait_for(c.shutdown_event.wait(), timeout=30)
            return
        except asyncio.TimeoutError:
            pass
        try:
            now = now_ts()
            for j in JobRepo.due_for_delete(now):
                if j.file_path:
                    with contextlib.suppress(Exception):
                        p = Path(j.file_path)
                        parent = p.parent
                        if p.exists():
                            p.unlink()
                        cleanup_empty_dir(parent)
                with contextlib.suppress(Exception):
                    jd = DOWNLOAD_DIR / j.job_id
                    if jd.exists():
                        shutil.rmtree(jd, ignore_errors=True)
                if c.bot and j.msg_id:
                    with contextlib.suppress(Exception):
                        await c.bot.delete_message(j.chat_id, j.msg_id)
                if c.bot:
                    user = UserRepo.get(j.user_id)
                    lang = user_lang(user)
                    with contextlib.suppress(Exception):
                        kb = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text=tr(lang, "btn_redo"),
                                callback_data=safe_cb(f"redl:{j.job_id}"))]])
                        await c.bot.send_message(
                            j.chat_id,
                            f"{tr(lang, 'file_removed')}\n"
                            f"🆔 <code>{j.job_id}</code>",
                            reply_markup=kb)
                JobRepo.update(j.job_id, notice_msg_id=1, file_path=None)
        except Exception as e:
            logging.error(f"auto_delete error: {e}")


async def announce_schedule_loop(c: Container):
    import json
    from types import SimpleNamespace
    while not c.shutdown_event.is_set():
        try:
            await asyncio.wait_for(c.shutdown_event.wait(), timeout=20)
            return
        except asyncio.TimeoutError:
            pass
        try:
            ts = float(db_get("announce_schedule_ts", "0") or 0)
            if ts <= 0 or now_ts() < ts:
                continue
            raw = db_get("announce_scheduled_payload", "")
            db_set("announce_schedule", "")
            db_set("announce_schedule_ts", "0")
            db_set("announce_scheduled_payload", "")
            if not raw:
                continue
            pl = json.loads(raw)
            uids = _audience_uids()
            if not uids:
                continue
            fake = SimpleNamespace(
                message=SimpleNamespace(
                    chat=SimpleNamespace(id=pl.get("chat_id"))),
                from_user=SimpleNamespace(id=pl.get("admin_id", 0)))
            await _do_user_broadcast(
                c, fake, uids, pl.get("text") or "",
                pl.get("media") or {}, pl.get("forward") or None)
        except Exception as e:
            logging.error(f"announce_schedule error: {e}")


async def auto_backup_loop(c: Container):
    last_check = 0
    while not c.shutdown_event.is_set():
        try:
            await asyncio.wait_for(c.shutdown_event.wait(), timeout=60)
            return
        except asyncio.TimeoutError:
            pass
        try:
            now = now_ts()
            if now - last_check < 60:
                continue
            last_check = now
            if db_get("auto_backup_enabled", "0") != "1":
                continue
            try:
                ih = float(db_get("auto_backup_hours", "24"))
            except ValueError:
                ih = 24.0
            try:
                lt = float(db_get("auto_backup_last", "0") or "0")
            except ValueError:
                lt = 0.0
            if now - lt < ih * 3600:
                continue
            name = f"auto_backup_{fmt_dt_short(now)}.db"
            dst = BACKUP_DIR / name
            checkpoint_db()
            shutil.copy2(DB_PATH, dst)
            size = dst.stat().st_size
            get_conn().execute(
                "INSERT INTO backups(path, size, created_at) VALUES (?, ?, ?)",
                (str(dst), size, now))
            db_set("auto_backup_last", str(now))
        except Exception as e:
            logging.error(f"auto_backup error: {e}")


async def recover_stuck_jobs(c: Container):
    try:
        for j in JobRepo.stuck_queued(now_ts() + 1):
            clear_cancelled(j.job_id)
            JobRepo.update(j.job_id, status=STATUS_QUEUED, error=None)
            await c.job_queue.put(j.job_id)
        for j in JobRepo.active(10000):
            if j.status in (STATUS_DOWNLOADING, STATUS_UPLOADING):
                clear_cancelled(j.job_id)
                JobRepo.update(j.job_id, status=STATUS_QUEUED,
                               error="interrupted_restart")
                await c.job_queue.put(j.job_id)
            elif j.status == STATUS_ANALYZING:
                JobRepo.update(j.job_id, status=STATUS_CANCELLED,
                               error="interrupted_restart",
                               finished_at=now_ts())
    except Exception as e:
        logging.error(f"recover error: {e}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
async def main():
    print_banner()
    log_step("Loading", "settings...")
    load_settings()
    log_step("Database", "initializing...")
    run_migrations()
    log_step("Database", f"{DB_PATH.name} ready")
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    log_step("FFmpeg", "detected" if ffmpeg_ok else "missing", ok=ffmpeg_ok)
    log_step("Pillow", "detected" if HAS_PIL else "missing", ok=HAS_PIL)
    log_step("gallery-dl", "detected" if HAS_GALLERY_DL else "missing",
             ok=HAS_GALLERY_DL)
    cookies_path = DATA_DIR / "cookies.txt"
    log_step("Cookies", "found" if cookies_path.exists() else "not found",
             ok=cookies_path.exists())
    log_step("Owners", str(len(OWNER_IDS)))
    MenuButtonRepo.seed_defaults()
    cleanup_menu_buttons()

    global CONTAINER
    CONTAINER = Container()

    log_step("Bot", "connecting...")
    try:
        local_server = TelegramAPIServer.from_base(LOCAL_TG_API, is_local=True)
        session = AiohttpSession(api=local_server, timeout=1800, limit=100)
        with contextlib.suppress(Exception):
            session.middleware(PremiumEmojiRequestMiddleware())
        CONTAINER.bot = Bot(
            token=CFG.bot_token, session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = await asyncio.wait_for(CONTAINER.bot.get_me(), timeout=30.0)
        log_step("Bot", f"@{me.username}")
        log_step("API", LOCAL_TG_API)
    except asyncio.TimeoutError:
        log_err("Bot connection timed out after 30s")
        sys.exit(1)
    except Exception as e:
        log_err(f"Bot connection failed: {e}")
        sys.exit(1)

    # ✅ فقط start و lang در منوی ربات نمایش داده میشن
    with contextlib.suppress(Exception):
        await CONTAINER.bot.set_my_commands([
            BotCommand(command="start", description="🏠 Start / شروع"),
            BotCommand(command="lang",  description="🌐 Language / زبان"),
        ])
        log_step("Commands", "registered (start, lang)")

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(InjectMiddleware(CONTAINER))
    dp.callback_query.middleware(InjectMiddleware(CONTAINER))
    dp.message.middleware(UserUpsertMiddleware())
    dp.callback_query.middleware(UserUpsertMiddleware())
    dp.message.middleware(BlockGuardMiddleware())
    dp.callback_query.middleware(BlockGuardMiddleware())
    dp.message.middleware(MaintenanceGuard())
    dp.callback_query.middleware(MaintenanceGuard())
    dp.callback_query.middleware(CallbackRateLimitMiddleware(per_sec=0.6))
    dp.include_router(router)

    log_step("Jobs", "recovering...")
    await recover_stuck_jobs(CONTAINER)

    try:
        n_workers = max(1, int(os.getenv("BOT_WORKERS", "3")))
    except (ValueError, TypeError):
        n_workers = 3
    for i in range(n_workers):
        CONTAINER.worker_tasks.append(
            asyncio.create_task(worker(CONTAINER, i)))
    log_step("Workers", str(n_workers))

    CONTAINER.bg_tasks.append(
        asyncio.create_task(auto_delete_loop(CONTAINER)))
    CONTAINER.bg_tasks.append(
        asyncio.create_task(auto_backup_loop(CONTAINER)))
    CONTAINER.bg_tasks.append(
        asyncio.create_task(announce_schedule_loop(CONTAINER)))

    sys.stdout.write("\n")
    sys.stdout.write(
        f"  {C.GRN}{C.B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}\n")
    sys.stdout.write(f"  {C.GRN}{C.B}✓ ONLINE{C.R}\n")
    sys.stdout.write(
        f"  {C.GRN}{C.B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}\n\n")
    sys.stdout.flush()

    try:
        await CONTAINER.bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(CONTAINER.bot,
                                allowed_updates=["message", "callback_query"])
    except KeyboardInterrupt:
        sys.stdout.write(f"\n  {C.YEL}⚠ Stopped{C.R}\n")
    finally:
        CONTAINER.shutdown_event.set()
        for t in CONTAINER.worker_tasks + CONTAINER.bg_tasks:
            t.cancel()
        await asyncio.gather(
            *(CONTAINER.worker_tasks + CONTAINER.bg_tasks),
            return_exceptions=True)
        with contextlib.suppress(Exception):
            await CONTAINER.bot.session.close()
        close_conn()
        log_ok("Bot stopped cleanly")


def _run():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.stdout.write(f"\n  {C.YEL}⚠ Stopped{C.R}\n")
    except Exception as e:
        log_err(f"Fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    _run()