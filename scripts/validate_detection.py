#!/usr/bin/env python3
"""
Detection Validation Script

Validates detector performance against ground truth annotations.
Compares current detector vs optimized detector and calculates precision/recall metrics.

Usage:
    python scripts/validate_detection.py
    python scripts/validate_detection.py --samples-dir /path/to/samples
    python scripts/validate_detection.py --use-optimized  # Test optimized config
    python scripts/validate_detection.py --show-failures  # Show failed detections
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig
from msmacro.cv.detection_config import load_config


@dataclass
class ValidationResult:
    """Results for a single sample validation."""
    sample_name: str
    has_ground_truth: bool

    # Ground truth
    gt_player_count: int = 0
    gt_player_positions: List[Tuple[int, int]] = field(default_factory=list)

    # Detection results
    detected_player: bool = False
    detected_player_pos: Tuple[int, int] = None

    # Metrics
    true_positive: bool = False
    false_positive: bool = False
    false_negative: bool = False
    position_error: float = None  # Euclidean distance if detected

    def __str__(self):
        if not self.has_ground_truth:
            return f"{self.sample_name}: No ground truth (player off-screen)"

        status = "✅ TP" if self.true_positive else \
                 "❌ FP" if self.false_positive else \
                 "❌ FN" if self.false_negative else "?"

        if self.position_error is not None:
            return f"{self.sample_name}: {status} (error: {self.position_error:.1f}px)"
        else:
            return f"{self.sample_name}: {status}"


def load_annotation(annotation_path: Path) -> Dict[str, Any]:
    """Load annotation JSON file."""
    with open(annotation_path, 'r') as f:
        return json.load(f)


def load_image(image_path: Path) -> np.ndarray:
    """Load image file."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")
    return img


def calculate_position_error(detected: Tuple[int, int], ground_truth: Tuple[int, int]) -> float:
    """Calculate Euclidean distance between detected and ground truth positions."""
    dx = detected[0] - ground_truth[0]
    dy = detected[1] - ground_truth[1]
    return np.sqrt(dx*dx + dy*dy)


def validate_sample(
    image_path: Path,
    annotation_path: Path,
    detector: MinimapObjectDetector,
    tolerance: float = 5.0
) -> ValidationResult:
    """
    Validate detector on a single sample.

    Args:
        image_path: Path to minimap image
        annotation_path: Path to annotation JSON
        detector: Detector instance to test
        tolerance: Position tolerance in pixels (default: 5px)

    Returns:
        ValidationResult
    """
    result = ValidationResult(sample_name=image_path.stem, has_ground_truth=True)

    # Load annotation
    annotation = load_annotation(annotation_path)
    annotations = annotation.get('annotations', [])

    # Extract ground truth player positions
    for ann in annotations:
        if ann.get('type') == 'player':
            result.gt_player_count += 1
            result.gt_player_positions.append((ann['x'], ann['y']))

    # Load image and run detection
    image = load_image(image_path)
    detection_result = detector.detect(image)

    # Check detection result
    result.detected_player = detection_result.player.detected

    if result.detected_player:
        result.detected_player_pos = (
            detection_result.player.x,
            detection_result.player.y
        )

    # Calculate metrics
    if result.gt_player_count == 0:
        # No ground truth player
        if result.detected_player:
            result.false_positive = True  # Detected player when none exists
        # else: True negative (correct)
    elif result.gt_player_count == 1:
        # Exactly one ground truth player
        gt_pos = result.gt_player_positions[0]

        if result.detected_player:
            # Calculate position error
            result.position_error = calculate_position_error(
                result.detected_player_pos, gt_pos
            )

            if result.position_error <= tolerance:
                result.true_positive = True  # Correct detection
            else:
                # Detected wrong position (too far from ground truth)
                result.false_positive = True
                result.false_negative = True  # Missed the actual player
        else:
            result.false_negative = True  # Failed to detect player
    else:
        # Multiple ground truth players (shouldn't happen in your data)
        # Find closest match
        if result.detected_player:
            min_error = float('inf')
            for gt_pos in result.gt_player_positions:
                error = calculate_position_error(result.detected_player_pos, gt_pos)
                if error < min_error:
                    min_error = error

            result.position_error = min_error
            if min_error <= tolerance:
                result.true_positive = True
            else:
                result.false_positive = True

        # Check for missed players
        # (Simplified: just check if we detected anything)
        if not result.detected_player:
            result.false_negative = True

    return result


