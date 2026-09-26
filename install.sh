#!/bin/bash
# ══════════════════════════════════════════════════════════════
#  Arka Downloader — Adaptive Installer (v5.3.0)
#  Made for @AMIRALI_IRX
#  Usage: sudo bash install.sh install
# ══════════════════════════════════════════════════════════════

R="\033[0m"; B="\033[1m"; D="\033[2m"
RED="\033[91m"; GRN="\033[92m"; YEL="\033[93m"
BLU="\033[94m"; MAG="\033[95m"; CYN="\033[96m"

ok()   { echo -e "  ${GRN}✓${R} $1"; }
err()  { echo -e "  ${RED}✗${R} $1"; }
warn() { echo -e "  ${YEL}⚠${R} $1"; }
info() { echo -e "  ${CYN}▸${R} $1"; }
step() { echo -e "\n${MAG}${B}━━━ $1 ━━━${R}"; }
val()  { printf "  ${D}  %-22s${R} ${CYN}%s${R}\n" "$1" "$2"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="arkabot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-root}"
API_ID_DEFAULT="2040"
API_HASH_DEFAULT="b18441a1ff607e10a989891a5462e627"
LOGROTATE_FILE="/etc/logrotate.d/arkabot"
TG_DATA_DIR="$PROJECT_DIR/data/tg-api"

MAIN_FILE=""

# ─── Adaptive values (filled by detect_server) ───
CPU_CORES=1
RAM_MB=1024
SWAP_MB=0
DISK_TOTAL_MB=10240
DISK_AVAIL_MB=5120
DISK_TYPE="Unknown"

WORKERS=2
MAX_CONCURRENT=2
MAX_FILE_MB=2048
DL_HOUR=10
DL_DAY=50
PHOTO_HOUR=30
PHOTO_DAY=200
MUSIC_HOUR=30
MUSIC_DAY=200
DELETE_DELAY=60
SQLITE_CACHE_MB=32
LOG_RETENTION=7
SERVICE_NICE=0
OOM_SCORE=0

# ─── Helper: sudo wrapper (works when running as root) ───
if [ "$RUN_USER" = "root" ]; then
    AS_USER=""
    AS_USER_MSG="(running as root)"
else
    AS_USER="sudo -u $RUN_USER"
    AS_USER_MSG="(running as $RUN_USER)"
fi

if [ "$EUID" -ne 0 ]; then
    err "Root privileges required. Run: sudo bash install.sh install"
    exit 1
fi

banner() {
    clear
    echo -e "${CYN}${B}"
    cat << "EOF"
   █████╗ ██████╗ ██╗  ██╗ █████╗
  ██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗
  ███████║██████╔╝█████╔╝ ███████║
  ██╔══██║██╔══██╗██╔═██╗ ██╔══██║
  ██║  ██║██║  ██║██║  ██╗██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
EOF
    echo -e "${R}"
    echo -e "${MAG}${B}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
    echo -e "  ${YEL}⚡${R} ${B}Version${R} ${CYN}5.3.0${R}   ${YEL}👤${R} ${B}Owner${R} ${CYN}@AMIRALI_IRX${R}   ${YEL}💎${R} ${GRN}Adaptive${R}"
    echo -e "${MAG}${B}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}\n"
}

detect_main_file() {
    for c in bot.py DownVip.py main.py app.py; do
        [ -f "$PROJECT_DIR/$c" ] && MAIN_FILE="$PROJECT_DIR/$c" && return 0
    done
    for f in "$PROJECT_DIR"/*.py; do
        [ -f "$f" ] || continue
        if grep -q "aiogram" "$f" 2>/dev/null; then
            MAIN_FILE="$f"; return 0
        fi
    done
    return 1
}

# ══════════════════════════════════════════════════════════════
#  SERVER PROFILE DETECTION + AUTO-CONFIG
# ══════════════════════════════════════════════════════════════
detect_server() {
    step "Server Profile"

    CPU_CORES=$(nproc 2>/dev/null || echo 1)
    [ "$CPU_CORES" -lt 1 ] && CPU_CORES=1

    RAM_MB=$(free -m | awk 'NR==2{print $2}')
    SWAP_MB=$(free -m | awk 'NR==3{print $2}')

    DISK_TOTAL_MB=$(df -m "$PROJECT_DIR" | awk 'NR==2{print $2}')
    DISK_AVAIL_MB=$(df -m "$PROJECT_DIR" | awk 'NR==2{print $4}')

    # Detect disk type (SSD / HDD)
    DISK_DEV=$(df "$PROJECT_DIR" | awk 'NR==2{print $1}' \
               | sed 's|/dev/||' | sed 's|[0-9]*$||')
    if [ -e "/sys/block/${DISK_DEV}/queue/rotational" ]; then
        ROT=$(cat "/sys/block/${DISK_DEV}/queue/rotational" 2>/dev/null)
        [ "$ROT" = "0" ] && DISK_TYPE="SSD" || DISK_TYPE="HDD"
    else
        DISK_TYPE="Unknown"
    fi

    # ═══ Workers: 2 + cores, capped 8 ═══
    WORKERS=$((CPU_CORES + 2))
    [ "$WORKERS" -gt 8 ] && WORKERS=8
    [ "$WORKERS" -lt 2 ] && WORKERS=2

    # ═══ Concurrent downloads based on RAM ═══
    if   [ "$RAM_MB" -lt 1024 ]; then MAX_CONCURRENT=1
    elif [ "$RAM_MB" -lt 2048 ]; then MAX_CONCURRENT=2
    elif [ "$RAM_MB" -lt 4096 ]; then MAX_CONCURRENT=4
    elif [ "$RAM_MB" -lt 8192 ]; then MAX_CONCURRENT=6
    else                              MAX_CONCURRENT=8
    fi
    [ "$MAX_CONCURRENT" -gt "$((CPU_CORES * 2))" ] && \
        MAX_CONCURRENT=$((CPU_CORES * 2))

    # ═══ Max file size based on free disk ═══
    if   [ "$DISK_AVAIL_MB" -lt 5120  ]; then MAX_FILE_MB=1024
    elif [ "$DISK_AVAIL_MB" -lt 20480 ]; then MAX_FILE_MB=2048
    else                                      MAX_FILE_MB=4096
    fi

    # ═══ Rate limits based on RAM ═══
    if   [ "$RAM_MB" -lt 1024 ]; then
        DL_HOUR=5;    DL_DAY=20;    PHOTO_HOUR=15;  PHOTO_DAY=100
        MUSIC_HOUR=15; MUSIC_DAY=100
    elif [ "$RAM_MB" -lt 2048 ]; then
        DL_HOUR=10;   DL_DAY=50;    PHOTO_HOUR=30;  PHOTO_DAY=200
        MUSIC_HOUR=30; MUSIC_DAY=200
    elif [ "$RAM_MB" -lt 4096 ]; then
        DL_HOUR=20;   DL_DAY=100;   PHOTO_HOUR=60;  PHOTO_DAY=400
        MUSIC_HOUR=60; MUSIC_DAY=400
    else
        DL_HOUR=50;   DL_DAY=300;   PHOTO_HOUR=150; PHOTO_DAY=1000
        MUSIC_HOUR=150; MUSIC_DAY=1000
    fi

    # ═══ Delete delay based on disk space ═══
    if   [ "$DISK_AVAIL_MB" -lt 5120  ]; then DELETE_DELAY=30
    elif [ "$DISK_AVAIL_MB" -lt 20480 ]; then DELETE_DELAY=60
    else                                      DELETE_DELAY=120
    fi

    # ═══ SQLite cache based on RAM ═══
    if   [ "$RAM_MB" -lt 1024 ]; then SQLITE_CACHE_MB=16
    elif [ "$RAM_MB" -lt 2048 ]; then SQLITE_CACHE_MB=32
    else                              SQLITE_CACHE_MB=64
    fi

    # ═══ Log retention based on disk ═══
    if   [ "$DISK_AVAIL_MB" -lt 5120  ]; then LOG_RETENTION=3
    elif [ "$DISK_AVAIL_MB" -lt 20480 ]; then LOG_RETENTION=7
    else                                      LOG_RETENTION=14
    fi

    # ═══ CPU niceness ═══
    if [ "$CPU_CORES" -lt 2 ]; then SERVICE_NICE=5; else SERVICE_NICE=0; fi

    # ═══ OOM protection ═══
    if [ "$RAM_MB" -lt 2048 ]; then OOM_SCORE=-300; else OOM_SCORE=0; fi

    # ─── Print ───
    val "CPU cores"       "$CPU_CORES"
    val "RAM"             "${RAM_MB} MB"
    val "Swap"            "${SWAP_MB} MB"
    val "Disk"            "${DISK_TOTAL_MB} MB ($DISK_TYPE)"
    val "Disk available"  "${DISK_AVAIL_MB} MB"
    val "Run user"        "$RUN_USER $AS_USER_MSG"

    echo ""
    info "Auto-Config (tuned to your server):"
    val "Workers"           "$WORKERS"
    val "Concurrent DL"     "$MAX_CONCURRENT"
    val "Max file size"     "${MAX_FILE_MB} MB"
    val "Video / Hour"      "$DL_HOUR"
    val "Video / Day"       "$DL_DAY"
    val "Photo / Hour"      "$PHOTO_HOUR"
    val "Photo / Day"       "$PHOTO_DAY"
    val "Music / Hour"      "$MUSIC_HOUR"
    val "Music / Day"       "$MUSIC_DAY"
    val "Delete delay"      "${DELETE_DELAY}s"
    val "SQLite cache"      "${SQLITE_CACHE_MB} MB"
    val "Log retention"     "${LOG_RETENTION} days"
    val "Service nice"      "$SERVICE_NICE"
}

preflight_checks() {
    step "Pre-flight Checks"
    command -v systemctl &>/dev/null || { err "systemctl not found"; exit 1; }
    ok "systemctl"
    command -v curl &>/dev/null || { err "curl not found"; exit 1; }
    ok "curl"
    command -v python3 &>/dev/null || { err "python3 not found"; exit 1; }
    ok "python3 ($(python3 -V 2>&1 | cut -d' ' -f2))"
    python3 -c 'import venv' 2>/dev/null || { err "python3-venv missing"; exit 1; }
    ok "python3-venv"
}

check_os() {
    step "Operating System"
    [ -f /etc/os-release ] && . /etc/os-release || { err "Unknown OS"; exit 1; }
    ok "System: $PRETTY_NAME"
    case "$ID" in
        ubuntu|debian|linuxmint|pop) PKG_MGR="apt" ;;
        centos|rhel|fedora|rocky|almalinux)
            command -v dnf &>/dev/null && PKG_MGR="dnf" || PKG_MGR="yum" ;;
        arch|manjaro) PKG_MGR="pacman" ;;
        *) PKG_MGR="apt" ;;
    esac
    ok "Package manager: $PKG_MGR"
}

install_system_deps() {
    step "System Dependencies"
    case "$PKG_MGR" in
        apt)
            apt update -qq
            DEBIAN_FRONTEND=noninteractive apt install -y -qq \
                python3 python3-pip python3-venv python3-dev \
                ffmpeg curl git unzip ca-certificates sqlite3 \
                libjpeg-dev zlib1g-dev libwebp-dev
            ;;
        dnf|yum)
            $PKG_MGR install -y -q \
                python3 python3-pip python3-virtualenv \
                ffmpeg curl git unzip ca-certificates sqlite \
                libjpeg-turbo-devel zlib-devel libwebp-devel
            ;;
        pacman)
            pacman -Sy --noconfirm --quiet \
                python python-pip ffmpeg curl git unzip ca-certificates \
                sqlite libjpeg-turbo zlib libwebp
            ;;
    esac
    ok "Python: $(python3 --version 2>&1)"
    command -v ffmpeg &>/dev/null && ok "FFmpeg" || warn "FFmpeg missing"
    command -v ffprobe &>/dev/null && ok "FFprobe" || warn "FFprobe missing"
    command -v sqlite3 &>/dev/null && ok "SQLite3" || warn "SQLite3 missing"
}

install_docker() {
    step "Docker Engine"
    if command -v docker &>/dev/null; then
        ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"
    else
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        ok "Docker installed"
    fi
    systemctl enable docker --now 2>/dev/null || true
    systemctl is-active --quiet docker && ok "Docker active" || warn "Docker inactive"
}

# ══════════════════════════════════════════════════════════════
#  ADAPTIVE SWAP
# ══════════════════════════════════════════════════════════════
ensure_swap() {
    step "Swap Memory"

    TOTAL_MB=$(free -m | awk 'NR==2{print $2}')
    SWAP_MB=$(free -m | awk 'NR==3{print $2}')
    SWAP_FILE="/swapfile"

    info "Detected: ${TOTAL_MB}MB RAM | ${SWAP_MB}MB swap"

    if   [ "$TOTAL_MB" -lt 1024 ]; then NEED_SWAP_MB=2048
    elif [ "$TOTAL_MB" -lt 2048 ]; then NEED_SWAP_MB=2048
    elif [ "$TOTAL_MB" -lt 4096 ]; then NEED_SWAP_MB=2048
    elif [ "$TOTAL_MB" -lt 8192 ]; then NEED_SWAP_MB=4096
    else                                 NEED_SWAP_MB=0
    fi

    if [ "$NEED_SWAP_MB" -eq 0 ]; then
        ok "Swap not required for ${TOTAL_MB}MB RAM"
        return
    fi

    if [ "$SWAP_MB" -ge "$NEED_SWAP_MB" ]; then
        ok "Swap: ${SWAP_MB}MB (sufficient)"
        return
    fi

    warn "Insufficient swap — target ${NEED_SWAP_MB}MB"

    if [ -f "$SWAP_FILE" ]; then
        info "Removing old swapfile..."
        swapoff "$SWAP_FILE" 2>/dev/null || true
        rm -f "$SWAP_FILE"
    fi

    info "Creating ${NEED_SWAP_MB}MB swapfile..."
    if ! fallocate -l "${NEED_SWAP_MB}M" "$SWAP_FILE" 2>/dev/null; then
        dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$NEED_SWAP_MB" status=none
    fi

    chmod 600 "$SWAP_FILE"
    mkswap "$SWAP_FILE" >/dev/null
    swapon "$SWAP_FILE"

    sed -i "\|^$SWAP_FILE|d" /etc/fstab 2>/dev/null || true
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab

    if ! grep -q "^vm.swappiness" /etc/sysctl.conf 2>/dev/null; then
        echo "vm.swappiness=10" >> /etc/sysctl.conf
    fi
    if ! grep -q "^vm.vfs_cache_pressure" /etc/sysctl.conf 2>/dev/null; then
        echo "vm.vfs_cache_pressure=50" >> /etc/sysctl.conf
    fi
    sysctl -w vm.swappiness=10 >/dev/null 2>&1 || true
    sysctl -w vm.vfs_cache_pressure=50 >/dev/null 2>&1 || true

    NEW_SWAP=$(free -m | awk 'NR==3{print $2}')
    ok "Swap: ${SWAP_MB}MB → ${NEW_SWAP}MB"
}

cleanup_old_services() {
    step "Cleanup Conflicting Services"
    local found=0
    for old_svc in arka-downloader arka downloader; do
        if systemctl list-unit-files 2>/dev/null | grep -q "^${old_svc}\.service"; then
            warn "Found: $old_svc — disabling"
            systemctl stop    "$old_svc" 2>/dev/null || true
            systemctl disable "$old_svc" 2>/dev/null || true
            found=1
        fi
    done
    pkill -9 -f "DownVip" 2>/dev/null || true
    sleep 1
    [ "$found" -eq 1 ] && systemctl daemon-reload && ok "Old services removed" || \
        ok "No conflicts found"
}

setup_telegram_api_container() {
    step "Telegram Bot API (Local Server)"

    mkdir -p "$TG_DATA_DIR"
    chown "$RUN_USER:$RUN_USER" "$TG_DATA_DIR" 2>/dev/null || true
    ok "Data directory: $TG_DATA_DIR"

    if docker ps -a --format '{{.Names}}' | grep -q "^telegram-bot-api$"; then
        MOUNT=$(docker inspect telegram-bot-api --format '{{range .Mounts}}{{.Source}}{{end}}' 2>/dev/null || echo "")
        if [ "$MOUNT" != "$TG_DATA_DIR" ]; then
            warn "Wrong mount detected — recreating"
            docker rm -f telegram-bot-api >/dev/null 2>&1 || true
        else
            docker start telegram-bot-api >/dev/null 2>&1 || true
        fi
    fi

    if ! docker ps --format '{{.Names}}' | grep -q "^telegram-bot-api$"; then
        info "Starting container with bind mount..."
        docker run -d \
            --name telegram-bot-api \
            --restart=always \
            --network host \
            -v "$TG_DATA_DIR:/var/lib/telegram-bot-api" \
            -e TELEGRAM_API_ID="$API_ID_DEFAULT" \
            -e TELEGRAM_API_HASH="$API_HASH_DEFAULT" \
            -e TELEGRAM_LOCAL=1 \
            aiogram/telegram-bot-api:latest >/dev/null

        for i in {1..20}; do
            HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 \
                   http://127.0.0.1:8081/ 2>/dev/null || echo "")
            if [ "$HTTP" = "404" ] || [ "$HTTP" = "200" ] || [ "$HTTP" = "401" ]; then
                ok "Telegram API online (${i}s)"
                return
            fi
            sleep 1
        done
        warn "API not responding — check: docker logs telegram-bot-api"
    else
        ok "Container running"
    fi
}

check_files() {
    step "Project Files"
    detect_main_file || { err "No bot.py found"; exit 1; }
    ok "Main file: $(basename "$MAIN_FILE")"

    for d in data downloads logs backups updates data/tg-api; do
        mkdir -p "$PROJECT_DIR/$d"
        chown "$RUN_USER:$RUN_USER" "$PROJECT_DIR/$d" 2>/dev/null || true
    done
    ok "Working directories ready"

    if [ ! -f "$PROJECT_DIR/data/cookies.txt" ]; then
        cat > "$PROJECT_DIR/data/cookies.txt" <<'COOKIEEOF'
# Netscape HTTP Cookie File
# Used by yt-dlp and gallery-dl.
COOKIEEOF
        chown "$RUN_USER:$RUN_USER" "$PROJECT_DIR/data/cookies.txt" 2>/dev/null || true
        chmod 600 "$PROJECT_DIR/data/cookies.txt" 2>/dev/null || true
        warn "Created empty data/cookies.txt"
    else
        ok "data/cookies.txt exists"
    fi

    chown "$RUN_USER:$RUN_USER" "$MAIN_FILE" 2>/dev/null || true
}

setup_venv() {
    step "Python Virtual Environment"
    if [ ! -d "$VENV_DIR" ]; then
        $AS_USER python3 -m venv "$VENV_DIR"
        ok "venv created"
    else
        ok "venv already exists"
    fi

    info "Installing Python packages (2-3 minutes)..."
    $AS_USER "$VENV_DIR/bin/pip" install --upgrade pip -q
    $AS_USER "$VENV_DIR/bin/pip" install -q \
        "aiogram>=3.13.0" "yt-dlp>=2024.10.0" "gallery-dl>=1.27.0" \
        "curl_cffi>=0.7.0" "aiohttp>=3.10.0" "aiofiles>=24.1.0" \
        "pydantic-settings>=2.5.0" "python-dotenv>=1.0.0" "Pillow>=10.0.0"

    local missing=0
    for pkg in aiogram yt_dlp gallery_dl curl_cffi pydantic_settings dotenv PIL; do
        $AS_USER "$VENV_DIR/bin/python" -c "import $pkg" 2>/dev/null || {
            err "Missing: $pkg"; missing=1; }
    done
    [ "$missing" -eq 0 ] && ok "All packages installed" || warn "Some packages failed"
}

# ══════════════════════════════════════════════════════════════
#  .env WITH ADAPTIVE VALUES
# ══════════════════════════════════════════════════════════════
setup_env() {
    step ".env Configuration"

    if [ -f "$PROJECT_DIR/.env" ]; then
        EXISTING_TOKEN=$(grep -m1 '^BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null \
                         | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
        EXISTING_OWNER=$(grep -m1 '^OWNER_IDS=' "$PROJECT_DIR/.env" 2>/dev/null \
                         | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
        if [[ "$EXISTING_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] && [ -n "$EXISTING_OWNER" ]; then
            ok ".env credentials preserved"
            TOKEN="$EXISTING_TOKEN"
            OID="$EXISTING_OWNER"
        else
            warn ".env invalid — recreating"
            rm -f "$PROJECT_DIR/.env"
        fi
    fi

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        echo ""
        echo -e "  ${D}Get BOT_TOKEN from @BotFather${R}"
        echo -e "  ${D}Get OWNER_IDS from @userinfobot (numeric only)${R}"
        echo ""
        read -p "  BOT_TOKEN: " TOKEN
        read -p "  OWNER_IDS (numeric, comma-separated): " OID

        [ -z "$TOKEN" ] || [ -z "$OID" ] && { err "Empty input"; exit 1; }
        [[ ! "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] && \
            { err "Invalid BOT_TOKEN format"; exit 1; }

        OID_CLEAN=$(echo "$OID" | tr -d ' ')
        [[ ! "$OID_CLEAN" =~ ^-?[0-9]+(,-?[0-9]+)*$ ]] && \
            { err "OWNER_IDS must be numeric"; exit 1; }
        OID="$OID_CLEAN"
    fi

    cat > "$PROJECT_DIR/.env" <<EOF
# ══════════════════════════════════════════════════════════════
#  Arka Downloader — Auto-Generated Config
#  Tuned for: ${CPU_CORES} cores / ${RAM_MB}MB RAM / ${DISK_TOTAL_MB}MB disk
#  Generated: $(date '+%Y-%m-%d %H:%M:%S')
# ══════════════════════════════════════════════════════════════

# ─── Telegram ───
BOT_TOKEN="$TOKEN"
OWNER_IDS="$OID"
TELEGRAM_API_ID="$API_ID_DEFAULT"
TELEGRAM_API_HASH="$API_HASH_DEFAULT"
BOT_NAME="Arka Downloader"
OWNER_USERNAME="@AMIRALI_IRX"

# ─── Adaptive (server-tuned) ───
BOT_WORKERS=$WORKERS
BOT_MAX_CONCURRENT=$MAX_CONCURRENT
BOT_MAX_FILE_SIZE_MB=$MAX_FILE_MB
BOT_MAX_DL_HOUR=$DL_HOUR
BOT_MAX_DL_DAY=$DL_DAY
BOT_MAX_PHOTO_HOUR=$PHOTO_HOUR
BOT_MAX_PHOTO_DAY=$PHOTO_DAY
BOT_MAX_MUSIC_HOUR=$MUSIC_HOUR
BOT_MAX_MUSIC_DAY=$MUSIC_DAY
BOT_DELETE_DELAY=$DELETE_DELAY
BOT_SQLITE_CACHE_MB=$SQLITE_CACHE_MB
EOF

    chmod 600 "$PROJECT_DIR/.env"
    chown "$RUN_USER:$RUN_USER" "$PROJECT_DIR/.env" 2>/dev/null || true
    ok ".env written with adaptive config"
}

# ══════════════════════════════════════════════════════════════
#  APPLY ADAPTIVE VALUES TO DATABASE
# ══════════════════════════════════════════════════════════════
apply_adaptive_to_db() {
    step "Applying Adaptive Config to Database"

    DB="$PROJECT_DIR/data/bot.db"

    if [ ! -f "$DB" ]; then
        warn "bot.db not found yet — will apply after first bot run"
        return 1
    fi

    if ! command -v sqlite3 &>/dev/null; then
        warn "sqlite3 not installed — skipping DB tuning"
        return 1
    fi

    # Check if settings table exists (bot must have run at least once)
    TABLE_EXISTS=$(sqlite3 "$DB" \
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings';" \
        2>/dev/null)

    if [ -z "$TABLE_EXISTS" ]; then
        warn "settings table not found — will apply after first bot run"
        return 1
    fi

    sqlite3 "$DB" <<SQLEOF
INSERT INTO settings(key, value) VALUES ('max_concurrent',   '$MAX_CONCURRENT')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_file_size_mb', '$MAX_FILE_MB')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_dl_hour',      '$DL_HOUR')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_dl_day',       '$DL_DAY')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_photo_hour',   '$PHOTO_HOUR')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_photo_day',    '$PHOTO_DAY')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_music_hour',   '$MUSIC_HOUR')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('max_music_day',    '$MUSIC_DAY')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
INSERT INTO settings(key, value) VALUES ('delete_delay',     '$DELETE_DELAY')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
SQLEOF

    # Optimize SQLite pragmas
    sqlite3 "$DB" "PRAGMA optimize;" 2>/dev/null || true

    chown "$RUN_USER:$RUN_USER" "$DB" 2>/dev/null || true

    ok "Adaptive values applied to DB"
    return 0
}

# ══════════════════════════════════════════════════════════════
#  SYSTEMD SERVICE
# ══════════════════════════════════════════════════════════════
setup_service() {
    step "Systemd Service"

    local EXTRA=""
    if [ "$SERVICE_NICE" -ne 0 ]; then
        EXTRA+="Nice=${SERVICE_NICE}"$'\n'
    fi
    if [ "$OOM_SCORE" -ne 0 ]; then
        EXTRA+="OOMScoreAdjust=${OOM_SCORE}"$'\n'
    fi

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Arka Downloader Telegram Bot
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$PROJECT_DIR
Environment="PYTHONUNBUFFERED=1"
Environment="BOT_WORKERS=$WORKERS"
ExecStart=$VENV_DIR/bin/python $MAIN_FILE
Restart=always
RestartSec=15
StandardOutput=append:$PROJECT_DIR/logs/stdout.log
StandardError=append:$PROJECT_DIR/logs/stderr.log
LimitNOFILE=65536
TimeoutStopSec=20
${EXTRA}
[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" 2>/dev/null
    ok "Service created: $SERVICE_NAME"

    if [ -n "$EXTRA" ]; then
        info "Adaptive tweaks applied:"
        [ "$SERVICE_NICE" -ne 0 ] && val "Nice" "$SERVICE_NICE"
        [ "$OOM_SCORE" -ne 0 ] && val "OOMScoreAdjust" "$OOM_SCORE"
    fi
    val "BOT_WORKERS" "$WORKERS"
}

# ══════════════════════════════════════════════════════════════
#  ADAPTIVE LOGROTATE
# ══════════════════════════════════════════════════════════════
setup_logrotate() {
    step "Logrotate"
    [ ! -d /etc/logrotate.d ] && warn "logrotate not installed" && return

    cat > "$LOGROTATE_FILE" <<EOF
$PROJECT_DIR/logs/*.log {
    daily
    rotate $LOG_RETENTION
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $RUN_USER $RUN_USER
    copytruncate
}
EOF
    ok "Configured (${LOG_RETENTION}-day retention)"
}

cleanup_webhook() {
    step "Webhook Cleanup"
    [ ! -f "$PROJECT_DIR/.env" ] && return
    TOKEN=$(grep -m1 '^BOT_TOKEN=' "$PROJECT_DIR/.env" | cut -d'=' -f2- \
            | tr -d '"' | tr -d "'" | xargs)
    [ -z "$TOKEN" ] && return
    RESP=$(curl -s -X POST \
        "https://api.telegram.org/bot${TOKEN}/deleteWebhook?drop_pending_updates=true" \
        2>/dev/null)
    echo "$RESP" | grep -q '"ok":true' && ok "Webhook cleared" || warn "Skipped"
}

cmd_install() {
    banner
    detect_server
    preflight_checks
    check_os
    install_system_deps
    install_docker
    ensure_swap
    cleanup_old_services
    check_files
    setup_venv
    setup_env
    setup_telegram_api_container
    cleanup_webhook
    setup_service
    setup_logrotate

    step "Starting Service (Phase 1 — DB Init)"
    systemctl restart "$SERVICE_NAME"
    info "Waiting 15s for bot to create database..."
    sleep 15

    # ── Apply adaptive values now that DB exists ──
    if apply_adaptive_to_db; then
        step "Restarting Service (Phase 2 — Apply Adaptive Config)"
        systemctl restart "$SERVICE_NAME"
        sleep 8
    else
        warn "Adaptive DB tuning skipped"
    fi

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo ""
        echo -e "  ${GRN}${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
        echo -e "  ${GRN}${B}✓ ONLINE — Bot started successfully${R}"
        echo -e "  ${GRN}${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
        echo ""
        echo -e "  ${CYN}▸ Status:${R}   sudo bash install.sh status"
        echo -e "  ${CYN}▸ Logs:${R}     sudo bash install.sh logs"
        echo -e "  ${CYN}▸ Health:${R}   sudo bash install.sh health"
        echo -e "  ${CYN}▸ Restart:${R}  sudo bash install.sh restart"
        echo ""
        echo -e "  ${YEL}ℹ File size limit:${R} ${B}${MAX_FILE_MB} MB${R} (Local Bot API)"
        echo -e "  ${YEL}ℹ Server profile:${R}  ${B}${CPU_CORES}c / ${RAM_MB}MB RAM / ${DISK_TYPE}${R}"
        echo -e "  ${YEL}ℹ Workers:${R}         ${B}${WORKERS}${R}"
        echo -e "  ${YEL}ℹ Concurrent DL:${R}   ${B}${MAX_CONCURRENT}${R}"
        echo ""
    else
        err "Service failed to start — logs:"
        journalctl -u "$SERVICE_NAME" -n 40 --no-pager
        echo ""
        info "Check: tail -50 $PROJECT_DIR/logs/stderr.log"
        exit 1
    fi
}

cmd_start()   { systemctl start   "$SERVICE_NAME" && ok "Started"; }
cmd_stop()    { systemctl stop    "$SERVICE_NAME" && ok "Stopped"; }
cmd_restart() {
    systemctl restart "$SERVICE_NAME"
    sleep 3
    systemctl is-active --quiet "$SERVICE_NAME" && ok "Restarted" || {
        err "Restart failed"; journalctl -u "$SERVICE_NAME" -n 20 --no-pager; }
}
cmd_status()  { systemctl status  "$SERVICE_NAME" --no-pager; }

cmd_logs() {
    echo -e "${CYN}▸ Live logs (Ctrl+C to exit)${R}\n"
    if [ -f "$PROJECT_DIR/logs/stdout.log" ]; then
        tail -f "$PROJECT_DIR/logs/stdout.log" "$PROJECT_DIR/logs/stderr.log"
    else
        journalctl -u "$SERVICE_NAME" -f
    fi
}
cmd_journal() { journalctl -u "$SERVICE_NAME" -f; }

cmd_cleanup() {
    banner
    cleanup_old_services
    cleanup_webhook
    ok "Cleanup done"
}

cmd_update() {
    banner
    step "Updating Packages"
    [ ! -d "$VENV_DIR" ] && { err "venv not found"; exit 1; }
    $AS_USER "$VENV_DIR/bin/pip" install --upgrade -q \
        aiogram yt-dlp gallery-dl curl_cffi aiohttp aiofiles \
        pydantic-settings python-dotenv Pillow
    ok "Packages updated"
    systemctl restart "$SERVICE_NAME"
    sleep 5
    ok "Service restarted"
}

cmd_backup() {
    banner
    step "Database Backup"
    TS=$(date +%Y%m%d_%H%M%S)
    BK="$PROJECT_DIR/backups/manual_${TS}.db"
    if [ -f "$PROJECT_DIR/data/bot.db" ]; then
        if command -v sqlite3 &>/dev/null; then
            sqlite3 "$PROJECT_DIR/data/bot.db" ".backup '$BK'" 2>/dev/null || \
                cp "$PROJECT_DIR/data/bot.db" "$BK"
        else
            cp "$PROJECT_DIR/data/bot.db" "$BK"
        fi
        SIZE=$(du -h "$BK" | cut -f1)
        ok "Backup: $(basename "$BK") ($SIZE)"
    else
        err "bot.db not found"
    fi
}

cmd_cookies() {
    banner
    step "Cookies Status"
    CK="$PROJECT_DIR/data/cookies.txt"
    [ ! -f "$CK" ] && { err "cookies.txt not found"; exit 1; }
    LINES=$(grep -vc '^#' "$CK" 2>/dev/null | tr -d '[:space:]')
    [ "$LINES" -gt 0 ] 2>/dev/null && \
        ok "Entries: $LINES" || warn "File is empty"
    info "Path: $CK"
}

cmd_apply() {
    banner
    detect_server
    apply_adaptive_to_db && {
        systemctl restart "$SERVICE_NAME"
        sleep 5
        ok "Adaptive config applied & service restarted"
    } || err "Failed to apply adaptive config"
}

cmd_uninstall() {
    banner
    step "Uninstalling"
    systemctl stop    "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE" "$LOGROTATE_FILE"
    systemctl daemon-reload
    ok "Service removed"
    info "Project files preserved: $PROJECT_DIR"
}

cmd_health() {
    banner
    step "Health Check"

    CPU_CORES=$(nproc 2>/dev/null || echo 1)
    RAM_MB=$(free -m | awk 'NR==2{print $2}')
    USED_MB=$(free -m | awk 'NR==2{print $3}')
    SWAP_MB=$(free -m | awk 'NR==3{print $2}')
    DISK_AVAIL_MB=$(df -m "$PROJECT_DIR" | awk 'NR==2{print $4}')

    val "CPU cores" "$CPU_CORES"
    val "RAM"       "${USED_MB}/${RAM_MB} MB"
    val "Swap"      "${SWAP_MB} MB"
    val "Disk free" "${DISK_AVAIL_MB} MB"
    val "Run user"  "$RUN_USER"

    echo ""
    detect_main_file && info "Main file: $(basename "$MAIN_FILE")" || warn "Main file not detected"

    systemctl is-active --quiet "$SERVICE_NAME" && \
        ok "Service: active" || err "Service: NOT active"

    systemctl is-active --quiet docker && \
        ok "Docker: active" || err "Docker: NOT active"

    docker ps --format '{{.Names}}' | grep -q "^telegram-bot-api$" && \
        ok "Container: running" || err "Container: NOT running"

    MOUNT=$(docker inspect telegram-bot-api --format '{{range .Mounts}}{{.Source}}{{end}}' 2>/dev/null || echo "")
    [ "$MOUNT" = "$TG_DATA_DIR" ] && \
        ok "Mount: correct" || warn "Mount: $MOUNT"

    HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 \
           http://127.0.0.1:8081/ 2>/dev/null)
    case "$HTTP" in
        200|401|404) ok "Telegram API: online (HTTP $HTTP)" ;;
        *)           err "Telegram API: NOT responding (HTTP $HTTP)" ;;
    esac

    [ -d "$TG_DATA_DIR" ] && {
        CNT=$(find "$TG_DATA_DIR" -type f 2>/dev/null | wc -l)
        ok "TG data dir: $CNT files"
    }

    [ -d "$VENV_DIR" ] && {
        $AS_USER "$VENV_DIR/bin/python" -c 'import PIL' 2>/dev/null && \
            ok "Pillow" || warn "Pillow missing"
        $AS_USER "$VENV_DIR/bin/python" -c 'import gallery_dl' 2>/dev/null && \
            ok "gallery-dl" || warn "gallery-dl missing"
        $AS_USER "$VENV_DIR/bin/python" -c 'import yt_dlp' 2>/dev/null && \
            ok "yt-dlp" || warn "yt-dlp missing"
    }

    [ -f "$PROJECT_DIR/.env" ] && \
        ok ".env (perms $(stat -c '%a' "$PROJECT_DIR/.env"))" || err ".env missing"

    # Check DB adaptive config
    if [ -f "$PROJECT_DIR/data/bot.db" ] && command -v sqlite3 &>/dev/null; then
        echo ""
        step "Database Adaptive Config"
        sqlite3 "$PROJECT_DIR/data/bot.db" \
            "SELECT '  ' || key || ' = ' || value FROM settings WHERE key IN
             ('max_concurrent','max_file_size_mb','max_dl_hour','max_dl_day',
              'max_photo_hour','max_photo_day','max_music_hour','max_music_day',
              'delete_delay') ORDER BY key;" 2>/dev/null
    fi

    echo ""
    step "Active Configuration (.env)"
    [ -f "$PROJECT_DIR/.env" ] && \
        grep -E '^BOT_' "$PROJECT_DIR/.env" | sed 's/^/     /'

    echo ""
    step "Last 15 Log Lines"
    [ -f "$PROJECT_DIR/logs/stdout.log" ] && \
        tail -15 "$PROJECT_DIR/logs/stdout.log" || warn "No stdout.log yet"
}

show_help() {
    banner
    echo -e "  ${B}Usage:${R} sudo bash install.sh ${CYN}<command>${R}\n"
    echo -e "  ${GRN}install${R}     Full adaptive install + start"
    echo -e "  ${GRN}start${R}       Start service"
    echo -e "  ${GRN}stop${R}        Stop service"
    echo -e "  ${GRN}restart${R}     Restart service"
    echo -e "  ${GRN}status${R}      Show service status"
    echo -e "  ${GRN}logs${R}        Tail bot log file"
    echo -e "  ${GRN}journal${R}     Follow systemd journal"
    echo -e "  ${GRN}health${R}      Full health check"
    echo -e "  ${GRN}apply${R}       Re-apply adaptive config to DB"
    echo -e "  ${GRN}cookies${R}     Check cookies status"
    echo -e "  ${GRN}cleanup${R}     Clean old services + webhook"
    echo -e "  ${GRN}update${R}      Update Python packages"
    echo -e "  ${GRN}backup${R}      Backup database"
    echo -e "  ${GRN}uninstall${R}   Remove service\n"
}

case "${1:-}" in
    install)   cmd_install   ;;
    start)     cmd_start     ;;
    stop)      cmd_stop      ;;
    restart)   cmd_restart   ;;
    status)    cmd_status    ;;
    logs)      cmd_logs      ;;
    journal)   cmd_journal   ;;
    health)    cmd_health    ;;
    apply)     cmd_apply     ;;
    cookies)   cmd_cookies   ;;
    cleanup)   cmd_cleanup   ;;
    update)    cmd_update    ;;
    backup)    cmd_backup    ;;
    uninstall) cmd_uninstall ;;
    *)         show_help     ;;
esac