#!/usr/bin/env python3
"""
Simplified test for keystroke ignore logic without evdev dependencies.
This helps identify issues in the key parsing and filtering logic.
"""

import json
import random
from typing import List, Dict, Optional, Set

# Mock the keymap data that would come from msmacro.utils.keymap
MOCK_NAME_TO_ECODE = {
    # Letters
    "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9, "G": 10, "H": 11, "I": 12, "J": 13,
    "K": 14, "L": 15, "M": 16, "N": 17, "O": 18, "P": 19, "Q": 20, "R": 21, "S": 22,
    "T": 23, "U": 24, "V": 25, "W": 26, "X": 27, "Y": 28, "Z": 29,
    # Modifiers
    "LCTRL": 224, "LSHIFT": 225, "LALT": 226, "CTRL": 224,
}

MOCK_HID_USAGE = {
    # KEY_A through KEY_Z map to ecodes 30-54, HID usage 4-29
    30: 4, 31: 5, 32: 6, 33: 7, 34: 8, 35: 9, 36: 10, 37: 11, 38: 12, 39: 13,
    40: 14, 41: 15, 42: 16, 43: 17, 44: 18, 45: 19, 46: 20, 47: 21, 48: 22,
    49: 23, 50: 24, 51: 25, 52: 26, 53: 27, 54: 28, 55: 29,
    # Special keys
    44: 44,   # KEY_SPACE -> usage 44
    28: 40,   # KEY_ENTER -> usage 40
    15: 43,   # KEY_TAB -> usage 43
    1: 41,    # KEY_ESC -> usage 41
}

MOCK_COMMON_MAPPINGS = {
    'SPACE': 44,     # Direct to HID usage
    'ENTER': 40,
    'TAB': 43,
    'ESCAPE': 41,
    'ESC': 41,
}

def mock_usage_from_ecode(ecode: int) -> int:
    """Mock version of usage_from_ecode."""
    return MOCK_HID_USAGE.get(ecode, 0)

def parse_ignore_keys_debug(ignore_keys: Optional[List[str]]) -> Set[int]:
    """Debug version of Player._parse_ignore_keys with detailed logging."""
    print(f"  🔍 Parsing ignore_keys: {ignore_keys}")
    
    if not ignore_keys:
        print("    → No ignore keys provided, returning empty set")
        return set()
    
    ignore_usages = set()
    for i, key_name in enumerate(ignore_keys):
        print(f"    Key {i+1}: '{key_name}'")
        
        if not key_name or not key_name.strip():
            print(f"      → Empty/whitespace key, skipping")
            continue
            
        key_name_upper = key_name.strip().upper()
        print(f"      → Normalized to: '{key_name_upper}'")
        
        # Try direct lookup in NAME_TO_ECODE first
        if key_name_upper in MOCK_NAME_TO_ECODE:
            ecode = MOCK_NAME_TO_ECODE[key_name_upper]
            usage = mock_usage_from_ecode(ecode)
            print(f"      → Found in NAME_TO_ECODE: ecode={ecode}, usage={usage}")
            if usage:
                ignore_usages.add(usage)
                print(f"      → Added usage {usage} to ignore set")
            else:
                print(f"      → Warning: ecode {ecode} has no HID usage")
            continue
        
        # Try common mappings
        if key_name_upper in MOCK_COMMON_MAPPINGS:
            usage = MOCK_COMMON_MAPPINGS[key_name_upper]
            print(f"      → Found in common mappings: usage={usage}")
            ignore_usages.add(usage)
            print(f"      → Added usage {usage} to ignore set")
        else:
            print(f"      → Not found in any mappings, ignoring")
    
    print(f"    Final ignore_usages: {ignore_usages}")
    return ignore_usages

def test_key_parsing():
    """Test key name parsing with debug output."""
    print("🔍 Testing Key Name Parsing")
    print("=" * 50)
    
    test_cases = [
        ["a"],
        ["A"], 
        ["space"],
        ["SPACE"],
        ["ctrl"],
        ["CTRL"],
        ["a", "space", "ctrl"],
        ["", "space", ""],
        ["invalid_key"],
        []
    ]
    
    for test_keys in test_cases:
        print(f"\nTest case: {test_keys}")
        result = parse_ignore_keys_debug(test_keys)
        print(f"Result: {result}")
        print("-" * 30)

