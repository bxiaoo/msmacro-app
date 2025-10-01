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

# Core evdev -> HID usage mapping (full keyboard support)
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
    # Numeric Keypad
    ecodes.KEY_NUMLOCK:83, ecodes.KEY_KPSLASH:84, ecodes.KEY_KPASTERISK:85, ecodes.KEY_KPMINUS:86,
    ecodes.KEY_KPPLUS:87, ecodes.KEY_KPENTER:88, ecodes.KEY_KP1:89, ecodes.KEY_KP2:90,
    ecodes.KEY_KP3:91, ecodes.KEY_KP4:92, ecodes.KEY_KP5:93, ecodes.KEY_KP6:94,
    ecodes.KEY_KP7:95, ecodes.KEY_KP8:96, ecodes.KEY_KP9:97, ecodes.KEY_KP0:98,
    ecodes.KEY_KPDOT:99,
    # Extended function keys
    ecodes.KEY_F13:104, ecodes.KEY_F14:105, ecodes.KEY_F15:106, ecodes.KEY_F16:107,
    ecodes.KEY_F17:108, ecodes.KEY_F18:109, ecodes.KEY_F19:110, ecodes.KEY_F20:111,
    ecodes.KEY_F21:112, ecodes.KEY_F22:113, ecodes.KEY_F23:114, ecodes.KEY_F24:115,
    # Additional system keys
    ecodes.KEY_MENU:118, ecodes.KEY_POWER:102, ecodes.KEY_SLEEP:248,
    # International/Language keys
    ecodes.KEY_102ND:100,  # Non-US \ and |
}

