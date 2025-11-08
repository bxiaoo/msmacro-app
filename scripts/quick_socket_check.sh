#!/bin/bash
# Quick socket path diagnostic

echo "======================================================================"
echo "SOCKET PATH DIAGNOSTIC"
echo "======================================================================"

echo ""
echo "1. CHECKING COMMON SOCKET LOCATIONS"
echo "----------------------------------------------------------------------"

SOCKET_PATHS=(
    "/run/msmacro.sock"
    "/run/user/1000/msmacro.sock"
    "/run/user/$(id -u)/msmacro.sock"
    "/tmp/msmacro.sock"
)

FOUND_SOCKET=""

for socket in "${SOCKET_PATHS[@]}"; do
    if [ -S "$socket" ]; then
        echo "✓ FOUND: $socket"
        ls -l "$socket"
        FOUND_SOCKET="$socket"
    else
        echo "✗ Not found: $socket"
    fi
done

echo ""
echo "2. SEARCHING FOR ANY msmacro.sock FILES"
echo "----------------------------------------------------------------------"
find /run /tmp -name "msmacro.sock" 2>/dev/null

echo ""
echo "3. CHECKING DAEMON STATUS"
echo "----------------------------------------------------------------------"
if systemctl is-active --quiet msmacro; then
    echo "✓ msmacro.service is ACTIVE"
    systemctl status msmacro --no-pager | head -20
else
    echo "✗ msmacro.service is NOT ACTIVE"
    echo ""
    echo "Service status:"
    systemctl status msmacro --no-pager | head -20
fi

echo ""
echo "4. CHECKING DAEMON PROCESS"
echo "----------------------------------------------------------------------"
DAEMON_PID=$(pgrep -f "python.*msmacro.*daemon")
if [ -n "$DAEMON_PID" ]; then
    echo "✓ Daemon process found (PID: $DAEMON_PID)"
    ps aux | grep "$DAEMON_PID" | grep -v grep
else
    echo "✗ No daemon process found"
fi

echo ""
echo "5. CHECKING ENVIRONMENT VARIABLES"
echo "----------------------------------------------------------------------"
if [ -n "$MSMACRO_SOCKET" ]; then
    echo "MSMACRO_SOCKET is set: $MSMACRO_SOCKET"
    if [ -S "$MSMACRO_SOCKET" ]; then
        echo "  ✓ Socket exists at this path"
    else
        echo "  ✗ Socket does NOT exist at this path!"
    fi
else
    echo "MSMACRO_SOCKET is not set (will use default)"
fi

echo ""
echo "6. CHECKING DAEMON LOGS FOR SOCKET INFO"
echo "----------------------------------------------------------------------"
echo "Last 30 lines mentioning 'socket' or 'IPC':"
journalctl -u msmacro --no-pager | grep -iE "(socket|ipc)" | tail -30

echo ""
echo "======================================================================"
echo "DIAGNOSIS"
echo "======================================================================"

if [ -n "$FOUND_SOCKET" ]; then
    echo "✅ Socket found at: $FOUND_SOCKET"
    echo ""
    echo "To fix the scripts, run:"
    echo "  export MSMACRO_SOCKET=$FOUND_SOCKET"
    echo "  .venv/bin/python scripts/debug_cv_capture.py"
else
    echo "❌ NO SOCKET FOUND!"
    echo ""
    echo "Possible issues:"
    echo "  1. Daemon is not running"
    echo "  2. Daemon failed to start (check logs above)"
    echo "  3. Daemon crashed during startup"
    echo ""
    echo "Try:"
    echo "  1. Check daemon logs:"
    echo "     journalctl -u msmacro -n 50"
    echo "  2. Restart daemon:"
    echo "     sudo systemctl restart msmacro"
    echo "  3. Check for errors:"
    echo "     journalctl -u msmacro -f"
fi

echo "======================================================================"
