import asyncio
from evdev import InputDevice, ecodes
from .hidio import HIDWriter
from .recorder import Recorder
from .keymap import is_modifier, mod_bit, usage_from_ecode, parse_hotkey

class Bridge:
    """
    BRIDGE:
      LALT+R -> "RECORD"
      LALT+Q -> "STOP"
      (optional) extra choices (e.g. LALT+S/P/D) → returns the choice label
    RECORD:
      LALT+Q -> stop recording, return actions
    """

    def __init__(self, evdev_path: str, hidg_path: str,
                 stop_hotkey: str = "LALT+Q",
                 record_hotkey: str = "LALT+R",
                 grab: bool = True,
                 extra_hotkeys: dict[str,str] | None = None):
        self.dev = InputDevice(evdev_path)
        self.w = HIDWriter(hidg_path)
        self.grab = grab

        self.modmask = 0
        self.down = set()
        self.rec = Recorder()

        # main hotkeys
        self.stop_mod_ecode, self.stop_key_ecode = parse_hotkey(stop_hotkey)
        self.stop_key_usage = usage_from_ecode(self.stop_key_ecode)
        self.rec_mod_ecode,  self.rec_key_ecode  = parse_hotkey(record_hotkey)
        self.rec_key_usage  = usage_from_ecode(self.rec_key_ecode)

        # optional extra hotkeys: {"LALT+S":"CHOICE_SAVE", ...}
        self.extra = {}
        if extra_hotkeys:
            for spec, label in extra_hotkeys.items():
                mod_ec, key_ec = parse_hotkey(spec)
                self.extra[(mod_ec, usage_from_ecode(key_ec))] = label

        self._stopping_armed = False
        self._record_armed = False
        self._armed_extra: tuple[int,int,str] | None = None

    def _hot_active(self, mod_ecode, key_usage) -> bool:
        mod_down = (self.modmask & mod_bit(mod_ecode)) != 0
        return mod_down and (key_usage in self.down)

    def _extra_active(self):
        for (m_ec, u), label in self.extra.items():
            if self._hot_active(m_ec, u):
                return (m_ec, u, label)
        return None

    def _send_filtered(self):
        keys = set(self.down)
        modm = self.modmask & 0xFF
        # strip chords only while active
        if self._hot_active(self.stop_mod_ecode, self.stop_key_usage):
            keys.discard(self.stop_key_usage)
            modm &= (~mod_bit(self.stop_mod_ecode)) & 0xFF
        if self._hot_active(self.rec_mod_ecode, self.rec_key_usage):
            keys.discard(self.rec_key_usage)
            modm &= (~mod_bit(self.rec_mod_ecode)) & 0xFF
        e = self._extra_active()
        if e:
            m_ec, u, _ = e
            keys.discard(u)
            modm &= (~mod_bit(m_ec)) & 0xFF
        self.w.send(modm, {k for k in keys if k})

    async def run_bridge(self) -> str:
        """Return 'RECORD', 'STOP' or an extra choice label (if configured)."""
        if self.grab:
            try: self.dev.grab()
            except: pass
        self._stopping_armed = False
        self._record_armed = False
        self._armed_extra = None

        try:
            async for ev in self.dev.async_read_loop():
                if ev.type != ecodes.EV_KEY: continue
                code, val = ev.code, ev.value
                if val == 2: continue
                is_down = (val == 1)

                stop_prev = self._hot_active(self.stop_mod_ecode, self.stop_key_usage)
                rec_prev  = self._hot_active(self.rec_mod_ecode,  self.rec_key_usage)
                extra_prev = self._extra_active()

                if is_modifier(code):
                    bit = mod_bit(code)
                    if is_down: self.modmask |= bit
                    else:       self.modmask &= (~bit) & 0xFF
                else:
                    usage = usage_from_ecode(code)
                    if is_down: self.down.add(usage)
                    else:       self.down.discard(usage)

                stop_curr = self._hot_active(self.stop_mod_ecode, self.stop_key_usage)
                rec_curr  = self._hot_active(self.rec_mod_ecode,  self.rec_key_usage)
                extra_curr = self._extra_active()

                # STOP: arm on activation, act on release
                if (not self._stopping_armed) and (not stop_prev) and stop_curr:
                    self._stopping_armed = True
                    self._send_filtered(); continue
                if self._stopping_armed and (not stop_curr) and (code in (self.stop_mod_ecode, self.stop_key_ecode)) and (val == 0):
                    self.w.all_up(); return "STOP"

                # RECORD
                if (not self._record_armed) and (not rec_prev) and rec_curr:
                    self._record_armed = True
                    self._send_filtered(); continue
                if self._record_armed and (not rec_curr) and (code in (self.rec_mod_ecode, self.rec_key_ecode)) and (val == 0):
                    self.w.all_up(); return "RECORD"

                # EXTRA
                if (self._armed_extra is None) and (extra_prev is None) and (extra_curr is not None):
                    self._armed_extra = extra_curr
                    self._send_filtered(); continue
                if self._armed_extra and (extra_curr is None) and (code in (self._armed_extra[0],) or usage_from_ecode(code)==self._armed_extra[1]) and (val == 0):
                    _, _, label = self._armed_extra
                    self.w.all_up(); return label

                self._send_filtered()
        finally:
            try: self.dev.ungrab()
            except: pass
            try: self.dev.close()
            except: pass
            self.w.all_up()

    async def run_record(self):
        """Return list of actions; forwards live during record."""
        if self.grab:
            try: self.dev.grab()
            except: pass
        self.rec.start()
        self._stopping_armed = False
        try:
            async for ev in self.dev.async_read_loop():
                if ev.type != ecodes.EV_KEY: continue
                code, val = ev.code, ev.value
                if val == 2: continue
                is_down = (val == 1)

                stop_prev = self._hot_active(self.stop_mod_ecode, self.stop_key_usage)

                if is_modifier(code):
                    bit = mod_bit(code)
                    if is_down: self.modmask |= bit
                    else:       self.modmask &= (~bit) & 0xFF
                    usage = usage_from_ecode(code)
                else:
                    usage = usage_from_ecode(code)
                    if is_down: self.down.add(usage)
                    else:       self.down.discard(usage)

                stop_curr = self._hot_active(self.stop_mod_ecode, self.stop_key_usage)

                # record all keys except while a chord is active
                if not self._hot_active(self.stop_mod_ecode, self.stop_key_usage) and \
                   not self._hot_active(self.rec_mod_ecode,  self.rec_key_usage):
                    if not is_modifier(code):
                        if is_down: self.rec.on_down(usage)
                        else:       self.rec.on_up(usage)

                if (not self._stopping_armed) and (not stop_prev) and stop_curr:
                    self._stopping_armed = True
                    self._send_filtered(); continue
                if self._stopping_armed and (not stop_curr) and (code in (self.stop_mod_ecode, self.stop_key_ecode)) and (val == 0):
                    break

                self._send_filtered()
        finally:
            try: self.dev.ungrab()
            except: pass
            try: self.dev.close()
            except: pass
            self.w.all_up()

        return self.rec.actions
