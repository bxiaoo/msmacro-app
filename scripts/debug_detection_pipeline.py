#!/usr/bin/env python3
"""
Debug Detection Pipeline

Shows what happens at each stage of the detection pipeline to understand
why the optimized config isn't detecting anything.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from msmacro.cv.object_detection import MinimapObjectDetector, DetectorConfig

# Load sample image
sample_path = Path.home() / '.local/share/msmacro/calibration/minimap_samples/sample_20251120_225058.png'
img = cv2.imread(str(sample_path))

if img is None:
    print(f"Failed to load: {sample_path}")
    sys.exit(1)

print(f"Image loaded: {img.shape}")

# Create optimized detector
config = DetectorConfig(
    player_hsv_lower=(28, 250, 250),
    player_hsv_upper=(32, 255, 255),
    min_blob_size=4,
    max_blob_size=16,
    min_circularity=0.71,
    enable_contrast_validation=False,
    temporal_smoothing=False  # Disable for debugging
)

# Manually run each stage
print("\n" + "="*70)
print("DETECTION PIPELINE DEBUG")
print("="*70)

# Stage 1: HSV conversion
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
print(f"\n1. HSV Conversion:")
print(f"   Shape: {hsv.shape}")

# Stage 2: HSV filtering
lower = np.array(config.player_hsv_lower)
upper = np.array(config.player_hsv_upper)
mask = cv2.inRange(hsv, lower, upper)
print(f"\n2. HSV Filtering (H={config.player_hsv_lower[0]}-{config.player_hsv_upper[0]}, S≥{config.player_hsv_lower[1]}, V≥{config.player_hsv_lower[2]}):")
print(f"   Pixels in mask: {np.count_nonzero(mask)}")

# Stage 3: Morphological operations
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
mask_morph = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
mask_morph = cv2.morphologyEx(mask_morph, cv2.MORPH_OPEN, kernel)
print(f"\n3. Morphological Operations (3x3 ELLIPSE, CLOSE then OPEN):")
print(f"   Pixels after morphology: {np.count_nonzero(mask_morph)}")

# Stage 4: Find contours
contours, _ = cv2.findContours(mask_morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"\n4. Contour Detection:")
print(f"   Total contours found: {len(contours)}")

# Stage 5: Size filtering
size_filtered = []
for i, contour in enumerate(contours):
    area = cv2.contourArea(contour)
    if config.min_blob_size <= area <= config.max_blob_size:
        size_filtered.append(contour)
        print(f"   Contour {i}: area={area:.1f} ✅ PASS size filter")
    else:
        print(f"   Contour {i}: area={area:.1f} ❌ FAIL size filter (need {config.min_blob_size}-{config.max_blob_size})")

print(f"\n   Contours after size filter: {len(size_filtered)}")

# Stage 6: Shape filtering
final_blobs = []
for i, contour in enumerate(size_filtered):
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)

    if perimeter == 0:
        print(f"   Size-filtered contour {i}: perimeter=0 ❌ SKIP")
        continue

    circularity = 4 * np.pi * area / (perimeter * perimeter)

    # Bounding box for aspect ratio
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = float(w) / h if h > 0 else 0

    print(f"   Size-filtered contour {i}:")
    print(f"     Area: {area:.1f}")
    print(f"     Circularity: {circularity:.3f} (need ≥{config.min_circularity})")
    print(f"     Aspect ratio: {aspect_ratio:.3f} (need {config.min_aspect_ratio}-{config.max_aspect_ratio})")

    if circularity >= config.min_circularity:
        if config.min_aspect_ratio <= aspect_ratio <= config.max_aspect_ratio:
            final_blobs.append((contour, x + w//2, y + h//2))
            print(f"     ✅ PASS shape filter")
        else:
            print(f"     ❌ FAIL aspect ratio")
    else:
        print(f"     ❌ FAIL circularity")

print(f"\n6. Final Detection:")
print(f"   Blobs passing all filters: {len(final_blobs)}")

if final_blobs:
    for i, (contour, cx, cy) in enumerate(final_blobs):
        print(f"   Blob {i}: position=({cx}, {cy})")
        print(f"   Expected: (178, 49)")
        error = np.sqrt((cx - 178)**2 + (cy - 49)**2)
        print(f"   Position error: {error:.1f} pixels")
else:
    print("   ❌ NO BLOBS DETECTED")

print("\n" + "="*70)
