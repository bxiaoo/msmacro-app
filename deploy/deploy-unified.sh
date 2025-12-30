#!/bin/bash
# Deploy MSMacro Unified Service to Raspberry Pi
# This replaces both msmacro.service and msmacro-bridge.service
# Usage: ./deploy-unified.sh [pi-host]

set -e

PI_HOST="${1:-bxiao@10.0.0.2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================"
echo "MSMacro Unified Service Deployment"
echo "========================================"
echo "Target: $PI_HOST"
echo "Project: $PROJECT_DIR"
echo ""

# SSH connection multiplexing - reuse single connection for all SSH/SCP calls
SSH_CONTROL_PATH="/tmp/msmacro-deploy-$$"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CONTROL_PATH -o ControlPersist=60"

# Cleanup function to close master connection on exit
cleanup() {
    ssh -O exit -o ControlPath="$SSH_CONTROL_PATH" "$PI_HOST" 2>/dev/null || true
}
trap cleanup EXIT

# Check if Pi is reachable
echo "[1/8] Checking Pi connectivity..."
if ! ping -c 1 -W 2 "${PI_HOST#*@}" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach ${PI_HOST#*@}"
    echo "Try: ./deploy-unified.sh bxiao@raspberrypi.local"
    exit 1
fi
echo "  OK - Pi is reachable"

# Establish SSH master connection (this is the only password prompt)
echo ""
echo "[2/8] Establishing SSH connection..."
ssh $SSH_OPTS -o ControlMaster=yes -fN "$PI_HOST"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to connect to $PI_HOST"
    exit 1
fi
echo "  OK - SSH connection established"

# Stop and disable conflicting services
echo ""
echo "[3/8] Stopping conflicting services..."
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl stop msmacro-bridge 2>/dev/null || true'
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl disable msmacro-bridge 2>/dev/null || true'
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl stop msmacro 2>/dev/null || true'
echo "  OK - Old services stopped"

# Sync project code to Pi
echo ""
echo "[4/8] Syncing project code..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='*.egg-info' \
    --exclude='.pytest_cache' \
    --exclude='webui/node_modules' \
    --exclude='webui/dist' \
    -e "ssh $SSH_OPTS" \
    "$PROJECT_DIR/" "$PI_HOST:/opt/msmacro-app/"
echo "  OK - Code synced to /opt/msmacro-app/"

# Ensure Python venv exists and install dependencies
echo ""
echo "[5/8] Setting up Python environment..."
ssh $SSH_OPTS "$PI_HOST" '
    cd /opt/msmacro-app
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        echo "Created new virtualenv"
    fi
    .venv/bin/pip install -q -e .
    .venv/bin/pip install -q evdev aiohttp
'
echo "  OK - Python environment ready"

# Install systemd service
echo ""
echo "[6/8] Installing systemd service..."
cat "$PROJECT_DIR/contrib/systemd/msmacro.service" | ssh $SSH_OPTS "$PI_HOST" 'sudo tee /etc/systemd/system/msmacro.service > /dev/null'
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl daemon-reload'
echo "  OK - Service file installed"

# Enable and start service
echo ""
echo "[7/8] Enabling and starting service..."
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl enable msmacro'
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl start msmacro'
echo "  OK - Service enabled and started"

# Check status
echo ""
echo "[8/8] Checking service status..."
echo ""
ssh $SSH_OPTS "$PI_HOST" 'sudo systemctl status msmacro --no-pager' || true

echo ""
echo "========================================"
echo "Deployment complete!"
echo "========================================"
echo ""
echo "The unified msmacro.service now provides:"
echo "  - Full daemon functionality (recording, playback, skills, CV)"
echo "  - Mac bridge (UDP/TCP network communication)"
echo "  - Unix socket IPC for local CLI tools"
echo ""
echo "Network ports:"
echo "  - TCP 5000: Control plane"
echo "  - UDP 5001: Injection commands"
echo "  - UDP 5002: Keyboard events -> Mac"
echo ""
echo "Useful commands:"
echo "  Status:  ssh $PI_HOST 'sudo systemctl status msmacro'"
echo "  Logs:    ssh $PI_HOST 'journalctl -u msmacro -f'"
echo "  Restart: ssh $PI_HOST 'sudo systemctl restart msmacro'"
echo "  Stop:    ssh $PI_HOST 'sudo systemctl stop msmacro'"
echo ""
echo "Test connection from Mac:"
echo "  msmacro check-connection --pi-ip ${PI_HOST#*@}"
echo ""
