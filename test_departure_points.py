#!/usr/bin/env python3
"""
Test script for departure points functionality.
Tests the data model, tolerance modes, and basic operations.
"""

import sys
import time
from msmacro.cv.map_config import DeparturePoint, MapConfig

def test_departure_point_creation():
    """Test creating a departure point."""
    print("Test 1: Creating departure point...")
    point = DeparturePoint(
        id="test-id-123",
        name="Test Point",
        x=100,
        y=50,
        order=0,
        tolerance_mode="both",
        tolerance_value=5,
        created_at=time.time()
    )
    assert point.id == "test-id-123"
    assert point.name == "Test Point"
    assert point.x == 100
    assert point.y == 50
    print("✓ Departure point created successfully")

def test_tolerance_modes():
    """Test all 5 tolerance modes."""
    print("\nTest 2: Testing tolerance modes...")

    # Create a point at (100, 100)
    point = DeparturePoint(
        id="test",
        name="Test",
        x=100,
        y=100,
        order=0,
        tolerance_mode="both",
        tolerance_value=5,
        created_at=time.time()
    )

    # Test 1: "both" mode - both X and Y must be within tolerance
    point.tolerance_mode = "both"
    assert point.check_hit(102, 102) == True, "Should hit: within 5px in both directions"
    assert point.check_hit(106, 102) == False, "Should miss: X too far"
    assert point.check_hit(102, 106) == False, "Should miss: Y too far"
    print("✓ 'both' mode works correctly")

    # Test 2: "y_axis" mode - only Y matters
    point.tolerance_mode = "y_axis"
    assert point.check_hit(200, 102) == True, "Should hit: Y within 5px, X doesn't matter"
    assert point.check_hit(10, 98) == True, "Should hit: Y within 5px, X far away"
    assert point.check_hit(100, 106) == False, "Should miss: Y too far"
    print("✓ 'y_axis' mode works correctly")

    # Test 3: "x_axis" mode - only X matters
    point.tolerance_mode = "x_axis"
    assert point.check_hit(102, 200) == True, "Should hit: X within 5px, Y doesn't matter"
    assert point.check_hit(98, 10) == True, "Should hit: X within 5px, Y far away"
    assert point.check_hit(106, 100) == False, "Should miss: X too far"
    print("✓ 'x_axis' mode works correctly")

    # Test 4: "y_greater" mode - current Y must be > saved Y
    point.tolerance_mode = "y_greater"
    assert point.check_hit(100, 101) == True, "Should hit: Y > 100"
    assert point.check_hit(100, 150) == True, "Should hit: Y >> 100"
    assert point.check_hit(100, 100) == False, "Should miss: Y == 100"
    assert point.check_hit(100, 50) == False, "Should miss: Y < 100"
    print("✓ 'y_greater' mode works correctly")

    # Test 5: "y_less" mode - current Y must be < saved Y
    point.tolerance_mode = "y_less"
    assert point.check_hit(100, 99) == True, "Should hit: Y < 100"
    assert point.check_hit(100, 50) == True, "Should hit: Y << 100"
    assert point.check_hit(100, 100) == False, "Should miss: Y == 100"
    assert point.check_hit(100, 150) == False, "Should miss: Y > 100"
    print("✓ 'y_less' mode works correctly")

    # Test 6: "x_greater" mode - current X must be > saved X
    point.tolerance_mode = "x_greater"
    assert point.check_hit(101, 100) == True, "Should hit: X > 100"
    assert point.check_hit(150, 100) == True, "Should hit: X >> 100"
    assert point.check_hit(100, 100) == False, "Should miss: X == 100"
    assert point.check_hit(50, 100) == False, "Should miss: X < 100"
    print("✓ 'x_greater' mode works correctly")

    # Test 7: "x_less" mode - current X must be < saved X
    point.tolerance_mode = "x_less"
    assert point.check_hit(99, 100) == True, "Should hit: X < 100"
    assert point.check_hit(50, 100) == True, "Should hit: X << 100"
    assert point.check_hit(100, 100) == False, "Should miss: X == 100"
    assert point.check_hit(150, 100) == False, "Should miss: X > 100"
    print("✓ 'x_less' mode works correctly")

def test_map_config_integration():
    """Test MapConfig departure points integration."""
    print("\nTest 3: Testing MapConfig integration...")

    config = MapConfig(
        name="Test Map",
        tl_x=68,
        tl_y=56,
        width=340,
        height=86,
        created_at=time.time()
    )

    # Add departure points
    point1 = config.add_departure_point(100, 100, "Point 1", "both", 5)
    assert len(config.departure_points) == 1
    assert point1.order == 0
    print("✓ Added first departure point")

    point2 = config.add_departure_point(200, 150, "Point 2", "y_axis", 10)
    assert len(config.departure_points) == 2
    assert point2.order == 1
    print("✓ Added second departure point")

    # Test removal
    config.remove_departure_point(point1.id)
    assert len(config.departure_points) == 1
    assert config.departure_points[0].id == point2.id
    assert config.departure_points[0].order == 0  # Reordered
    print("✓ Removed point and reordered")

    # Test update
    config.update_departure_point(point2.id, name="Updated Point", tolerance_value=15)
    assert config.departure_points[0].name == "Updated Point"
    assert config.departure_points[0].tolerance_value == 15
    print("✓ Updated point properties")

    # Test check_all_departure_hits
    config.add_departure_point(150, 150, "Point 3", "both", 5)
    hits = config.check_all_departure_hits(152, 152)
    assert point2.id in hits
    assert config.departure_points[1].id in hits
    print("✓ check_all_departure_hits works")

def test_serialization():
    """Test to_dict and from_dict."""
    print("\nTest 4: Testing serialization...")

    config = MapConfig(
        name="Serialization Test",
        tl_x=68,
        tl_y=56,
        width=340,
        height=86,
        created_at=time.time()
    )

    config.add_departure_point(100, 100, "Point A", "both", 5)
    config.add_departure_point(200, 200, "Point B", "y_axis", 10)

    # Convert to dict
    config_dict = config.to_dict()
    assert "departure_points" in config_dict
    assert len(config_dict["departure_points"]) == 2
    print("✓ to_dict includes departure points")

    # Convert back from dict
    config_restored = MapConfig.from_dict(config_dict)
    assert len(config_restored.departure_points) == 2
    assert config_restored.departure_points[0].name == "Point A"
    assert config_restored.departure_points[1].tolerance_mode == "y_axis"
    print("✓ from_dict restores departure points correctly")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Departure Points Test Suite")
    print("=" * 60)

    try:
        test_departure_point_creation()
        test_tolerance_modes()
        test_map_config_integration()
        test_serialization()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
