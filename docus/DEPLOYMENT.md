# MSMacro Deployment Quick Reference

## Fresh Installation on Raspberry Pi

```bash
# 1. Clone repository
git clone https://github.com/your-repo/msmacro-app.git
cd msmacro-app

# 2. Install Python dependencies
pip3 install -e .

# 3. Build frontend
cd webui
npm install
npm run build
cd ..

# 4. Configure (optional - defaults should work)
export MSMACRO_RECDIR=~/msmacro-recordings
export MSMACRO_SOCKET=/run/msmacro.sock

# 5. Start daemon
python3 -m msmacro daemon &

# 6. Access web UI
# Open browser to: http://<pi-ip>:8787
```

## Update Existing Installation

```bash
# 1. Navigate to repo
cd ~/msmacro-app

# 2. Pull latest changes
git pull origin main

# 3. Update Python dependencies (if changed)
pip3 install -e .

# 4. Rebuild frontend
cd webui
npm run build
cd ..

# 5. Restart daemon
python3 -m msmacro ctl stop
python3 -m msmacro daemon &

# 6. Clear browser cache
# Browser: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
```

## Quick Verification

```bash
# Check daemon status
python3 -m msmacro ctl status

# Test API
curl http://localhost:8787/api/status | jq
curl http://localhost:8787/api/system/stats | jq

# Check logs (if using systemd)
journalctl -u msmacro-daemon -f
```

## System Stats Feature

**New in this version**: Real-time performance monitoring in header

- **CPU Usage**: Green < 60%, Yellow 60-79%, Red ≥ 80%
- **RAM Usage**: Green < 70%, Yellow 70-84%, Red ≥ 85%
- **Temperature**: Green < 60°C, Yellow 60-69°C, Red ≥ 70°C (Pi only)
- **Update Rate**: Every 3 seconds

## Troubleshooting

### Stats Not Showing

```bash
# Verify psutil installed
python3 -c "import psutil; print(psutil.__version__)"

# If not installed
pip3 install psutil

# Restart daemon
python3 -m msmacro ctl stop
python3 -m msmacro daemon &
```

### Map Configuration Not Working

See: `docus/testing/MAP_CONFIG_TESTING_GUIDE.md`

### High CPU/RAM Usage

See: `docus/07_SYSTEM_MONITORING.md` - Performance Optimization section

## Documentation

- **User Guides**: `docus/` directory (00-07 series)
- **Testing Guides**: `docus/testing/` directory
- **Implementation Notes**: `docus/archived/` directory

## Support

For issues:
1. Check documentation in `docus/`
2. Review troubleshooting sections
3. Check browser console (F12)
4. Review daemon logs

---

**Quick Links**:
- System Monitoring: `docus/07_SYSTEM_MONITORING.md`
- Map Configuration: `docus/06_MAP_CONFIGURATION.md`
- API Reference: `docus/05_API_REFERENCE.md`
