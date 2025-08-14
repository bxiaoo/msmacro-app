import sys
# Add the current directory to the path so it can find the 'msmacro' module
sys.path.insert(0, '.')

print("--- Starting test_keyboard.py ---")

try:
    from msmacro import keyboard
    print("DEBUG: Successfully imported 'msmacro.keyboard'")
    keyboard.find_keyboard_event()
    print("--- Finished test_keyboard.py ---")
except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")
