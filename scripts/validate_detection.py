#!/usr/bin/env python3
"""
Validate object detection accuracy against ground truth annotations.

This script runs the object detector on the test dataset and compares
results with ground truth annotations to calculate precision, recall,
and position error metrics.

Usage:
    python scripts/validate_detection.py --dataset data/yuyv_test_set/

    # Use custom config
    python scripts/validate_detection.py --dataset data/yuyv_test_set/ --config calibrated_config.json

    # Save detailed results
    python scripts/validate_detection.py --dataset data/yuyv_test_set/ --output validation_results.json

Requirements:
    - Dataset must be annotated (ground_truth.json must exist)
    - At least 10 frames should be annotated for meaningful statistics
"""

import argparse
import sys
from pathlib import Path
import json
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig


# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_ground_truth(dataset_dir: Path):
    """Load ground truth annotations."""
    gt_path = dataset_dir / "ground_truth.json"

    if not gt_path.exists():
        raise FileNotFoundError(
            f"Ground truth not found: {gt_path}\n"
            f"Run annotation tool first: python scripts/annotate_ground_truth.py --dataset {dataset_dir}"
        )

    with open(gt_path) as f:
        ground_truth = json.load(f)

    if not ground_truth:
        raise ValueError("Ground truth file is empty")

    print(f"✓ Loaded {len(ground_truth)} ground truth annotations")
    return ground_truth


