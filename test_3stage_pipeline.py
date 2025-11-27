#!/usr/bin/env python3
"""Test the new 3-stage geometric center detection pipeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import cv2
from msmacro.cv.object_detection import MinimapObjectDetector

def test_pipeline():
    """Test 3-stage pipeline on calibration samples."""

    samples_dir = Path("/Users/boweixiao/Downloads/calibration_samples_20251126_232003")
    output_dir = Path("/tmp/3stage_final")
    output_dir.mkdir(exist_ok=True)

    print("="*80)
    print("3-STAGE GEOMETRIC CENTER DETECTION TEST")
    print("="*80)
    print("\nPipeline:")
    print("  Stage 1: Tight color detection (S≥200, V≥200) → Bright cores")
    print("  Stage 2: Morphological expansion (7x7 dilate x2) → Full markers")
    print("  Stage 3: Geometric fitting (fitEllipse) → True centers")
    print("="*80 + "\n")

    for filename in sorted(samples_dir.glob("*.png")):
        print(f"{filename.name}:")

        # Load image
        frame = cv2.imread(str(filename))
        if frame is None:
            print("  ERROR: Could not read")
            continue

        # Create fresh detector with new 3-stage pipeline
        detector = MinimapObjectDetector()

        # Detect
        result = detector.detect(frame)

        if result.player.detected:
            x, y = result.player.x, result.player.y
            conf = result.player.confidence

            print(f"  ✅ Detected at ({x}, {y})")
            print(f"     Confidence: {conf:.3f}")

            # Create visualization
            vis = detector.visualize(frame, result)

            # Add pipeline info
            cv2.putText(vis, "3-Stage Pipeline: Tight→Expand→FitEllipse", (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Save
            output_path = output_dir / f"3stage_{filename.name}"
            cv2.imwrite(str(output_path), vis)
            print(f"     Saved: {output_path}")
        else:
            print(f"  ❌ NOT DETECTED")

        print()

    print(f"Visualizations saved to: {output_dir}/")
    print("\n" + "="*80)
    print("Review visualizations - yellow markers should be at geometric centers!")
    print("="*80)

if __name__ == "__main__":
    test_pipeline()
