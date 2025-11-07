"""
Region-based analysis utilities for CV frames.

Provides functions to analyze specific regions of captured frames for:
- Color detection (white/black/specific colors)
- Template matching in regions
- Text detection (OCR) in regions
- Shape detection in regions
"""

import numpy as np
import cv2
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Region:
    """
    Define a rectangular region of interest in a frame.

    Coordinates can be:
    - Absolute pixels: x=100, y=50, width=200, height=100
    - Relative (0.0-1.0): x=0.0, y=0.0, width=0.2, height=0.1 (top-left 20% x 10%)
    """
    x: float  # Left edge (pixels or relative 0.0-1.0)
    y: float  # Top edge (pixels or relative 0.0-1.0)
    width: float  # Width (pixels or relative 0.0-1.0)
    height: float  # Height (pixels or relative 0.0-1.0)
    relative: bool = False  # True if coordinates are relative (0.0-1.0)

    def to_absolute(self, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """
        Convert region to absolute pixel coordinates.

        Returns:
            Tuple of (x, y, width, height) in pixels
        """
        if self.relative:
            x = int(self.x * frame_width)
            y = int(self.y * frame_height)
            w = int(self.width * frame_width)
            h = int(self.height * frame_height)
        else:
            x = int(self.x)
            y = int(self.y)
            w = int(self.width)
            h = int(self.height)

        # Clamp to frame boundaries
        x = max(0, min(x, frame_width - 1))
        y = max(0, min(y, frame_height - 1))
        w = max(1, min(w, frame_width - x))
        h = max(1, min(h, frame_height - y))

        return (x, y, w, h)


def extract_region(frame: np.ndarray, region: Region) -> np.ndarray:
    """
    Extract a region from a frame.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        region: Region definition

    Returns:
        Cropped region as numpy array
    """
    height, width = frame.shape[:2]
    x, y, w, h = region.to_absolute(width, height)
    return frame[y:y+h, x:x+w]


def is_white_region(
    frame: np.ndarray,
    region: Region,
    threshold: int = 240,
    min_white_ratio: float = 0.95
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if a region is mostly white.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        region: Region to analyze
        threshold: Minimum pixel value to consider "white" (0-255, default: 240)
        min_white_ratio: Minimum ratio of white pixels required (0.0-1.0, default: 0.95)

    Returns:
        Tuple of (is_white: bool, stats: dict)

    Example:
        >>> # Check if top-left 200x100 region is white
        >>> region = Region(x=0, y=0, width=200, height=100)
        >>> is_white, stats = is_white_region(frame, region)
        >>> if is_white:
        >>>     print(f"White frame detected! {stats['white_ratio']:.1%} white pixels")
    """
    # Extract region
    roi = extract_region(frame, region)

    # Convert to grayscale if needed
    if len(roi.shape) == 3:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        gray = roi

    # Count white pixels
    white_pixels = np.sum(gray >= threshold)
    total_pixels = gray.size
    white_ratio = white_pixels / total_pixels if total_pixels > 0 else 0.0

    # Calculate average brightness
    avg_brightness = np.mean(gray)

    # Determine if region is white
    is_white = white_ratio >= min_white_ratio

    stats = {
        "white_ratio": white_ratio,
        "white_pixels": int(white_pixels),
        "total_pixels": int(total_pixels),
        "avg_brightness": float(avg_brightness),
        "threshold": threshold,
        "min_white_ratio": min_white_ratio,
        "is_white": is_white,
    }

    return is_white, stats


def is_black_region(
    frame: np.ndarray,
    region: Region,
    threshold: int = 15,
    min_black_ratio: float = 0.95
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if a region is mostly black.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        region: Region to analyze
        threshold: Maximum pixel value to consider "black" (0-255, default: 15)
        min_black_ratio: Minimum ratio of black pixels required (0.0-1.0, default: 0.95)

    Returns:
        Tuple of (is_black: bool, stats: dict)
    """
    roi = extract_region(frame, region)

    if len(roi.shape) == 3:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        gray = roi

    black_pixels = np.sum(gray <= threshold)
    total_pixels = gray.size
    black_ratio = black_pixels / total_pixels if total_pixels > 0 else 0.0
    avg_brightness = np.mean(gray)

    is_black = black_ratio >= min_black_ratio

    stats = {
        "black_ratio": black_ratio,
        "black_pixels": int(black_pixels),
        "total_pixels": int(total_pixels),
        "avg_brightness": float(avg_brightness),
        "threshold": threshold,
        "min_black_ratio": min_black_ratio,
        "is_black": is_black,
    }

    return is_black, stats


def detect_color_in_region(
    frame: np.ndarray,
    region: Region,
    color_bgr: Tuple[int, int, int],
    tolerance: int = 20,
    min_color_ratio: float = 0.8
) -> Tuple[bool, Dict[str, Any]]:
    """
    Detect a specific color in a region.

    Args:
        frame: Input frame (BGR numpy array)
        region: Region to analyze
        color_bgr: Target color in BGR format (B, G, R)
        tolerance: Color match tolerance (0-255, default: 20)
        min_color_ratio: Minimum ratio of matching pixels (0.0-1.0, default: 0.8)

    Returns:
        Tuple of (color_detected: bool, stats: dict)

    Example:
        >>> # Detect pure white (255, 255, 255) in top-left corner
        >>> region = Region(x=0, y=0, width=100, height=100)
        >>> detected, stats = detect_color_in_region(frame, region, (255, 255, 255))
    """
    roi = extract_region(frame, region)

    # Create color range
    lower = np.array([max(0, c - tolerance) for c in color_bgr])
    upper = np.array([min(255, c + tolerance) for c in color_bgr])

    # Create mask for matching pixels
    mask = cv2.inRange(roi, lower, upper)

    # Count matching pixels
    matching_pixels = np.sum(mask > 0)
    total_pixels = mask.size
    color_ratio = matching_pixels / total_pixels if total_pixels > 0 else 0.0

    color_detected = color_ratio >= min_color_ratio

    stats = {
        "color_ratio": color_ratio,
        "matching_pixels": int(matching_pixels),
        "total_pixels": int(total_pixels),
        "color_bgr": color_bgr,
        "tolerance": tolerance,
        "min_color_ratio": min_color_ratio,
        "color_detected": color_detected,
    }

    return color_detected, stats


def get_region_average_color(frame: np.ndarray, region: Region) -> Tuple[int, int, int]:
    """
    Get the average color of a region.

    Args:
        frame: Input frame (BGR numpy array)
        region: Region to analyze

    Returns:
        Tuple of (B, G, R) average color values
    """
    roi = extract_region(frame, region)
    avg_color = cv2.mean(roi)[:3]  # Get BGR, ignore alpha
    return tuple(int(c) for c in avg_color)


def visualize_region(
    frame: np.ndarray,
    region: Region,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    label: Optional[str] = None
) -> np.ndarray:
    """
    Draw a region rectangle on a frame for visualization.

    Args:
        frame: Input frame (will be copied, not modified)
        region: Region to draw
        color: Rectangle color in BGR (default: green)
        thickness: Line thickness (default: 2)
        label: Optional text label to draw above region

    Returns:
        Copy of frame with region visualized
    """
    result = frame.copy()
    height, width = frame.shape[:2]
    x, y, w, h = region.to_absolute(width, height)

    # Draw rectangle
    cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)

    # Draw label if provided
    if label:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 1
        text_size = cv2.getTextSize(label, font, font_scale, font_thickness)[0]

        # Draw background for text
        text_bg_y = max(5, y - 5)
        cv2.rectangle(
            result,
            (x, text_bg_y - text_size[1] - 4),
            (x + text_size[0] + 4, text_bg_y + 2),
            color,
            -1  # Filled
        )

        # Draw text
        cv2.putText(
            result,
            label,
            (x + 2, text_bg_y),
            font,
            font_scale,
            (255, 255, 255),  # White text
            font_thickness
        )

    return result


def detect_white_frame_bounds(
    frame: np.ndarray,
    scan_region: Optional[Region] = None,
    threshold: int = 240,
    min_white_pixels: int = 100
) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect white frame boundaries in a scan region.

    This function finds the bounding box of white pixels that form a frame/border.
    Useful for detecting UI elements with white borders.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        scan_region: Region to scan (default: top-left 300x200 pixels)
        threshold: Minimum pixel value to consider "white" (0-255, default: 240)
        min_white_pixels: Minimum white pixels required for detection (default: 100)

    Returns:
        Tuple of (x, y, width, height) in absolute pixels, or None if not detected

    Example:
        >>> bounds = detect_white_frame_bounds(frame)
        >>> if bounds:
        >>>     x, y, w, h = bounds
        >>>     cropped = frame[y:y+h, x:x+w]
    """
    # Default scan region: top-left 300x200 pixels
    if scan_region is None:
        scan_region = Region(x=0, y=0, width=300, height=200)

    # Extract scan region
    roi = extract_region(frame, scan_region)
    frame_height, frame_width = frame.shape[:2]
    scan_x, scan_y, scan_w, scan_h = scan_region.to_absolute(frame_width, frame_height)

    # Convert to grayscale if needed
    if len(roi.shape) == 3:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        gray = roi

    # Create binary mask of white pixels
    _, white_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # Count white pixels
    white_pixel_count = np.sum(white_mask > 0)
    if white_pixel_count < min_white_pixels:
        return None

    # Find contours of white regions
    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Find the largest contour (likely the white frame)
    largest_contour = max(contours, key=cv2.contourArea)

    # Get bounding rectangle
    x, y, w, h = cv2.boundingRect(largest_contour)

    # Convert to absolute frame coordinates
    abs_x = scan_x + x
    abs_y = scan_y + y

    # Ensure bounds are within frame
    abs_x = max(0, min(abs_x, frame_width - 1))
    abs_y = max(0, min(abs_y, frame_height - 1))
    w = max(1, min(w, frame_width - abs_x))
    h = max(1, min(h, frame_height - abs_y))

    return (abs_x, abs_y, w, h)


def detect_top_left_white_frame(
    frame: np.ndarray,
    max_region_width: int = 800,
    max_region_height: int = 600,
    threshold: int = 240,
    min_white_ratio: float = 0.85,
    edge_margin: int = 20
) -> Optional[Dict[str, Any]]:
    """
    Detect white frame content in the top-left area of the frame.

    Optimized for detecting content with white borders/backgrounds that appear
    in the top-left corner of screenshots. Returns both the detected region and
    analysis metadata.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        max_region_width: Maximum width to search (default: 800)
        max_region_height: Maximum height to search (default: 600)
        threshold: Minimum pixel value to consider "white" (0-255, default: 240)
        min_white_ratio: Minimum ratio of white pixels (0.0-1.0, default: 0.85)
        edge_margin: Margin from edges to exclude (pixels, default: 20)

    Returns:
        Dict with keys:
            - 'detected' (bool): Whether white frame was detected
            - 'x', 'y', 'width', 'height' (int): Detected region coordinates
            - 'white_ratio' (float): Ratio of white pixels in region
            - 'avg_brightness' (float): Average brightness
            - 'confidence' (float): Detection confidence (0.0-1.0)
        Or None if detection fails

    Example:
        >>> result = detect_top_left_white_frame(frame)
        >>> if result and result['detected']:
        >>>     x, y, w, h = result['x'], result['y'], result['width'], result['height']
        >>>     cropped = frame[y:y+h, x:x+w]
    """
    frame_height, frame_width = frame.shape[:2]

    # Limit search region
    search_width = min(max_region_width, frame_width - edge_margin)
    search_height = min(max_region_height, frame_height - edge_margin)

    # Convert to grayscale
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # Extract top-left region for analysis
    top_left = gray[edge_margin:edge_margin + search_height, edge_margin:edge_margin + search_width]

    # Create binary mask of white pixels
    _, white_mask = cv2.threshold(top_left, threshold, 255, cv2.THRESH_BINARY)

    # Find white pixel regions
    white_pixels = np.sum(white_mask > 0)
    total_pixels = white_mask.size
    white_ratio = white_pixels / total_pixels if total_pixels > 0 else 0.0

    # Find contours to locate white regions
    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    result = {
        "detected": False,
        "white_ratio": white_ratio,
        "avg_brightness": float(np.mean(top_left)),
        "white_pixels": int(white_pixels),
        "total_pixels": int(total_pixels),
        "threshold": threshold,
        "confidence": 0.0,
    }

    if not contours or white_ratio < min_white_ratio:
        return result

    # Find largest contour (main white region)
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)

    # Convert back to absolute frame coordinates (accounting for edge_margin)
    abs_x = edge_margin + x
    abs_y = edge_margin + y

    # Clamp to frame boundaries
    abs_x = max(0, min(abs_x, frame_width - 1))
    abs_y = max(0, min(abs_y, frame_height - 1))
    w = max(1, min(w, frame_width - abs_x))
    h = max(1, min(h, frame_height - abs_y))

    # Analyze the detected region for quality
    region_roi = gray[abs_y:abs_y + h, abs_x:abs_x + w]
    _, region_mask = cv2.threshold(region_roi, threshold, 255, cv2.THRESH_BINARY)
    region_white_ratio = np.sum(region_mask > 0) / region_mask.size

    # Confidence: how "white" is the detected region
    confidence = min(1.0, region_white_ratio)

    result.update({
        "detected": region_white_ratio >= min_white_ratio,
        "x": int(abs_x),
        "y": int(abs_y),
        "width": int(w),
        "height": int(h),
        "region_white_ratio": float(region_white_ratio),
        "confidence": float(confidence),
    })

    return result


def detect_and_crop_white_frame(
    frame: np.ndarray,
    scan_region: Optional[Region] = None,
    threshold: int = 240,
    min_white_pixels: int = 100
) -> Optional[np.ndarray]:
    """
    Detect and crop to white frame region in one operation.

    Args:
        frame: Input frame (BGR or grayscale numpy array)
        scan_region: Region to scan (default: top-left 300x200 pixels)
        threshold: Minimum pixel value to consider "white" (0-255, default: 240)
        min_white_pixels: Minimum white pixels required for detection (default: 100)

    Returns:
        Cropped frame containing the white frame region, or None if not detected

    Example:
        >>> cropped = detect_and_crop_white_frame(frame)
        >>> if cropped is not None:
        >>>     cv2.imwrite("white_frame.jpg", cropped)
    """
    bounds = detect_white_frame_bounds(frame, scan_region, threshold, min_white_pixels)

    if bounds is None:
        return None

    x, y, w, h = bounds
    return frame[y:y+h, x:x+w]


# Common region presets for 1280x720 and 1920x1080 screens
REGIONS = {
    # Top-left corner (200x100 pixels)
    "top_left_corner": Region(x=0, y=0, width=200, height=100),

    # Top-left corner (relative: 15% width, 10% height)
    "top_left_relative": Region(x=0.0, y=0.0, width=0.15, height=0.1, relative=True),

    # Top-right corner
    "top_right_corner": Region(x=1.0, y=0.0, width=0.15, height=0.1, relative=True),

    # Bottom-left corner
    "bottom_left_corner": Region(x=0.0, y=0.9, width=0.15, height=0.1, relative=True),

    # Bottom-right corner
    "bottom_right_corner": Region(x=0.85, y=0.9, width=0.15, height=0.1, relative=True),

    # Center region
    "center": Region(x=0.4, y=0.4, width=0.2, height=0.2, relative=True),

    # Top bar (full width, 50 pixels high)
    "top_bar": Region(x=0.0, y=0.0, width=1.0, height=50, relative=False),

    # Bottom bar (full width, 50 pixels high)
    "bottom_bar": Region(x=0.0, y=1.0, width=1.0, height=50, relative=False),
}
