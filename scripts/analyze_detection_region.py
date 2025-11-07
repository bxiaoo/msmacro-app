#!/usr/bin/env python3
"""
Analyze example frames to extract white frame detection coordinates.
"""

import cv2
import numpy as np
import sys

def find_red_rectangle(image_path):
    """Find red rectangle marker in the marked image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return None

    # Convert to HSV for better red detection
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Red color range in HSV (red wraps around at 0/180)
    # Lower red range (0-10)
    lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])

    # Upper red range (170-180)
    lower_red2 = np.array([170, 120, 120])
    upper_red2 = np.array([180, 255, 255])

    # Create masks for both red ranges
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    # Combine masks
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Find contours of red regions
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        print("No red rectangle found")
        return None

    # Find the largest contour (should be the red rectangle)
    largest_contour = max(contours, key=cv2.contourArea)

    # Get bounding rectangle
    x, y, w, h = cv2.boundingRect(largest_contour)

    print(f"Red rectangle found at: x={x}, y={y}, width={w}, height={h}")
    return (x, y, w, h)

def analyze_cropped_frame(image_path):
    """Analyze the cropped white frame to understand characteristics."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return None

    h, w = img.shape[:2]
    print(f"Cropped frame dimensions: {w}x{h}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Analyze brightness distribution
    avg_brightness = np.mean(gray)
    print(f"Average brightness: {avg_brightness:.1f}")

    # Find white pixels (threshold > 240)
    white_mask = gray > 240
    white_ratio = np.sum(white_mask) / (w * h)
    print(f"White pixel ratio: {white_ratio:.2%}")

    # Analyze edges to find the white frame border
    # Check top edge
    top_edge = gray[0:5, :]
    top_white = np.mean(top_edge > 240)
    print(f"Top edge white ratio: {top_white:.2%}")

    # Check left edge
    left_edge = gray[:, 0:5]
    left_white = np.mean(left_edge > 240)
    print(f"Left edge white ratio: {left_white:.2%}")

    return {
        'width': w,
        'height': h,
        'avg_brightness': avg_brightness,
        'white_ratio': white_ratio
    }

def analyze_original_background(image_path, x, y, w, h):
    """Analyze the background around the white frame in original image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return None

    # Convert to YUYV to analyze Y channel (luminance)
    # OpenCV doesn't directly support YUYV, but we can analyze grayscale as approximation
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Sample background regions around the white frame
    margin = 10

    # Left background (if available)
    if x > margin:
        left_bg = gray[y:y+h, x-margin:x]
        left_avg = np.mean(left_bg)
        print(f"Left background brightness: {left_avg:.1f}")

    # Top background (if available)
    if y > margin:
        top_bg = gray[y-margin:y, x:x+w]
        top_avg = np.mean(top_bg)
        print(f"Top background brightness: {top_avg:.1f}")

    # Bottom background
    if y + h + margin < gray.shape[0]:
        bottom_bg = gray[y+h:y+h+margin, x:x+w]
        bottom_avg = np.mean(bottom_bg)
        print(f"Bottom background brightness: {bottom_avg:.1f}")

    # Right background
    if x + w + margin < gray.shape[1]:
        right_bg = gray[y:y+h, x+w:x+w+margin]
        right_avg = np.mean(right_bg)
        print(f"Right background brightness: {right_avg:.1f}")

    # Analyze the white frame region itself
    frame_region = gray[y:y+h, x:x+w]
    frame_avg = np.mean(frame_region)
    frame_white_pixels = np.sum(frame_region > 240)
    frame_total_pixels = w * h
    frame_white_ratio = frame_white_pixels / frame_total_pixels

    print(f"\nWhite frame region:")
    print(f"  Average brightness: {frame_avg:.1f}")
    print(f"  White pixels: {frame_white_pixels}/{frame_total_pixels}")
    print(f"  White ratio: {frame_white_ratio:.2%}")

def main():
    print("=" * 60)
    print("Analyzing detection region from example images")
    print("=" * 60)

    # Paths to example images
    redmark_path = "/Users/boweixiao/Downloads/msmacro_cv_frame_redmark.jpg"
    original_path = "/Users/boweixiao/Downloads/msmacro_cv_frame_original.jpg"
    cropped_path = "/Users/boweixiao/Downloads/msmacro_cv_frame_cropped.jpg"
    filtered_path = "/Users/boweixiao/Downloads/msmacro_cv_frame_filtered.jpg"

    print("\n1. Finding red rectangle marker...")
    print("-" * 60)
    coords = find_red_rectangle(redmark_path)

    if coords:
        x, y, w, h = coords

        print("\n2. Analyzing cropped frame characteristics...")
        print("-" * 60)
        analyze_cropped_frame(cropped_path)

        print("\n3. Analyzing background around white frame...")
        print("-" * 60)
        analyze_original_background(original_path, x, y, w, h)

        print("\n" + "=" * 60)
        print("DETECTION PARAMETERS TO USE:")
        print("=" * 60)
        print(f"Fixed starting point: ({x}, {y})")
        print(f"Expected dimensions: ~{w}x{h} (variable)")
        print(f"White threshold: 240 (grayscale)")
        print(f"Min white ratio for border: >50%")
        print("=" * 60)
    else:
        print("\nFailed to extract coordinates from marked image")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