NAME_TO_ECODE = {
    # Modifiers
    "LCTRL": ecodes.KEY_LEFTCTRL,  "LSHIFT": ecodes.KEY_LEFTSHIFT,
    "LALT":  ecodes.KEY_LEFTALT,   "LGUI":   ecodes.KEY_LEFTMETA,
    "RCTRL": ecodes.KEY_RIGHTCTRL, "RSHIFT": ecodes.KEY_RIGHTSHIFT,
    "RALT":  ecodes.KEY_RIGHTALT,  "RGUI":   ecodes.KEY_RIGHTMETA,
    # Letters
    "A": ecodes.KEY_A, "B": ecodes.KEY_B, "C": ecodes.KEY_C, "D": ecodes.KEY_D,
    "E": ecodes.KEY_E, "F": ecodes.KEY_F, "G": ecodes.KEY_G, "H": ecodes.KEY_H,
    "I": ecodes.KEY_I, "J": ecodes.KEY_J, "K": ecodes.KEY_K, "L": ecodes.KEY_L,
    "M": ecodes.KEY_M, "N": ecodes.KEY_N, "O": ecodes.KEY_O, "P": ecodes.KEY_P,
    "Q": ecodes.KEY_Q, "R": ecodes.KEY_R, "S": ecodes.KEY_S, "T": ecodes.KEY_T,
    "U": ecodes.KEY_U, "V": ecodes.KEY_V, "W": ecodes.KEY_W, "X": ecodes.KEY_X,
    "Y": ecodes.KEY_Y, "Z": ecodes.KEY_Z,
    # Numbers
    "1": ecodes.KEY_1, "2": ecodes.KEY_2, "3": ecodes.KEY_3, "4": ecodes.KEY_4,
    "5": ecodes.KEY_5, "6": ecodes.KEY_6, "7": ecodes.KEY_7, "8": ecodes.KEY_8,
    "9": ecodes.KEY_9, "0": ecodes.KEY_0,
    # Controls & punctuation
    "ENTER": ecodes.KEY_ENTER, "RETURN": ecodes.KEY_ENTER,
    "ESCAPE": ecodes.KEY_ESC, "ESC": ecodes.KEY_ESC,
    "BACKSPACE": ecodes.KEY_BACKSPACE, "TAB": ecodes.KEY_TAB, "SPACE": ecodes.KEY_SPACE,
    "MINUS": ecodes.KEY_MINUS, "-": ecodes.KEY_MINUS,
    "EQUAL": ecodes.KEY_EQUAL, "=": ecodes.KEY_EQUAL,
    "LEFTBRACE": ecodes.KEY_LEFTBRACE, "[": ecodes.KEY_LEFTBRACE,
    "RIGHTBRACE": ecodes.KEY_RIGHTBRACE, "]": ecodes.KEY_RIGHTBRACE,
    "BACKSLASH": ecodes.KEY_BACKSLASH, "\\": ecodes.KEY_BACKSLASH,
    "SEMICOLON": ecodes.KEY_SEMICOLON, ";": ecodes.KEY_SEMICOLON,
    "APOSTROPHE": ecodes.KEY_APOSTROPHE, "'": ecodes.KEY_APOSTROPHE,
    "GRAVE": ecodes.KEY_GRAVE, "`": ecodes.KEY_GRAVE,
    "COMMA": ecodes.KEY_COMMA, ",": ecodes.KEY_COMMA,
    "DOT": ecodes.KEY_DOT, ".": ecodes.KEY_DOT,
    "SLASH": ecodes.KEY_SLASH, "/": ecodes.KEY_SLASH,
    "CAPSLOCK": ecodes.KEY_CAPSLOCK,
    # Function keys
    "F1": ecodes.KEY_F1, "F2": ecodes.KEY_F2, "F3": ecodes.KEY_F3, "F4": ecodes.KEY_F4,
    "F5": ecodes.KEY_F5, "F6": ecodes.KEY_F6, "F7": ecodes.KEY_F7, "F8": ecodes.KEY_F8,
    "F9": ecodes.KEY_F9, "F10": ecodes.KEY_F10, "F11": ecodes.KEY_F11, "F12": ecodes.KEY_F12,
    "F13": ecodes.KEY_F13, "F14": ecodes.KEY_F14, "F15": ecodes.KEY_F15, "F16": ecodes.KEY_F16,
    "F17": ecodes.KEY_F17, "F18": ecodes.KEY_F18, "F19": ecodes.KEY_F19, "F20": ecodes.KEY_F20,
    "F21": ecodes.KEY_F21, "F22": ecodes.KEY_F22, "F23": ecodes.KEY_F23, "F24": ecodes.KEY_F24,
    # Navigation
    "RIGHT": ecodes.KEY_RIGHT, "LEFT": ecodes.KEY_LEFT, "DOWN": ecodes.KEY_DOWN, "UP": ecodes.KEY_UP,
    "INSERT": ecodes.KEY_INSERT, "HOME": ecodes.KEY_HOME, "PAGEUP": ecodes.KEY_PAGEUP,
    "DELETE": ecodes.KEY_DELETE, "END": ecodes.KEY_END, "PAGEDOWN": ecodes.KEY_PAGEDOWN,
    "PRINT": ecodes.KEY_PRINT, "SCROLLLOCK": ecodes.KEY_SCROLLLOCK, "PAUSE": ecodes.KEY_PAUSE,
    # Numeric Keypad
    "NUMLOCK": ecodes.KEY_NUMLOCK, "KP_SLASH": ecodes.KEY_KPSLASH, "KP_ASTERISK": ecodes.KEY_KPASTERISK,
    "KP_MINUS": ecodes.KEY_KPMINUS, "KP_PLUS": ecodes.KEY_KPPLUS, "KP_ENTER": ecodes.KEY_KPENTER,
    "KP_1": ecodes.KEY_KP1, "KP_2": ecodes.KEY_KP2, "KP_3": ecodes.KEY_KP3,
    "KP_4": ecodes.KEY_KP4, "KP_5": ecodes.KEY_KP5, "KP_6": ecodes.KEY_KP6,
    "KP_7": ecodes.KEY_KP7, "KP_8": ecodes.KEY_KP8, "KP_9": ecodes.KEY_KP9,
    "KP_0": ecodes.KEY_KP0, "KP_DOT": ecodes.KEY_KPDOT,
    # Alternative keypad names
    "NUMPAD_1": ecodes.KEY_KP1, "NUMPAD_2": ecodes.KEY_KP2, "NUMPAD_3": ecodes.KEY_KP3,
    "NUMPAD_4": ecodes.KEY_KP4, "NUMPAD_5": ecodes.KEY_KP5, "NUMPAD_6": ecodes.KEY_KP6,
    "NUMPAD_7": ecodes.KEY_KP7, "NUMPAD_8": ecodes.KEY_KP8, "NUMPAD_9": ecodes.KEY_KP9,
    "NUMPAD_0": ecodes.KEY_KP0, "NUMPAD_DOT": ecodes.KEY_KPDOT,
    "NUMPAD_SLASH": ecodes.KEY_KPSLASH, "NUMPAD_ASTERISK": ecodes.KEY_KPASTERISK,
    "NUMPAD_MINUS": ecodes.KEY_KPMINUS, "NUMPAD_PLUS": ecodes.KEY_KPPLUS,
    "NUMPAD_ENTER": ecodes.KEY_KPENTER,
    # System keys
    "MENU": ecodes.KEY_MENU, "POWER": ecodes.KEY_POWER, "SLEEP": ecodes.KEY_SLEEP,
}

NAME_TO_ECODE.update({
    "LCTL":    ecodes.KEY_LEFTCTRL,
    "RCTL":    ecodes.KEY_RIGHTCTRL,
    "CTRL":    ecodes.KEY_LEFTCTRL,   # prefer left by default
    "CONTROL": ecodes.KEY_LEFTCTRL,
    "LMETA":   ecodes.KEY_LEFTMETA,
    "RMETA":   ecodes.KEY_RIGHTMETA,
    "LWIN":    ecodes.KEY_LEFTMETA,   # optional Windows-key aliases
    "RWIN":    ecodes.KEY_RIGHTMETA,
})

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

def name_to_usage(key_name: str) -> int:
    """Convert user-friendly key name to HID usage ID.
    Returns 0 if key name is not found."""
    if not key_name or not key_name.strip():
        return 0
    
    key_name_upper = key_name.strip().upper()
    ecode = NAME_TO_ECODE.get(key_name_upper)
    if ecode is None:
        return 0
    
    return usage_from_ecode(ecode)
