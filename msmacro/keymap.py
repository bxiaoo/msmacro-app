from evdev import ecodes

# Modifier bits (for byte0 of HID report)
MOD_BITS = {
    ecodes.KEY_LEFTCTRL:   1 << 0,
    ecodes.KEY_LEFTSHIFT:  1 << 1,
    ecodes.KEY_LEFTALT:    1 << 2,
    ecodes.KEY_LEFTMETA:   1 << 3,
    ecodes.KEY_RIGHTCTRL:  1 << 4,
    ecodes.KEY_RIGHTSHIFT: 1 << 5,
    ecodes.KEY_RIGHTALT:   1 << 6,
    ecodes.KEY_RIGHTMETA:  1 << 7,
}

# Modifier usages in the HID usage table (224..231)
MOD_USAGE = {
    ecodes.KEY_LEFTCTRL:   224,
    ecodes.KEY_LEFTSHIFT:  225,
    ecodes.KEY_LEFTALT:    226,
    ecodes.KEY_LEFTMETA:   227,
    ecodes.KEY_RIGHTCTRL:  228,
    ecodes.KEY_RIGHTSHIFT: 229,
    ecodes.KEY_RIGHTALT:   230,
    ecodes.KEY_RIGHTMETA:  231,
}

# Core evdev -> HID usage mapping (extend as needed)
HID_USAGE = {
    # Letters
    ecodes.KEY_A:4, ecodes.KEY_B:5, ecodes.KEY_C:6, ecodes.KEY_D:7, ecodes.KEY_E:8,
    ecodes.KEY_F:9, ecodes.KEY_G:10, ecodes.KEY_H:11, ecodes.KEY_I:12, ecodes.KEY_J:13,
    ecodes.KEY_K:14, ecodes.KEY_L:15, ecodes.KEY_M:16, ecodes.KEY_N:17, ecodes.KEY_O:18,
    ecodes.KEY_P:19, ecodes.KEY_Q:20, ecodes.KEY_R:21, ecodes.KEY_S:22, ecodes.KEY_T:23,
    ecodes.KEY_U:24, ecodes.KEY_V:25, ecodes.KEY_W:26, ecodes.KEY_X:27, ecodes.KEY_Y:28,
    ecodes.KEY_Z:29,
    # Numbers
    ecodes.KEY_1:30, ecodes.KEY_2:31, ecodes.KEY_3:32, ecodes.KEY_4:33, ecodes.KEY_5:34,
    ecodes.KEY_6:35, ecodes.KEY_7:36, ecodes.KEY_8:37, ecodes.KEY_9:38, ecodes.KEY_0:39,
    # Controls & punctuation
    ecodes.KEY_ENTER:40, ecodes.KEY_ESC:41, ecodes.KEY_BACKSPACE:42, ecodes.KEY_TAB:43,
    ecodes.KEY_SPACE:44, ecodes.KEY_MINUS:45, ecodes.KEY_EQUAL:46, ecodes.KEY_LEFTBRACE:47,
    ecodes.KEY_RIGHTBRACE:48, ecodes.KEY_BACKSLASH:49, ecodes.KEY_SEMICOLON:51,
    ecodes.KEY_APOSTROPHE:52, ecodes.KEY_GRAVE:53, ecodes.KEY_COMMA:54, ecodes.KEY_DOT:55,
    ecodes.KEY_SLASH:56, ecodes.KEY_CAPSLOCK:57,
    # Function keys
    ecodes.KEY_F1:58, ecodes.KEY_F2:59, ecodes.KEY_F3:60, ecodes.KEY_F4:61, ecodes.KEY_F5:62,
    ecodes.KEY_F6:63, ecodes.KEY_F7:64, ecodes.KEY_F8:65, ecodes.KEY_F9:66, ecodes.KEY_F10:67,
    ecodes.KEY_F11:68, ecodes.KEY_F12:69,
    # Navigation
    ecodes.KEY_PRINT:70, ecodes.KEY_SCROLLLOCK:71, ecodes.KEY_PAUSE:72, ecodes.KEY_INSERT:73,
    ecodes.KEY_HOME:74, ecodes.KEY_PAGEUP:75, ecodes.KEY_DELETE:76, ecodes.KEY_END:77,
    ecodes.KEY_PAGEDOWN:78, ecodes.KEY_RIGHT:79, ecodes.KEY_LEFT:80, ecodes.KEY_DOWN:81,
    ecodes.KEY_UP:82,
}

NAME_TO_ECODE = {
    # Modifiers
    "LCTRL": ecodes.KEY_LEFTCTRL,  "LSHIFT": ecodes.KEY_LEFTSHIFT,
    "LALT":  ecodes.KEY_LEFTALT,   "LGUI":   ecodes.KEY_LEFTMETA,
    "RCTRL": ecodes.KEY_RIGHTCTRL, "RSHIFT": ecodes.KEY_RIGHTSHIFT,
    "RALT":  ecodes.KEY_RIGHTALT,  "RGUI":   ecodes.KEY_RIGHTMETA,
    # Letters subset (extend as needed)
    "A": ecodes.KEY_A, "B": ecodes.KEY_B, "C": ecodes.KEY_C, "D": ecodes.KEY_D,
    "E": ecodes.KEY_E, "F": ecodes.KEY_F, "G": ecodes.KEY_G, "H": ecodes.KEY_H,
    "I": ecodes.KEY_I, "J": ecodes.KEY_J, "K": ecodes.KEY_K, "L": ecodes.KEY_L,
    "M": ecodes.KEY_M, "N": ecodes.KEY_N, "O": ecodes.KEY_O, "P": ecodes.KEY_P,
    "Q": ecodes.KEY_Q, "R": ecodes.KEY_R, "S": ecodes.KEY_S, "T": ecodes.KEY_T,
    "U": ecodes.KEY_U, "V": ecodes.KEY_V, "W": ecodes.KEY_W, "X": ecodes.KEY_X,
    "Y": ecodes.KEY_Y, "Z": ecodes.KEY_Z,
}

# ---- helpers ----

def is_modifier(ecode: int) -> bool:
    return ecode in MOD_BITS

def mod_bit(ecode: int) -> int:
    return MOD_BITS.get(ecode, 0)

def usage_from_ecode(ecode: int) -> int:
    if is_modifier(ecode):
        return MOD_USAGE.get(ecode, 0)
    return HID_USAGE.get(ecode, 0)

def parse_hotkey(spec: str) -> tuple[int, int]:
    """Return (modifier_ecode, key_ecode) from 'LALT+Q' style string.
    Raises ValueError for invalid spec."""
    parts = (spec or "").split("+")
    if len(parts) != 2:
        raise ValueError("Hotkey must be MOD+KEY (e.g., LALT+Q)")
    mod_name, key_name = parts[0].strip().upper(), parts[1].strip().upper()
    mod_ecode = NAME_TO_ECODE.get(mod_name)
    key_ecode = NAME_TO_ECODE.get(key_name)
    if mod_ecode not in MOD_BITS or key_ecode is None or key_ecode in MOD_BITS:
        raise ValueError("Invalid hotkey; require one modifier + one non-mod key")
    return mod_ecode, key_ecode