def validate_all_samples(
    samples_dir: Path,
    detector: MinimapObjectDetector,
    tolerance: float = 5.0,
    show_failures: bool = False
) -> Tuple[List[ValidationResult], Dict[str, Any]]:
    """
    Validate detector on all samples with annotations.

    Returns:
        (results, metrics)
    """
    # Find all annotation files
    annotation_files = list(samples_dir.glob("*.annotations.json"))

    if not annotation_files:
        raise ValueError(f"No annotation files found in {samples_dir}")

    print(f"\n{'='*70}")
    print(f"VALIDATING DETECTOR ON {len(annotation_files)} ANNOTATED SAMPLES")
    print('='*70)

    results = []

    for ann_path in sorted(annotation_files):
        # Find corresponding image
        # ann_path is like "sample_20251120_225058.annotations.json"
        # image is like "sample_20251120_225058.png"
        base_name = str(ann_path).replace('.annotations.json', '')
        image_path = Path(base_name + '.png')
        if not image_path.exists():
            image_path = Path(base_name + '.jpg')
        if not image_path.exists():
            print(f"⚠️  Warning: No image found for {ann_path.name}")
            continue

        # Validate
        result = validate_sample(image_path, ann_path, detector, tolerance)
        results.append(result)

        # Show result
        status_icon = "✅" if result.true_positive else \
                     "❌" if (result.false_positive or result.false_negative) else "⚪"

        print(f"{status_icon} {result}")

        # Show failure details if requested
        if show_failures and (result.false_positive or result.false_negative):
            print(f"   GT: {result.gt_player_positions}")
            print(f"   Detected: {result.detected_player_pos}")
            if result.position_error:
                print(f"   Position error: {result.position_error:.1f}px")

    # Calculate aggregate metrics
    tp = sum(1 for r in results if r.true_positive)
    fp = sum(1 for r in results if r.false_positive)
    fn = sum(1 for r in results if r.false_negative)
    tn = len(results) - tp - fp - fn  # Samples with no player, correctly not detected

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Position accuracy (only for true positives)
    position_errors = [r.position_error for r in results if r.position_error is not None]
    avg_position_error = np.mean(position_errors) if position_errors else 0.0
    max_position_error = np.max(position_errors) if position_errors else 0.0

    metrics = {
        'total_samples': len(results),
        'true_positives': tp,
        'false_positives': fp,
        'false_negatives': fn,
        'true_negatives': tn,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'avg_position_error': avg_position_error,
        'max_position_error': max_position_error
    }

    return results, metrics


