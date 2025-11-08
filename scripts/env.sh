#!/bin/bash
# Environment setup for msmacro scripts
# Usage: source scripts/env.sh

# Detect socket path
if [ -S "/run/user/1000/msmacro.sock" ]; then
    export MSMACRO_SOCKET=/run/user/1000/msmacro.sock
    echo "✓ Using socket: /run/user/1000/msmacro.sock"
elif [ -S "/run/msmacro.sock" ]; then
    export MSMACRO_SOCKET=/run/msmacro.sock
    echo "✓ Using socket: /run/msmacro.sock"
else
    echo "⚠️  No daemon socket found"
    echo "   Start daemon: sudo systemctl start msmacro"
fi

# Set other paths
export MSMACRO_RECDIR=${MSMACRO_RECDIR:-/home/bxiao/.local/share/msmacro/records}
export MSMACRO_EVENTS=${MSMACRO_EVENTS:-/run/user/1000/msmacro.events}

echo "Environment configured for msmacro"
