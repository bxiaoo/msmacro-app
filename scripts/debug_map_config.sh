#!/bin/bash
# Debug map configuration file location mismatch

echo "======================================================================"
echo "MAP CONFIGURATION DIAGNOSTIC"
echo "======================================================================"

echo ""
echo "1. USER IDENTITY CHECK"
echo "----------------------------------------------------------------------"
echo "Current user: $(whoami)"
echo "Current UID: $(id -u)"
echo "Home directory: $HOME"

echo ""
echo "2. DAEMON USER CHECK"
echo "----------------------------------------------------------------------"
DAEMON_PID=$(pgrep -f "python.*msmacro.*daemon" | head -1)
if [ -n "$DAEMON_PID" ]; then
    echo "✓ Daemon process found (PID: $DAEMON_PID)"
    DAEMON_USER=$(ps -o user= -p $DAEMON_PID)
    DAEMON_HOME=$(sudo -u $DAEMON_USER bash -c 'echo $HOME')
    echo "  Daemon user: $DAEMON_USER"
    echo "  Daemon home: $DAEMON_HOME"
else
    echo "✗ No daemon process found"
    DAEMON_USER=""
    DAEMON_HOME=""
fi

echo ""
echo "3. WEB SERVER USER CHECK"
echo "----------------------------------------------------------------------"
WEB_PID=$(pgrep -f "python.*msmacro.web.server" | head -1)
if [ -n "$WEB_PID" ]; then
    echo "✓ Web server process found (PID: $WEB_PID)"
    WEB_USER=$(ps -o user= -p $WEB_PID)
    WEB_HOME=$(sudo -u $WEB_USER bash -c 'echo $HOME')
    echo "  Web user: $WEB_USER"
    echo "  Web home: $WEB_HOME"
else
    echo "✗ No web server process found"
    WEB_USER=""
    WEB_HOME=""
fi

echo ""
echo "4. CONFIG FILE LOCATIONS"
echo "----------------------------------------------------------------------"

# Current user's config
CURRENT_CONFIG="$HOME/.local/share/msmacro/map_configs.json"
echo "Current user config: $CURRENT_CONFIG"
if [ -f "$CURRENT_CONFIG" ]; then
    echo "  ✓ EXISTS"
    echo "  Size: $(stat -c %s "$CURRENT_CONFIG" 2>/dev/null || stat -f %z "$CURRENT_CONFIG" 2>/dev/null) bytes"
    echo "  Modified: $(stat -c %y "$CURRENT_CONFIG" 2>/dev/null || stat -f "%Sm" "$CURRENT_CONFIG" 2>/dev/null)"
    echo "  Owner: $(stat -c '%U:%G' "$CURRENT_CONFIG" 2>/dev/null || stat -f '%Su:%Sg' "$CURRENT_CONFIG" 2>/dev/null)"
else
    echo "  ✗ DOES NOT EXIST"
fi

# Daemon user's config
if [ -n "$DAEMON_HOME" ]; then
    DAEMON_CONFIG="$DAEMON_HOME/.local/share/msmacro/map_configs.json"
    echo ""
    echo "Daemon user config: $DAEMON_CONFIG"
    if [ -f "$DAEMON_CONFIG" ]; then
        echo "  ✓ EXISTS"
        echo "  Size: $(stat -c %s "$DAEMON_CONFIG" 2>/dev/null || stat -f %z "$DAEMON_CONFIG" 2>/dev/null) bytes"
        echo "  Modified: $(stat -c %y "$DAEMON_CONFIG" 2>/dev/null || stat -f "%Sm" "$DAEMON_CONFIG" 2>/dev/null)"
        echo "  Owner: $(stat -c '%U:%G' "$DAEMON_CONFIG" 2>/dev/null || stat -f '%Su:%Sg' "$DAEMON_CONFIG" 2>/dev/null)"
    else
        echo "  ✗ DOES NOT EXIST"
    fi
fi

# Web user's config
if [ -n "$WEB_HOME" ] && [ "$WEB_HOME" != "$DAEMON_HOME" ]; then
    WEB_CONFIG="$WEB_HOME/.local/share/msmacro/map_configs.json"
    echo ""
    echo "Web user config: $WEB_CONFIG"
    if [ -f "$WEB_CONFIG" ]; then
        echo "  ✓ EXISTS"
        echo "  Size: $(stat -c %s "$WEB_CONFIG" 2>/dev/null || stat -f %z "$WEB_CONFIG" 2>/dev/null) bytes"
        echo "  Modified: $(stat -c %y "$WEB_CONFIG" 2>/dev/null || stat -f "%Sm" "$WEB_CONFIG" 2>/dev/null)"
        echo "  Owner: $(stat -c '%U:%G' "$WEB_CONFIG" 2>/dev/null || stat -f '%Su:%Sg' "$WEB_CONFIG" 2>/dev/null)"
    else
        echo "  ✗ DOES NOT EXIST"
    fi