def print_metrics_report(metrics: Dict[str, Any], config_name: str = "Current"):
    """Print formatted metrics report."""
    print(f"\n{'='*70}")
    print(f"{config_name.upper()} DETECTOR PERFORMANCE METRICS")
    print('='*70)

    print(f"\n📊 Classification Metrics:")
    print(f"  True Positives:  {metrics['true_positives']:>3} (correctly detected player)")
    print(f"  False Positives: {metrics['false_positives']:>3} (detected when shouldn't)")
    print(f"  False Negatives: {metrics['false_negatives']:>3} (missed player)")
    print(f"  True Negatives:  {metrics['true_negatives']:>3} (correctly no detection)")

    print(f"\n📈 Performance Scores:")
    print(f"  Precision: {metrics['precision']:.1%} (of detections, how many correct?)")
    print(f"  Recall:    {metrics['recall']:.1%} (of ground truth, how many found?)")
    print(f"  F1 Score:  {metrics['f1_score']:.1%} (harmonic mean of P&R)")

    if metrics['true_positives'] > 0:
        print(f"\n📍 Position Accuracy (True Positives only):")
        print(f"  Average error: {metrics['avg_position_error']:.1f} pixels")
        print(f"  Maximum error: {metrics['max_position_error']:.1f} pixels")

    # Overall assessment
    print(f"\n🎯 Overall Assessment:")
    if metrics['precision'] == 1.0 and metrics['recall'] == 1.0:
        print("  ✅ PERFECT: 100% precision and 100% recall")
    elif metrics['precision'] >= 0.95 and metrics['recall'] >= 0.95:
        print("  ✅ EXCELLENT: ≥95% precision and recall")
    elif metrics['precision'] >= 0.90 and metrics['recall'] >= 0.90:
        print("  ✅ GOOD: ≥90% precision and recall")
    elif metrics['recall'] < 0.90:
        print(f"  ⚠️  WARNING: Low recall ({metrics['recall']:.1%}) - missing player dots")
    elif metrics['precision'] < 0.90:
        print(f"  ⚠️  WARNING: Low precision ({metrics['precision']:.1%}) - false detections")


def main():
    parser = argparse.ArgumentParser(description='Validate detector against ground truth')
    parser.add_argument(
        '--samples-dir',
        type=Path,
        default=Path.home() / '.local/share/msmacro/calibration/minimap_samples',
        help='Directory containing samples and annotations'
    )
    parser.add_argument(
        '--use-optimized',
        action='store_true',
        help='Test optimized config instead of current'
    )
    parser.add_argument(
        '--tolerance',
        type=float,
        default=5.0,
        help='Position tolerance in pixels (default: 5.0)'
    )
    parser.add_argument(
        '--show-failures',
        action='store_true',
        help='Show detailed information for failed detections'
    )
    args = parser.parse_args()

    if not args.samples_dir.exists():
        print(f"❌ Samples directory not found: {args.samples_dir}")
        return 1

    # Create detector
    if args.use_optimized:
        print("\n📋 Using OPTIMIZED detector configuration (Option C - balanced ranges)")
        config = DetectorConfig(
            player_hsv_lower=(20, 180, 180),
            player_hsv_upper=(40, 255, 255),
            temporal_smoothing=False  # Disable for validation (samples are independent)
        )
        config_name = "Optimized"
    else:
        print("\n📋 Using CURRENT detector configuration")
        try:
            config = load_config()
        except:
            # Fall back to default
            config = DetectorConfig()
        config_name = "Current"
        # Override temporal smoothing for validation
        config.temporal_smoothing = False

    detector = MinimapObjectDetector(config)

    print(f"\n🎨 HSV Ranges:")
    print(f"  Hue:        {config.player_hsv_lower[0]}-{config.player_hsv_upper[0]}")
    print(f"  Saturation: {config.player_hsv_lower[1]}-{config.player_hsv_upper[1]}")
    print(f"  Value:      {config.player_hsv_lower[2]}-{config.player_hsv_upper[2]}")

    # Validate
    try:
        results, metrics = validate_all_samples(
            args.samples_dir,
            detector,
            args.tolerance,
            args.show_failures
        )
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Print metrics
    print_metrics_report(metrics, config_name)

    print(f"\n{'='*70}")

    # Recommendations
    if metrics['recall'] < 1.0:
        print("\n⚠️  RECOMMENDATIONS FOR LOW RECALL:")
        print("  - Check failed samples for lighting/quality issues")
        print("  - Consider widening HSV ranges slightly")
        print("  - Verify annotations are accurate")

    if metrics['precision'] < 1.0:
        print("\n⚠️  RECOMMENDATIONS FOR LOW PRECISION:")
        print("  - Tighten HSV ranges to reduce false positives")
        print("  - Increase circularity threshold")
        print("  - Review false positive samples")

    if metrics['precision'] == 1.0 and metrics['recall'] == 1.0:
        print("\n✅ PERFECT DETECTION - READY FOR PRODUCTION!")

    return 0


if __name__ == '__main__':
    sys.exit(main())
