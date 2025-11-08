"""
Unit tests for msmacro.cv.object_detection module.

Tests cover:
- DetectorConfig initialization and defaults
- Color mask creation
- Blob filtering (size, circularity)
- Player detection (single yellow point)
- Other player detection (multiple red points)
- Temporal smoothing
- Performance benchmarking (<5ms target)
"""

import time
import unittest
import numpy as np
import cv2
from typing import Tuple

from msmacro.cv.object_detection import (
    DetectorConfig,
    MinimapObjectDetector,
    PlayerPosition,
    OtherPlayersStatus,
    DetectionResult
)


class TestDetectorConfig(unittest.TestCase):
    """Test DetectorConfig initialization and defaults."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DetectorConfig()
        
        # Player (yellow) defaults
        self.assertEqual(config.player_hsv_lower, (20, 100, 100))
        self.assertEqual(config.player_hsv_upper, (30, 255, 255))
        
        # Other players (red) defaults
        self.assertEqual(len(config.other_player_hsv_ranges), 2)
        self.assertEqual(config.other_player_hsv_ranges[0], ((0, 100, 100), (10, 255, 255)))
        self.assertEqual(config.other_player_hsv_ranges[1], ((170, 100, 100), (180, 255, 255)))
        
        # Blob filtering defaults
        self.assertEqual(config.min_blob_size, 3)
        self.assertEqual(config.max_blob_size, 15)
        self.assertEqual(config.min_circularity, 0.6)
        self.assertEqual(config.min_circularity_other, 0.5)
        
        # Temporal smoothing defaults
        self.assertTrue(config.temporal_smoothing)
        self.assertEqual(config.smoothing_alpha, 0.3)
    
    def test_custom_config(self):
        """Test custom configuration override."""
        config = DetectorConfig(
            player_hsv_lower=(15, 80, 80),
            player_hsv_upper=(35, 255, 255),
            min_blob_size=5,
            max_blob_size=20,
            min_circularity=0.7,
            temporal_smoothing=False
        )
        
        self.assertEqual(config.player_hsv_lower, (15, 80, 80))
        self.assertEqual(config.player_hsv_upper, (35, 255, 255))
        self.assertEqual(config.min_blob_size, 5)
        self.assertEqual(config.max_blob_size, 20)
        self.assertEqual(config.min_circularity, 0.7)
        self.assertFalse(config.temporal_smoothing)


class TestColorMask(unittest.TestCase):
    """Test color mask creation."""
    
    def setUp(self):
        """Create detector instance."""
        self.detector = MinimapObjectDetector()
    
    def test_mask_pure_yellow(self):
        """Test mask detects pure yellow circle."""
        # Create frame with yellow circle (morphological ops need larger regions)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.circle(frame, (50, 50), 5, (0, 255, 255), -1)  # BGR yellow circle
        
        mask = self.detector._create_color_mask(
            frame,
            (20, 100, 100),
            (30, 255, 255)
        )
        
        # Check that center region has detection
        center_region = mask[45:55, 45:55]
        self.assertGreater(np.sum(center_region), 0, "Pure yellow should be detected")
    
    def test_mask_pure_red(self):
        """Test mask detects pure red circle."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.circle(frame, (50, 50), 5, (0, 0, 255), -1)  # BGR red circle
        
        # Red wraps in HSV, test lower range
        mask = self.detector._create_color_mask(
            frame,
            (0, 100, 100),
            (10, 255, 255)
        )
        
        center_region = mask[45:55, 45:55]
        self.assertGreater(np.sum(center_region), 0, "Pure red should be detected")
    
    def test_mask_excludes_black(self):
        """Test mask excludes black pixels."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)  # All black
        
        mask = self.detector._create_color_mask(
            frame,
            (20, 100, 100),
            (30, 255, 255)
        )
        
        self.assertEqual(np.sum(mask), 0, "Black should not be detected as yellow")


class TestBlobFiltering(unittest.TestCase):
    """Test blob detection and filtering."""
    
    def setUp(self):
        """Create detector instance."""
        self.detector = MinimapObjectDetector()
    
    def _create_circle_mask(self, size: int, radius: int) -> np.ndarray:
        """Helper to create binary mask with circular blob."""
        mask = np.zeros((size, size), dtype=np.uint8)
        center = size // 2
        cv2.circle(mask, (center, center), radius, 255, -1)
        return mask
    
    def test_blob_size_filtering(self):
        """Test blob size (min/max) filtering."""
        # Too small blob (radius=1, diameter≈2)
        small_mask = self._create_circle_mask(100, 1)
        small_blobs = self.detector._find_circular_blobs(
            small_mask, min_size=3, max_size=15, min_circularity=0.5
        )
        self.assertEqual(len(small_blobs), 0, "Too small blob should be filtered")
        
        # Good size blob (radius=5, diameter=10)
        good_mask = self._create_circle_mask(100, 5)
        good_blobs = self.detector._find_circular_blobs(
            good_mask, min_size=3, max_size=15, min_circularity=0.5
        )
        self.assertEqual(len(good_blobs), 1, "Good size blob should be detected")
        
        # Too large blob (radius=10, diameter=20)
        large_mask = self._create_circle_mask(100, 10)
        large_blobs = self.detector._find_circular_blobs(
            large_mask, min_size=3, max_size=15, min_circularity=0.5
        )
        self.assertEqual(len(large_blobs), 0, "Too large blob should be filtered")
    
    def test_blob_circularity_filtering(self):
        """Test circularity filtering."""
        # Perfect circle (high circularity) - use larger radius to survive morphological ops
        circle_mask = self._create_circle_mask(100, 5)
        circle_blobs = self.detector._find_circular_blobs(
            circle_mask, min_size=3, max_size=20, min_circularity=0.7
        )
        self.assertEqual(len(circle_blobs), 1, "Circle should pass high circularity threshold")
        self.assertGreater(circle_blobs[0]['circularity'], 0.7)
        
        # Non-circular shape (rectangle - low circularity)
        rect_mask = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(rect_mask, (35, 45), (65, 55), 255, -1)  # 30x10 rectangle
        rect_blobs = self.detector._find_circular_blobs(
            rect_mask, min_size=3, max_size=50, min_circularity=0.8
        )
        self.assertEqual(len(rect_blobs), 0, "Rectangle should fail high circularity threshold")
    
    def test_blob_deduplication(self):
        """Test duplicate blob removal."""
        blobs = [
            {'center': (50, 50), 'circularity': 0.9},
            {'center': (52, 51), 'circularity': 0.85},  # Close to first (should be removed)
            {'center': (80, 80), 'circularity': 0.88},  # Far from others (should stay)
        ]
        
        unique = self.detector._deduplicate_blobs(blobs, distance_threshold=5.0)
        
        self.assertEqual(len(unique), 2, "Should remove duplicate at (52, 51)")
        # Best circularity should be kept
        self.assertEqual(unique[0]['center'], (50, 50))
        self.assertEqual(unique[1]['center'], (80, 80))


class TestPerformance(unittest.TestCase):
    """Test detection performance benchmarks."""
    
    def setUp(self):
        """Create detector and test frames."""
        self.detector = MinimapObjectDetector()
        
        # Create realistic test frame
        self.test_frame = np.zeros((86, 340, 3), dtype=np.uint8)
        # Add player
        cv2.circle(self.test_frame, (170, 43), 4, (0, 255, 255), -1)
        # Add other players
        cv2.circle(self.test_frame, (100, 30), 3, (0, 0, 255), -1)
        cv2.circle(self.test_frame, (200, 50), 3, (0, 0, 255), -1)
    
    def test_detection_speed(self):
        """Test that detection meets <5ms performance target."""
        # Warm up
        for _ in range(5):
            self.detector.detect(self.test_frame)
        
        # Benchmark
        iterations = 100
        start = time.perf_counter()
        
        for _ in range(iterations):
            result = self.detector.detect(self.test_frame)
        
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000.0
        
        # Get performance stats
        stats = self.detector.get_performance_stats()
        
        print(f"\nPerformance benchmark:")
        print(f"  Average: {stats['avg_ms']:.3f}ms")
        print(f"  Max: {stats['max_ms']:.3f}ms")
        print(f"  Min: {stats['min_ms']:.3f}ms")
        print(f"  Count: {stats['count']}")
        
        # Assert performance target
        self.assertLess(avg_ms, 5.0, f"Detection too slow: {avg_ms:.2f}ms (target <5ms)")
        self.assertLess(stats['max_ms'], 10.0, f"Max detection time too slow: {stats['max_ms']:.2f}ms")
    
    def test_performance_stats_tracking(self):
        """Test performance statistics tracking."""
        # Reset stats
        self.detector.reset_performance_stats()
        
        # Run detections
        for _ in range(10):
            self.detector.detect(self.test_frame)
        
        stats = self.detector.get_performance_stats()
        
        self.assertEqual(stats['count'], 10)
        self.assertGreater(stats['avg_ms'], 0)
        self.assertGreaterEqual(stats['max_ms'], stats['avg_ms'])
        self.assertLessEqual(stats['min_ms'], stats['avg_ms'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