fi

echo ""
echo "5. CONFIG FILE CONTENTS"
echo "----------------------------------------------------------------------"

# Function to show config contents
show_config() {
    local path=$1
    local label=$2

    if [ -f "$path" ]; then
        echo ""
        echo "$label:"
        echo "----------------------------------------"
        cat "$path" | python3 -m json.tool 2>/dev/null || cat "$path"
        echo "----------------------------------------"
    fi
}

show_config "$CURRENT_CONFIG" "Current user's config"

if [ -n "$DAEMON_CONFIG" ] && [ "$DAEMON_CONFIG" != "$CURRENT_CONFIG" ]; then
    if [ -r "$DAEMON_CONFIG" ]; then
        show_config "$DAEMON_CONFIG" "Daemon user's config"
    else
        echo ""
        echo "Daemon user's config (requires sudo):"
        echo "----------------------------------------"
        sudo cat "$DAEMON_CONFIG" 2>/dev/null | python3 -m json.tool 2>/dev/null || sudo cat "$DAEMON_CONFIG" 2>/dev/null
        echo "----------------------------------------"
    fi
fi

echo ""
echo "6. ENVIRONMENT VARIABLES"
echo "----------------------------------------------------------------------"
echo "Current process:"
printenv | grep MSMACRO || echo "  (no MSMACRO_* variables set)"

if [ -n "$DAEMON_PID" ]; then
    echo ""
    echo "Daemon process:"
    sudo cat /proc/$DAEMON_PID/environ 2>/dev/null | tr '\0' '\n' | grep MSMACRO || echo "  (no MSMACRO_* variables set)"
fi

echo ""
echo "======================================================================"
echo "DIAGNOSIS"
echo "======================================================================"

# Determine if there's a user mismatch
ISSUE_FOUND=false

if [ "$(whoami)" != "$DAEMON_USER" ]; then
    echo "⚠️  WARNING: Current user ($(whoami)) differs from daemon user ($DAEMON_USER)"
    ISSUE_FOUND=true
fi

if [ -f "$CURRENT_CONFIG" ] && [ -f "$DAEMON_CONFIG" ] && [ "$CURRENT_CONFIG" != "$DAEMON_CONFIG" ]; then
    echo "❌ PROBLEM: Multiple config files exist in different locations!"
    echo ""
    echo "This is the root cause! The web UI is writing to:"
    echo "  $CURRENT_CONFIG"
    echo ""
    echo "But the daemon is reading from:"
    echo "  $DAEMON_CONFIG"
    echo ""
    ISSUE_FOUND=true
fi

if [ ! -f "$DAEMON_CONFIG" ]; then
    echo "❌ PROBLEM: Daemon's config file does not exist!"
    echo ""
    echo "Expected location: $DAEMON_CONFIG"
    echo ""
    ISSUE_FOUND=true
fi

if [ "$ISSUE_FOUND" = true ]; then
    echo "SOLUTION:"
    echo "----------------------------------------------------------------------"
    echo "Option 1: Use a shared config location (RECOMMENDED)"
    echo "  Set MSMACRO_CONFIG_DIR environment variable for all services:"
    echo "    export MSMACRO_CONFIG_DIR=/etc/msmacro"
    echo "  OR"
    echo "    export MSMACRO_CONFIG_DIR=/opt/msmacro-app/config"
    echo ""
    echo "Option 2: Copy config to daemon user's home"
    echo "  sudo cp $CURRENT_CONFIG $DAEMON_CONFIG"
    echo "  sudo chown $DAEMON_USER:$DAEMON_USER $DAEMON_CONFIG"
    echo ""
    echo "Option 3: Create symlink"
    echo "  sudo -u $DAEMON_USER mkdir -p $(dirname $DAEMON_CONFIG)"
    echo "  sudo -u $DAEMON_USER ln -s $CURRENT_CONFIG $DAEMON_CONFIG"
else
    echo "✅ Config file locations appear correct"
    echo ""
    echo "If you still see 'No active map configuration', check:"
    echo "  1. Daemon logs for cv_reload_config command"
    echo "  2. Active config field in the JSON file"
    echo "  3. is_active flag on the config object"
fi

echo "======================================================================"
