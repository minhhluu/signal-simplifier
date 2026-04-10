#!/bin/bash

# Signal Simplifier Management Script
# Usage: ./script.sh {start|stop|status|restart}

APP_DIR=$(dirname "$(readlink -f "$0")")
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
BACKEND_PID_FILE="$APP_DIR/.backend.pid"
FRONTEND_PID_FILE="$APP_DIR/.frontend.pid"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INFO="${CYAN}[INFO]${NC}"
SUCCESS="${GREEN}[SUCCESS]${NC}"
WARN="${YELLOW}[WARNING]${NC}"
ERROR="${RED}[ERROR]${NC}"

# Helper: Rotate logs to keep previous runs
rotate_log() {
    local log_path="$1"
    if [ -f "$log_path" ]; then
        mv "$log_path" "${log_path}.old"
    fi
}

# Helper: Gracefully shut down a PID with timeout
graceful_kill() {
    local pid=$1
    local name=$2
    local timeout=5

    kill "$pid" 2>/dev/null
    while kill -0 "$pid" 2>/dev/null; do
        if [ $timeout -le 0 ]; then
            echo -e "${WARN} $name (PID: $pid) did not stop gracefully. Forcing Kill (SIGKILL)..."
            kill -9 "$pid" 2>/dev/null
            break
        fi
        sleep 1
        ((timeout--))
    done
}

# Helper: Check prerequisites
check_prerequisites() {
    if ! command -v npm &> /dev/null; then
        echo -e "${ERROR} 'npm' is not installed or not in PATH."
        exit 1
    fi
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        echo -e "${ERROR} Python 'venv' environment not found in backend directory."
        exit 1
    fi
}

start() {
    echo -e "${INFO} Starting Signal Simplifier Application..."
    check_prerequisites

    # 1. Start Backend
    if [ -f "$BACKEND_PID_FILE" ] && ps -p $(cat "$BACKEND_PID_FILE") > /dev/null; then
        echo -e "${WARN} Backend is already running (PID: $(cat "$BACKEND_PID_FILE"))"
    else
        echo -e "${INFO} Booting Backend (FastAPI)..."
        rotate_log "$BACKEND_DIR/backend.log"
        cd "$BACKEND_DIR" || exit 1
        source venv/bin/activate
        nohup python main.py > "$BACKEND_DIR/backend.log" 2>&1 &
        echo $! > "$BACKEND_PID_FILE"
        echo -e "${SUCCESS} Backend service active."
    fi

    # 2. Start Frontend
    if [ -f "$FRONTEND_PID_FILE" ] && ps -p $(cat "$FRONTEND_PID_FILE") > /dev/null; then
        echo -e "${WARN} Frontend is already running (PID: $(cat "$FRONTEND_PID_FILE"))"
    else
        echo -e "${INFO} Booting Frontend (Vite)..."
        rotate_log "$FRONTEND_DIR/frontend.log"
        cd "$FRONTEND_DIR" || exit 1
        nohup npm run dev > "$FRONTEND_DIR/frontend.log" 2>&1 &
        echo $! > "$FRONTEND_PID_FILE"
        echo -e "${SUCCESS} Frontend service active."
    fi

    echo ""
    echo -e "${SUCCESS} Application is live!"
    echo "       Frontend: http://localhost:3000"
    echo "       Backend:  http://localhost:8000"
    echo ""
}

stop() {
    echo -e "${INFO} Commencing Graceful Shutdown..."

    # Stop Frontend
    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        echo -e "${INFO} Terminating Frontend (PID: $PID)..."
        pkill -P "$PID" 2>/dev/null # Kill Vite sub-processes first
        graceful_kill "$PID" "Frontend"
        rm -f "$FRONTEND_PID_FILE"
    else
        echo -e "${INFO} Frontend is not running."
    fi

    # Stop Backend
    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        echo -e "${INFO} Terminating Backend (PID: $PID)..."
        graceful_kill "$PID" "Backend"
        rm -f "$BACKEND_PID_FILE"
    else
        echo -e "${INFO} Backend is not running."
    fi

    # Port Cleanup guarantee
    fuser -k 3000/tcp 2>/dev/null
    fuser -k 8000/tcp 2>/dev/null

    echo -e "${SUCCESS} All services stopped safely."
}

status() {
    echo -e "${INFO} Application Status Report:"
    if [ -f "$BACKEND_PID_FILE" ] && ps -p $(cat "$BACKEND_PID_FILE") > /dev/null; then
        echo -e "  ${GREEN}[RUNNING]${NC} Backend Core      (PID: $(cat "$BACKEND_PID_FILE"))"
    else
        echo -e "  ${RED}[STOPPED]${NC} Backend Core"
    fi

    if [ -f "$FRONTEND_PID_FILE" ] && ps -p $(cat "$FRONTEND_PID_FILE") > /dev/null; then
        echo -e "  ${GREEN}[RUNNING]${NC} Frontend UI       (PID: $(cat "$FRONTEND_PID_FILE"))"
    else
        echo -e "  ${RED}[STOPPED]${NC} Frontend UI"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    *)
        echo -e "${WARN} Usage: $0 {start|stop|status|restart}"
        exit 1
esac
