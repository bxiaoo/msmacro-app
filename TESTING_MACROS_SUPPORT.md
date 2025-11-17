# macOS Support Testing Guide

## Quick Test

### 1. Test Platform Detection
```bash
python3 -c "from msmacro.io.platform_abstraction import get_platform_info; import json; print(json.dumps(get_platform_info(), indent=2))"
```

### 2. Test Mock Keyboard
```bash
python3 -c "from msmacro.io.keyboard import find_keyboard_event; print(find_keyboard_event())"
```

### 3. Test Mock HID
```bash
python3 -c "from msmacro.io.hidio import HIDWriter; h = HIDWriter(); h.send(0, [4,5,6]); print('OK')"
```

### 4. Start Daemon (requires psutil)
```bash
# Install dependencies first:
pip install psutil aiohttp

# Start daemon:
python -m msmacro daemon
```

### 5. Test Web UI
```bash
# After daemon starts, visit:
open http://localhost:8787
```

## Expected Behavior

- ✅ Daemon starts without errors
- ⚠️  Warnings about mock keyboard/HID (expected)
- ✅ Web UI accessible
- ✅ CV capture works (with real capture card)
- ✅ Object detection works
- ⚠️  Keyboard/HID features are mocked (logged only)

## Troubleshooting

If daemon fails to start:
1. Check psutil is installed: `pip show psutil`
2. Check aiohttp is installed: `pip show aiohttp`
3. Look for import errors in output
4. Check platform info is correct