def test_filtering_logic():
    """Test the filtering logic with various scenarios."""
    print("\n🔍 Testing Filtering Logic")
    print("=" * 50)
    
    # Mock actions (what would come from the player)
    test_actions = [
        {"usage": 4, "press_at": 0.0, "dur": 0.1},    # 'a' key (usage 4)
        {"usage": 44, "press_at": 0.2, "dur": 0.05},  # space key (usage 44)
        {"usage": 5, "press_at": 0.4, "dur": 0.1},    # 'b' key (usage 5)
        {"usage": 44, "press_at": 0.6, "dur": 0.05},  # space key again
        {"usage": 6, "press_at": 0.8, "dur": 0.1},    # 'c' key (usage 6)
        {"usage": 224, "press_at": 1.0, "dur": 0.1},  # ctrl key (usage 224)
    ]
    
    print(f"Original actions ({len(test_actions)} total):")
    for i, action in enumerate(test_actions):
        usage = action["usage"]
        key_name = "?"
        if usage == 4: key_name = "a"
        elif usage == 5: key_name = "b"
        elif usage == 6: key_name = "c"
        elif usage == 44: key_name = "space"
        elif usage == 224: key_name = "ctrl"
        print(f"  {i+1}. usage={usage} ({key_name}), press_at={action['press_at']}")
    
    test_scenarios = [
        (["a"], 0.0, "Ignore 'a' with 0% chance (should keep all)"),
        (["a"], 1.0, "Ignore 'a' with 100% chance (should remove all 'a')"),
        (["space"], 1.0, "Ignore 'space' with 100% chance (should remove all space)"),
        (["a", "space"], 1.0, "Ignore 'a' and 'space' with 100% chance"),
        (["invalid"], 1.0, "Ignore invalid key with 100% chance (should keep all)"),
    ]
    
    for ignore_keys, tolerance, description in test_scenarios:
        print(f"\n📋 {description}")
        print(f"   ignore_keys={ignore_keys}, tolerance={tolerance}")
        
        # Parse ignore keys
        ignore_usages = parse_ignore_keys_debug(ignore_keys)
        
        if not ignore_usages or tolerance <= 0:
            print("   → No filtering will occur (no ignore usages or tolerance = 0)")
            continue
        
        # Apply filtering (deterministic for testing)
        random.seed(42)  # Fixed seed for reproducible results
        filtered_actions = []
        ignored_count = 0
        
        for action in test_actions:
            usage = action["usage"]
            if usage in ignore_usages and random.random() < tolerance:
                print(f"   → Ignoring action with usage {usage}")
                ignored_count += 1
                continue
            filtered_actions.append(action)
        
        print(f"   → Kept {len(filtered_actions)}/{len(test_actions)} actions, ignored {ignored_count}")
        for i, action in enumerate(filtered_actions):
            usage = action["usage"]
            print(f"     {i+1}. usage={usage}, press_at={action['press_at']}")

def identify_potential_issues():
    """Identify potential issues in the implementation."""
    print("\n🔍 Identifying Potential Issues")
    print("=" * 50)
    
    issues = []
    
    # Issue 1: Key name mapping
    print("1. Checking key name mappings...")
    common_user_inputs = ['a', 'space', 'ctrl', 'shift', 'enter']
    for key in common_user_inputs:
        usages = parse_ignore_keys_debug([key])
        if not usages:
            issues.append(f"Key '{key}' doesn't map to any HID usage")
        else:
            print(f"   ✅ '{key}' maps to usage(s): {usages}")
    
    # Issue 2: Frontend data format
    print("\n2. Checking frontend data format...")
    frontend_examples = [
        {"ignore_keys": ["a", "space", "ctrl"], "ignore_tolerance": 0.1},
        {"ignore_keys": ["", "", ""], "ignore_tolerance": 0.0},
        {"ignore_keys": [], "ignore_tolerance": 0.0},
    ]
    
    for example in frontend_examples:
        print(f"   Frontend data: {example}")
        usages = parse_ignore_keys_debug(example["ignore_keys"])
        tolerance = example["ignore_tolerance"]
        will_filter = bool(usages and tolerance > 0)
        print(f"   → Will apply filtering: {will_filter}")
    
    # Issue 3: Random seed behavior
    print("\n3. Checking randomization behavior...")
    ignore_usages = {4}  # 'a' key
    tolerance = 0.5      # 50% chance
    
    test_action = {"usage": 4, "press_at": 0.0, "dur": 0.1}
    
    ignored_count = 0
    kept_count = 0
    
    for i in range(100):
        if test_action["usage"] in ignore_usages and random.random() < tolerance:
            ignored_count += 1
        else:
            kept_count += 1
    
    print(f"   Over 100 trials with 50% tolerance:")
    print(f"   → Ignored: {ignored_count}, Kept: {kept_count}")
    print(f"   → Actual ignore rate: {ignored_count/100:.1%}")
    
    if issues:
        print(f"\n❌ Found {len(issues)} potential issues:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print(f"\n✅ No obvious issues found in key mapping")

def main():
    """Run all tests."""
    print("🚀 Simplified Keystroke Ignore Logic Test")
    print("=" * 60)
    
    test_key_parsing()
    test_filtering_logic()
    identify_potential_issues()
    
    print("\n" + "=" * 60)
    print("🔧 Next Steps for Debugging:")
    print("1. Check if the frontend is actually sending ignore_keys and ignore_tolerance")
    print("2. Add logging in the Player.play() method to see if randomization code is reached")
    print("3. Verify the API data flow: frontend → handlers.py → daemon.py → player.py")
    print("4. Test with a simple recording that has keystrokes you're trying to ignore")
    print("5. Use browser dev tools to inspect the actual API requests being sent")

if __name__ == "__main__":
    main()