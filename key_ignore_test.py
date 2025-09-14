#!/usr/bin/env python3
"""
Comprehensive test for keystroke ignore logic.
Tests the entire data flow from frontend to player.
"""

import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

def test_frontend_data_format():
    """Test 1: Verify frontend sends correct data format"""
    print("🔍 Test 1: Frontend Data Format")
    print("=" * 50)
    
    # These are the expected formats from the frontend
    sample_requests = [
        {
            "names": ["test.json"],
            "speed": 1.0,
            "jitter_time": 0.2,
            "jitter_hold": 0.045,
            "loop": 15,
            "ignore_keys": ["a", "space", "ctrl"],
            "ignore_tolerance": 0.3
        },
        {
            "names": ["test.json"],
            "speed": 1.0,
            "jitter_time": 0.2,
            "jitter_hold": 0.045,
            "loop": 15,
            "ignore_keys": ["", "", ""],  # Empty keys
            "ignore_tolerance": 0.0
        },
        {
            "names": ["test.json"],
            "speed": 1.0,
            "jitter_time": 0.2,
            "jitter_hold": 0.045,
            "loop": 15
            # Missing ignore_keys and ignore_tolerance
        }
    ]
    
    for i, request in enumerate(sample_requests, 1):
        print(f"\nSample Request {i}:")
        print(f"  Raw data: {request}")
        
        # Extract ignore parameters like the API handlers would
        ignore_keys = request.get("ignore_keys", [])
        ignore_tolerance = float(request.get("ignore_tolerance", 0.0))
        
        print(f"  Extracted ignore_keys: {ignore_keys} (type: {type(ignore_keys)})")
        print(f"  Extracted ignore_tolerance: {ignore_tolerance} (type: {type(ignore_tolerance)})")
        
        # Validate the data
        issues = []
        if not isinstance(ignore_keys, list):
            issues.append(f"ignore_keys should be list, got {type(ignore_keys)}")
        if not isinstance(ignore_tolerance, (int, float)):
            issues.append(f"ignore_tolerance should be number, got {type(ignore_tolerance)}")
        
        if issues:
            print(f"  ❌ Issues: {issues}")
        else:
            print(f"  ✅ Data format looks correct")