def validate_detection(dataset_dir: Path, config_file: Path = None, output_file: Path = None):
    """
    Run detection on test dataset and calculate metrics.

    Args:
        dataset_dir: Path to dataset directory
        config_file: Optional custom config JSON file
        output_file: Optional path to save detailed results

    Returns:
        Dictionary with validation metrics
    """
    print("\n" + "="*70)
    print("OBJECT DETECTION VALIDATION")
    print("="*70)
    print(f"Dataset: {dataset_dir}\n")

    # Load ground truth
    ground_truth = load_ground_truth(dataset_dir)

    # Load detector config
    if config_file and config_file.exists():
        print(f"✓ Loading custom config: {config_file}")
        with open(config_file) as f:
            config_data = json.load(f)
        # TODO: Convert JSON config to DetectorConfig
        detector = MinimapObjectDetector()
    else:
        print("Using default detector configuration")
        detector = MinimapObjectDetector()

    # Initialize metrics
    metrics = {
        "player_tp": 0,  # True positives
        "player_fp": 0,  # False positives
        "player_fn": 0,  # False negatives
        "player_tn": 0,  # True negatives
        "position_errors": [],
        "other_tp": 0,
        "other_fp": 0,
        "other_fn": 0,
        "other_tn": 0,
        "frame_results": []
    }

    total_frames = len(ground_truth)
    print(f"\nProcessing {total_frames} frames...")
    print("-" * 70)

    # Process each annotated frame
    for i, (filename, gt) in enumerate(ground_truth.items()):
        frame_path = dataset_dir / filename

        if not frame_path.exists():
            print(f"⚠️  Frame not found: {filename}")
            continue

        # Load frame
        frame = np.load(str(frame_path))

        # Run detection
        result = detector.detect(frame)

        # Player detection evaluation
        gt_player = gt.get("player")
        has_gt_player = gt_player is not None

        if has_gt_player and result.player.detected:
            # True Positive
            metrics["player_tp"] += 1
            gt_x, gt_y = gt_player
            error = np.sqrt((result.player.x - gt_x)**2 + (result.player.y - gt_y)**2)
            metrics["position_errors"].append(error)
            status = f"{Colors.GREEN}✓ TP{Colors.END}"
        elif has_gt_player and not result.player.detected:
            # False Negative
            metrics["player_fn"] += 1
            status = f"{Colors.RED}✗ FN{Colors.END}"
        elif not has_gt_player and result.player.detected:
            # False Positive
            metrics["player_fp"] += 1
            status = f"{Colors.YELLOW}! FP{Colors.END}"
        else:
            # True Negative
            metrics["player_tn"] += 1
            status = f"{Colors.GREEN}✓ TN{Colors.END}"

        # Other players evaluation
        has_gt_others = len(gt.get("other_players", [])) > 0

        if has_gt_others and result.other_players.detected:
            metrics["other_tp"] += 1
        elif has_gt_others and not result.other_players.detected:
            metrics["other_fn"] += 1
        elif not has_gt_others and result.other_players.detected:
            metrics["other_fp"] += 1
        else:
            metrics["other_tn"] += 1

        # Store frame result
        frame_result = {
            "filename": filename,
            "player_gt": gt_player,
            "player_detected": result.player.detected,
            "player_pos": (result.player.x, result.player.y) if result.player.detected else None,
            "player_confidence": result.player.confidence if result.player.detected else 0.0,
            "other_gt_count": len(gt.get("other_players", [])),
            "other_detected_count": result.other_players.count,
            "position_error": metrics["position_errors"][-1] if has_gt_player and result.player.detected else None
        }
        metrics["frame_results"].append(frame_result)

        # Progress output
        if (i + 1) % 10 == 0 or (i + 1) == total_frames:
            print(f"[{i+1:3d}/{total_frames}] {filename:40s} {status}")

    print("-" * 70)

    # Calculate statistics
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)

    # Player detection metrics
    player_total_positive = metrics["player_tp"] + metrics["player_fp"]
    player_total_gt_positive = metrics["player_tp"] + metrics["player_fn"]

    player_precision = metrics["player_tp"] / player_total_positive if player_total_positive > 0 else 0.0
    player_recall = metrics["player_tp"] / player_total_gt_positive if player_total_gt_positive > 0 else 0.0
    avg_position_error = np.mean(metrics["position_errors"]) if metrics["position_errors"] else 0.0

    # Other players metrics
    other_total_positive = metrics["other_tp"] + metrics["other_fp"]
    other_total_gt_positive = metrics["other_tp"] + metrics["other_fn"]

    other_precision = metrics["other_tp"] / other_total_positive if other_total_positive > 0 else 0.0
    other_recall = metrics["other_tp"] / other_total_gt_positive if other_total_gt_positive > 0 else 0.0

    # Display results
    print(f"\n{Colors.BOLD}Player Detection:{Colors.END}")
    print(f"  Precision: {player_precision:.2%} ({metrics['player_tp']}/{player_total_positive})")
    print(f"  Recall:    {player_recall:.2%} ({metrics['player_tp']}/{player_total_gt_positive})")
    print(f"  Position Error (avg): {avg_position_error:.2f} pixels")
    if metrics["position_errors"]:
        print(f"  Position Error (max): {np.max(metrics['position_errors']):.2f} pixels")
        print(f"  Position Error (std): {np.std(metrics['position_errors']):.2f} pixels")

    print(f"\n{Colors.BOLD}Other Players Detection:{Colors.END}")
    print(f"  Precision: {other_precision:.2%} ({metrics['other_tp']}/{other_total_positive})")
    print(f"  Recall:    {other_recall:.2%} ({metrics['other_tp']}/{other_total_gt_positive})")

    # Performance stats
    perf_stats = detector.get_performance_stats()
    print(f"\n{Colors.BOLD}Performance:{Colors.END}")
    print(f"  Average:  {perf_stats['avg_ms']:.2f} ms")
    print(f"  Max:      {perf_stats['max_ms']:.2f} ms")
    print(f"  Min:      {perf_stats['min_ms']:.2f} ms")
    print(f"  Frames:   {perf_stats['count']}")

    # Gate check
    print("\n" + "="*70)
    print("GATE CHECK (Production Deployment Requirements)")
    print("="*70)

    gate_checks = []

    # Player precision >90%
    player_precision_pass = player_precision >= 0.90
    gate_checks.append(("Player Precision ≥90%", player_precision >= 0.90, f"{player_precision:.1%}"))

    # Player recall >85%
    player_recall_pass = player_recall >= 0.85
    gate_checks.append(("Player Recall ≥85%", player_recall >= 0.85, f"{player_recall:.1%}"))

    # Position error <5px
    position_error_pass = avg_position_error < 5.0
    gate_checks.append(("Avg Position Error <5px", avg_position_error < 5.0, f"{avg_position_error:.2f}px"))

    # Other players precision >85%
    other_precision_pass = other_precision >= 0.85
    gate_checks.append(("Other Players Precision ≥85%", other_precision >= 0.85, f"{other_precision:.1%}"))

    # Other players recall >80%
    other_recall_pass = other_recall >= 0.80
    gate_checks.append(("Other Players Recall ≥80%", other_recall >= 0.80, f"{other_recall:.1%}"))

    # Performance <15ms on Pi 4 (relaxed check if not on Pi)
    perf_pass = perf_stats['avg_ms'] < 15.0
    gate_checks.append(("Performance <15ms", perf_pass, f"{perf_stats['avg_ms']:.2f}ms"))

    for check_name, passed, value in gate_checks:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {status}  {check_name:30s} = {value}")

    all_passed = all(check[1] for check in gate_checks)

    print("\n" + "="*70)
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ VALIDATION PASSED - Ready for production deployment{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ VALIDATION FAILED - Recalibrate HSV ranges{Colors.END}")
    print("="*70 + "\n")

    # Save detailed results if requested
    if output_file:
        output_data = {
            "metrics": {
                "player_precision": player_precision,
                "player_recall": player_recall,
                "avg_position_error": float(avg_position_error),
                "other_precision": other_precision,
                "other_recall": other_recall,
                "performance_avg_ms": perf_stats['avg_ms'],
                "gate_passed": all_passed
            },
            "gate_checks": [
                {"name": name, "passed": passed, "value": value}
                for name, passed, value in gate_checks
            ],
            "frame_results": metrics["frame_results"]
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Detailed results saved to: {output_file}\n")

    return {
        "player_precision": player_precision,
        "player_recall": player_recall,
        "avg_position_error": float(avg_position_error),
        "other_precision": other_precision,
        "other_recall": other_recall,
        "gate_passed": all_passed
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate object detection accuracy against ground truth",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to dataset directory with ground_truth.json"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional custom detector config JSON file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save detailed validation results"
    )

    args = parser.parse_args()

    if not args.dataset.is_dir():
        print(f"ERROR: Dataset directory not found: {args.dataset}")
        return 1

    if args.config and not args.config.exists():
        print(f"ERROR: Config file not found: {args.config}")
        return 1

    try:
        result = validate_detection(args.dataset, args.config, args.output)
        return 0 if result["gate_passed"] else 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