def test_key_parsing():
    """Test 2: Test the key parsing logic in detail"""
    print(f"\n🔍 Test 2: Key Parsing Logic")
    print("=" * 50)
    
    def parse_ignore_keys(ignore_keys: Optional[List[str]]) -> set[int]:
        """Copy of the Player._parse_ignore_keys method"""
        if not ignore_keys:
            return set()
        
        ignore_usages = set()
        
        # Direct key name to HID usage mapping for common keys
        key_to_usage = {
            # Letters (HID usage 4-29)
            'A': 4, 'B': 5, 'C': 6, 'D': 7, 'E': 8, 'F': 9, 'G': 10, 'H': 11, 'I': 12, 'J': 13,
            'K': 14, 'L': 15, 'M': 16, 'N': 17, 'O': 18, 'P': 19, 'Q': 20, 'R': 21, 'S': 22,
            'T': 23, 'U': 24, 'V': 25, 'W': 26, 'X': 27, 'Y': 28, 'Z': 29,
            
            # Numbers (HID usage 30-39)
            '1': 30, '2': 31, '3': 32, '4': 33, '5': 34, '6': 35, '7': 36, '8': 37, '9': 38, '0': 39,
            
            # Special keys
            'ENTER': 40, 'RETURN': 40,
            'ESCAPE': 41, 'ESC': 41,
            'BACKSPACE': 42,
            'TAB': 43,
            'SPACE': 44,
            'MINUS': 45, '-': 45,
            'EQUAL': 46, '=': 46,
            
            # Function keys
            'F1': 58, 'F2': 59, 'F3': 60, 'F4': 61, 'F5': 62, 'F6': 63,
            'F7': 64, 'F8': 65, 'F9': 66, 'F10': 67, 'F11': 68, 'F12': 69,
            
            # Navigation
            'RIGHT': 79, 'LEFT': 80, 'DOWN': 81, 'UP': 82,
            'INSERT': 73, 'HOME': 74, 'PAGEUP': 75, 'DELETE': 76, 'END': 77, 'PAGEDOWN': 78,
            
            # Modifiers (HID usage 224-231)
            'CTRL': 224, 'LCTRL': 224, 'RCTRL': 228,
            'SHIFT': 225, 'LSHIFT': 225, 'RSHIFT': 229,
            'ALT': 226, 'LALT': 226, 'RALT': 230,
            'SUPER': 227, 'LSUPER': 227, 'RSUPER': 231, 'CMD': 227, 'WIN': 227,
        }
        
        print(f"    Input ignore_keys: {ignore_keys}")
        for key_name in ignore_keys:
            if not key_name or not key_name.strip():
                print(f"      '{key_name}' -> skipped (empty)")
                continue
                
            key_name_upper = key_name.strip().upper()
            print(f"      '{key_name}' -> normalized to '{key_name_upper}'")
            
            if key_name_upper in key_to_usage:
                usage = key_to_usage[key_name_upper]
                ignore_usages.add(usage)
                print(f"        -> mapped to HID usage {usage} ✅")
            else:
                print(f"        -> not found in mapping ❌")
        
        print(f"    Final ignore_usages: {ignore_usages}")
        return ignore_usages
    
    test_cases = [
        ["a", "space", "ctrl"],
        ["A", "SPACE", "CTRL"],
        ["", "space", ""],
        ["invalid", "space", "b"],
        [],
        None
    ]
    
    for test_keys in test_cases:
        print(f"\n  Test case: {test_keys}")
        try:
            result = parse_ignore_keys(test_keys)
            print(f"  Result: {result}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

def create_test_recording():
    """Create a realistic test recording file"""
    print(f"\n🔍 Creating Test Recording")
    print("=" * 50)
    
    # Create actions that would come from recording "a space b space ctrl"
    actions = [
        {"usage": 4, "press": 0.0, "dur": 0.1},      # 'a' key
        {"usage": 44, "press": 0.2, "dur": 0.05},    # space key
        {"usage": 5, "press": 0.4, "dur": 0.1},      # 'b' key  
        {"usage": 44, "press": 0.6, "dur": 0.05},    # space key again
        {"usage": 224, "press": 0.8, "dur": 0.1},    # left ctrl
    ]
    
    recording = {
        "t0": 0.0,
        "actions": actions
    }
    
    test_file = Path("/tmp/test_ignore_recording.json")
    test_file.write_text(json.dumps(recording, indent=2))
    
    print(f"  Created test recording: {test_file}")
    print(f"  Actions: {len(actions)} keystrokes")
    
    # Show what keys are in the recording
    key_names = []
    for action in actions:
        usage = action["usage"]
        if usage == 4: key_names.append("'a'")
        elif usage == 5: key_names.append("'b'") 
        elif usage == 44: key_names.append("'space'")
        elif usage == 224: key_names.append("'ctrl'")
        else: key_names.append(f"usage_{usage}")
    
    print(f"  Contains keys: {key_names}")
    return test_file, actions

def test_player_load_logic():
    """Test 3: Test how Player loads and processes recordings"""
    print(f"\n🔍 Test 3: Player Load Logic")
    print("=" * 50)
    
    def mock_load(path):
        """Mock Player._load method"""
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict):
            if "actions" in data:
                return {"mode": "actions", "actions": list(data["actions"] or [])}
        raise ValueError("Invalid recording format")
    
    def mock_events_to_actions(events):
        """Mock Player._events_to_actions method"""
        return []  # Not needed for this test
    
    test_file, original_actions = create_test_recording()
    
    try:
        # Test loading
        loaded = mock_load(test_file)
        print(f"  Loaded recording: {loaded['mode']} mode")
        print(f"  Actions count: {len(loaded.get('actions', []))}")
        
        # Test the conversion logic (copy from Player.play)
        if loaded["mode"] == "events":
            abs_actions = mock_events_to_actions(loaded["events"])
        else:
            abs_actions = loaded["actions"]
        
        print(f"  Absolute actions: {len(abs_actions)}")
        
        # Test speed scaling (copy from Player.play)
        speed = 1.0
        inv_speed = 1.0 / speed if speed and speed > 0 else 1.0
        
        scaled = [{
            "usage": int(a["usage"]),
            "press_at": max(0.0, float(a.get("press", 0.0)) * inv_speed),
            "dur": max(0.0, float(a.get("dur", 0.0)) * inv_speed),
        } for a in abs_actions]
        
        print(f"  Scaled actions: {len(scaled)}")
        
        # Show the scaled actions  
        for i, action in enumerate(scaled):
            usage = action["usage"]
            key_name = "unknown"
            if usage == 4: key_name = "a"
            elif usage == 5: key_name = "b"
            elif usage == 44: key_name = "space" 
            elif usage == 224: key_name = "ctrl"
            print(f"    {i+1}. usage={usage} ({key_name}), press_at={action['press_at']:.3f}")
        
        return scaled
        
    except Exception as e:
        print(f"  ERROR in player load logic: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        test_file.unlink()

def test_ignore_filtering():
    """Test 4: Test the actual ignore filtering logic"""
    print(f"\n🔍 Test 4: Ignore Filtering Logic")
    print("=" * 50)
    
    def parse_ignore_keys(ignore_keys):
        """Copy of key parsing logic"""
        if not ignore_keys:
            return set()
        
        key_to_usage = {
            'A': 4, 'B': 5, 'C': 6, 'SPACE': 44, 'CTRL': 224, 'SHIFT': 225, 'ALT': 226,
        }
        
        ignore_usages = set()
        for key_name in ignore_keys:
            if not key_name or not key_name.strip():
                continue
            key_name_upper = key_name.strip().upper()
            if key_name_upper in key_to_usage:
                ignore_usages.add(key_to_usage[key_name_upper])
        
        return ignore_usages
    
    def apply_ignore_filtering(scaled_actions, ignore_keys, ignore_tolerance):
        """Copy of ignore filtering logic from Player"""
        ignore_usages = parse_ignore_keys(ignore_keys)
        print(f"    ignore_keys: {ignore_keys}")
        print(f"    ignore_usages: {ignore_usages}")  
        print(f"    ignore_tolerance: {ignore_tolerance}")
        
        if ignore_usages and ignore_tolerance > 0:
            original_count = len(scaled_actions)
            filtered_scaled = []
            ignored_count = 0
            
            for a in scaled_actions:
                usage = a["usage"]
                # Apply ignore randomization if this key is in the ignore list
                if usage in ignore_usages and random.random() < ignore_tolerance:
                    # Skip this keystroke (ignore it)
                    ignored_count += 1
                    print(f"      IGNORING: usage {usage}")
                    continue
                filtered_scaled.append(a)
                print(f"      KEEPING: usage {usage}")
            
            print(f"    Result: ignored {ignored_count}/{original_count} actions")
            return filtered_scaled
        else:
            print(f"    No filtering applied (ignore_usages={ignore_usages}, tolerance={ignore_tolerance})")
            return scaled_actions
    
    # Test with sample actions
    test_actions = [
        {"usage": 4, "press_at": 0.0, "dur": 0.1},    # 'a'
        {"usage": 44, "press_at": 0.2, "dur": 0.05},  # space
        {"usage": 5, "press_at": 0.4, "dur": 0.1},    # 'b'
        {"usage": 44, "press_at": 0.6, "dur": 0.05},  # space
        {"usage": 224, "press_at": 0.8, "dur": 0.1},  # ctrl
    ]
    
    test_scenarios = [
        ([], 0.0, "No ignore keys"),
        (["a"], 0.0, "Ignore 'a' with 0% tolerance"),
        (["a"], 1.0, "Ignore 'a' with 100% tolerance"),
        (["space"], 1.0, "Ignore 'space' with 100% tolerance"),
        (["a", "space"], 1.0, "Ignore 'a' and 'space' with 100% tolerance"),
        (["invalid"], 1.0, "Ignore invalid key with 100% tolerance"),
    ]
    
    for ignore_keys, tolerance, description in test_scenarios:
        print(f"\n  Scenario: {description}")
        
        # Set fixed seed for reproducible results
        random.seed(42)
        
        filtered = apply_ignore_filtering(test_actions, ignore_keys, tolerance)
        
        remaining_usages = [a["usage"] for a in filtered]
        print(f"    Remaining usages: {remaining_usages}")
        
        # Show which keys remained
        remaining_keys = []
        for usage in remaining_usages:
            if usage == 4: remaining_keys.append("a")
            elif usage == 5: remaining_keys.append("b")
            elif usage == 44: remaining_keys.append("space")
            elif usage == 224: remaining_keys.append("ctrl")
        print(f"    Remaining keys: {remaining_keys}")

def test_complete_flow():
    """Test 5: Test the complete data flow"""
    print(f"\n🔍 Test 5: Complete Data Flow Test")
    print("=" * 50)
    
    # Simulate a complete request from frontend to player
    frontend_request = {
        "names": ["test.json"],
        "speed": 1.0,
        "jitter_time": 0.0,
        "jitter_hold": 0.0,
        "loop": 1,
        "ignore_keys": ["a", "space"],
        "ignore_tolerance": 1.0
    }
    
    print(f"  1. Frontend request: {frontend_request}")
    
    # Extract parameters (like handlers.py would)
    ignore_keys = frontend_request.get("ignore_keys", [])
    ignore_tolerance = float(frontend_request.get("ignore_tolerance", 0.0))
    
    print(f"  2. API extracted: ignore_keys={ignore_keys}, ignore_tolerance={ignore_tolerance}")
    
    # Create and load test recording
    test_file, _ = create_test_recording()
    
    try:
        # Load recording (like Player._load would)
        loaded = json.loads(test_file.read_text())
        actions = loaded["actions"]
        print(f"  3. Loaded {len(actions)} actions from recording")
        
        # Apply ignore filtering
        def apply_filtering(actions, ignore_keys, ignore_tolerance):
            # Key parsing
            key_to_usage = {'A': 4, 'B': 5, 'SPACE': 44, 'CTRL': 224}
            ignore_usages = set()
            for key in ignore_keys:
                if key and key.strip().upper() in key_to_usage:
                    ignore_usages.add(key_to_usage[key.strip().upper()])
            
            print(f"    Parsed ignore_usages: {ignore_usages}")
            
            # Filtering
            if ignore_usages and ignore_tolerance > 0:
                random.seed(42)  # Fixed for testing
                filtered = []
                ignored_count = 0
                
                for action in actions:
                    usage = action["usage"]
                    if usage in ignore_usages and random.random() < ignore_tolerance:
                        ignored_count += 1
                        continue
                    filtered.append(action)
                
                print(f"    Filtered: ignored {ignored_count}/{len(actions)} actions")
                return filtered
            else:
                print(f"    No filtering applied")
                return actions
        
        filtered_actions = apply_filtering(actions, ignore_keys, ignore_tolerance)
        
        print(f"  4. Final result: {len(filtered_actions)} actions remain")
        
        # Show what keys survived
        surviving_keys = []
        for action in filtered_actions:
            usage = action["usage"]
            if usage == 4: surviving_keys.append("a")
            elif usage == 5: surviving_keys.append("b")
            elif usage == 44: surviving_keys.append("space")
            elif usage == 224: surviving_keys.append("ctrl")
        
        print(f"  5. Surviving keys: {surviving_keys}")
        
        # Expected: should only have 'b' and 'ctrl' (a and space should be ignored)
        expected = ["b", "ctrl"]
        if surviving_keys == expected:
            print(f"  ✅ SUCCESS: Got expected result {expected}")
        else:
            print(f"  ❌ FAILURE: Expected {expected}, got {surviving_keys}")
            
    finally:
        test_file.unlink()

def identify_issues():
    """Analyze potential issues in the current implementation"""
    print(f"\n🔍 Potential Issues Analysis")
    print("=" * 50)
    
    issues = []
    
    # Check 1: Parameter passing
    print("  1. Checking parameter passing chain...")
    print("     Frontend → API → Daemon → Player")
    print("     - Frontend sends: ignore_keys, ignore_tolerance")
    print("     - API extracts and passes to daemon")
    print("     - Daemon passes to Player.play()")
    print("     - Player applies filtering")
    
    # Check 2: Default values
    print("\n  2. Checking default values...")
    print("     - ignore_keys defaults to [] (empty list)")
    print("     - ignore_tolerance defaults to 0.0")
    print("     - If either is falsy, no filtering occurs")
    
    # Check 3: Frontend state
    print("\n  3. Frontend state issues to check:")
    print("     - Are ignore_keys being saved in playSettings state?")
    print("     - Is ignore_tolerance being saved?")
    print("     - Are they being sent in API requests?")
    print("     - Check browser dev tools Network tab")
    
    # Check 4: Backend issues
    print("\n  4. Backend issues to check:")  
    print("     - Are parameters reaching the daemon?")
    print("     - Are they being passed to Player.play()?")
    print("     - Is the filtering logic being executed?")
    print("     - Check daemon logs for debug output")
    
    print("\n  💡 Debugging recommendations:")
    print("     1. Add console.log() in PlaySettingsModal to verify state")
    print("     2. Check browser Network tab for API request content")
    print("     3. Add logging in daemon.py to verify parameters")
    print("     4. The Player now has debug output - check daemon logs")

def main():
    """Run all comprehensive tests"""
    print("🚀 Comprehensive Keystroke Ignore Logic Test")
    print("=" * 60)
    
    try:
        test_frontend_data_format()
        test_key_parsing()  
        test_player_load_logic()
        test_ignore_filtering()
        test_complete_flow()
        identify_issues()
        
        print("\n" + "=" * 60)
        print("✅ Comprehensive test completed!")
        print("\n🔧 Next steps:")
        print("1. Check if frontend is actually sending ignore parameters in API requests")
        print("2. Verify daemon receives and passes parameters to Player")
        print("3. Look for debug output in daemon logs during playback")
        print("4. Test with a real recording that has the keys you want to ignore")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()