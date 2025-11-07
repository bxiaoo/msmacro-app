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


# ============================================================================
# YUYV Format Processing Functions
# ============================================================================
# YUYV (also called YUY2) is a packed YUV format where:
# - 4 bytes represent 2 pixels: [Y0 U Y1 V]
# - Y = luminance (brightness) - 0-255
# - U, V = chrominance (color) - shared between 2 pixels
#
# For white frame detection, we only need the Y channel which directly
# represents brightness, allowing faster processing than full BGR conversion.
# ============================================================================

def bgr_to_yuyv_bytes(bgr_frame: np.ndarray) -> bytes:
    """
    Convert BGR frame to simulated YUYV byte format.

    Since OpenCV's VideoCapture.read() converts YUYV to BGR automatically,
    this function converts it back to YUYV format for processing with
    YUYV-based detection functions.

    Args:
        bgr_frame: BGR frame from OpenCV (HxWx3 numpy array)

    Returns:
        Simulated YUYV bytes (packed format: Y0 U Y1 V)

    Note:
        This is a simulation - real YUYV from camera would be slightly different
        due to chroma subsampling, but Y channel values are equivalent.
    """
    # Convert BGR to YCrCb (OpenCV's YUV equivalent)
    ycrcb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2YCrCb)

    h, w = ycrcb.shape[:2]

    # Extract Y, Cr, Cb channels
    y = ycrcb[:, :, 0]  # Y (luminance)
    cr = ycrcb[:, :, 1]  # Cr (red-difference)
    cb = ycrcb[:, :, 2]  # Cb (blue-difference)

    # YUYV packing: Y0 U Y1 V (4 bytes for 2 pixels, U and V shared)
    # U = Cb, V = Cr in YUV terminology
    yuyv_bytes = bytearray(h * w * 2)

    for row in range(h):
        for col in range(0, w, 2):  # Process 2 pixels at a time
            # Get Y values for both pixels
            y0 = y[row, col]
            y1 = y[row, col + 1] if col + 1 < w else y0

            # Get shared U (Cb) and V (Cr) values
            # Average Cb and Cr from both pixels
            u = cb[row, col] if col < w else 128
            v = cr[row, col] if col < w else 128

            # Pack into YUYV format: Y0 U Y1 V
            byte_offset = (row * w * 2) + (col * 2)
            yuyv_bytes[byte_offset + 0] = y0
            yuyv_bytes[byte_offset + 1] = u
            yuyv_bytes[byte_offset + 2] = y1
            yuyv_bytes[byte_offset + 3] = v

    return bytes(yuyv_bytes)


def extract_y_channel_from_yuyv(
    yuyv_data: bytes,
    width: int,
    height: int,
    x: int,
    y: int,
    region_width: int,
    region_height: int
) -> Optional[np.ndarray]:
    """
    Extract Y (luminance) channel from a region of YUYV raw data.

    YUYV packing format: Y0 U Y1 V (4 bytes for 2 pixels)
    Y values are at byte positions: 0, 2, 4, 6, 8, ...

    Args:
        yuyv_data: Raw YUYV bytes from camera
        width: Full frame width in pixels
        height: Full frame height in pixels
        x: Region start X coordinate
        y: Region start Y coordinate
        region_width: Region width in pixels
        region_height: Region height in pixels

    Returns:
        2D numpy array of Y values (uint8), or None on error

    Example:
        >>> # Extract 100x50 region starting at (10, 20)
        >>> y_data = extract_y_channel_from_yuyv(raw_bytes, 1280, 720, 10, 20, 100, 50)
        >>> white_pixels = np.sum(y_data > 240)
    """
    # Validate inputs
    if not yuyv_data:
        return None

    # YUYV uses 2 bytes per pixel (actually 4 bytes per 2 pixels)
    bytes_per_pixel = 2
    expected_size = width * height * bytes_per_pixel

    if len(yuyv_data) < expected_size:
        return None

    # Clamp region to frame boundaries
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    region_width = max(1, min(region_width, width - x))
    region_height = max(1, min(region_height, height - y))

    # Create output array
    y_channel = np.zeros((region_height, region_width), dtype=np.uint8)

    # Extract Y values row by row
    for row in range(region_height):
        frame_row = y + row
        for col in range(region_width):
            frame_col = x + col

            # Calculate byte position in YUYV data
            # Each row has (width * 2) bytes
            # Each pixel's Y value is at even byte positions: 0, 2, 4, ...
            byte_offset = (frame_row * width * 2) + (frame_col * 2)

            if byte_offset < len(yuyv_data):
                y_channel[row, col] = yuyv_data[byte_offset]

    return y_channel


def find_white_border_edges_yuyv(
    y_channel: np.ndarray,
    start_x: int,
    start_y: int,
    max_width: int = 500,
    max_height: int = 150,
    white_threshold: int = 240,
    border_thickness: int = 3
) -> Optional[Tuple[int, int, int, int]]:
    """
    Find white frame edges by scanning from a fixed starting point.

    Scans rightward and downward from the starting point to find white border
    edges, then returns the bounding box of the white-bordered region.

    Args:
        y_channel: Y (luminance) channel data (2D numpy array)
        start_x: Fixed X starting point in the Y channel
        start_y: Fixed Y starting point in the Y channel
        max_width: Maximum width to scan (default: 500)
        max_height: Maximum height to scan (default: 150)
        white_threshold: Minimum Y value for "white" pixels (default: 240)
        border_thickness: Expected border thickness in pixels (default: 3)

    Returns:
        Tuple of (x, y, width, height) relative to Y channel, or None if not found

    Algorithm:
        1. Verify top-left corner has white border
        2. Scan rightward to find right border edge
        3. Scan downward to find bottom border edge
        4. Validate borders are continuous and white
        5. Return bounding box including borders
    """
    h, w = y_channel.shape

    # Validate starting point is within bounds
    if start_x >= w or start_y >= h:
        return None

    # Check if starting point has white border (top-left corner)
    corner_region = y_channel[start_y:start_y+border_thickness,
                               start_x:start_x+border_thickness]
    if corner_region.size == 0:
        return None

    corner_white_ratio = np.sum(corner_region >= white_threshold) / corner_region.size
    if corner_white_ratio < 0.7:  # At least 70% of corner should be white
        return None

    # Scan rightward to find right edge
    # Look for continuous white border in top row
    right_edge = start_x + max_width
    for x in range(start_x + 10, min(start_x + max_width, w)):
        # Check top border at this x position
        top_border = y_channel[start_y:start_y+border_thickness, x:x+border_thickness]
        if top_border.size > 0:
            white_ratio = np.sum(top_border >= white_threshold) / top_border.size
            # If top border becomes non-white, we found the right edge
            if white_ratio < 0.5:
                right_edge = x
                break
    else:
        right_edge = min(start_x + max_width, w)

    frame_width = right_edge - start_x

    # Scan downward to find bottom edge
    # Look for continuous white border in left column
    bottom_edge = start_y + max_height
    for y in range(start_y + 10, min(start_y + max_height, h)):
        # Check left border at this y position
        left_border = y_channel[y:y+border_thickness, start_x:start_x+border_thickness]
        if left_border.size > 0:
            white_ratio = np.sum(left_border >= white_threshold) / left_border.size
            # If left border becomes non-white, we found the bottom edge
            if white_ratio < 0.5:
                bottom_edge = y
                break
    else:
        bottom_edge = min(start_y + max_height, h)

    frame_height = bottom_edge - start_y

    # Validate minimum size
    if frame_width < 50 or frame_height < 20:
        return None

    return (start_x, start_y, frame_width, frame_height)


def validate_dark_background_yuyv(
    y_channel: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    dark_min: int = 60,
    dark_max: int = 130,
    sample_margin: int = 10
) -> bool:
    """
    Validate that the region is on a dark gray background.

    Samples pixels around the detected white frame to ensure the surrounding
    area has dark gray coloring (typical of MapleStory UI backgrounds).

    Args:
        y_channel: Y (luminance) channel data (2D numpy array)
        x: Frame X coordinate
        y: Frame Y coordinate
        width: Frame width
        height: Frame height
        dark_min: Minimum Y value for "dark gray" (default: 60)
        dark_max: Maximum Y value for "dark gray" (default: 130)
        sample_margin: Margin around frame to sample (default: 10 pixels)

    Returns:
        True if background is dark gray, False otherwise
    """
    h, w = y_channel.shape

    # Sample left background
    if x > sample_margin:
        left_bg = y_channel[y:y+height, x-sample_margin:x]
        if left_bg.size > 0:
            left_avg = np.mean(left_bg)
            if not (dark_min <= left_avg <= dark_max):
                return False

    # Sample top background
    if y > sample_margin:
        top_bg = y_channel[y-sample_margin:y, x:x+width]
        if top_bg.size > 0:
            top_avg = np.mean(top_bg)
            if not (dark_min <= top_avg <= dark_max):
                return False

    return True


def detect_white_frame_yuyv(
    yuyv_data: bytes,
    frame_width: int,
    frame_height: int,
    fixed_start_x: int = 68,
    fixed_start_y: int = 56,
    max_frame_width: int = 500,
    max_frame_height: int = 150,
    white_threshold: int = 240
) -> Optional[Dict[str, Any]]:
    """
    Advanced white frame detection using raw YUYV data.

    Optimized for detecting MapleStory party/quest UI frame with white border
    on dark gray background. Uses fixed starting point and variable size detection.

    This function processes YUYV data directly (before BGR conversion) for
    better performance and color accuracy.

    Args:
        yuyv_data: Raw YUYV bytes from capture device
        frame_width: Frame width in pixels (e.g., 1280)
        frame_height: Frame height in pixels (e.g., 720)
        fixed_start_x: Fixed X coordinate where frame always starts (default: 68)
        fixed_start_y: Fixed Y coordinate where frame always starts (default: 56)
        max_frame_width: Maximum frame width to search (default: 500)
        max_frame_height: Maximum frame height to search (default: 150)
        white_threshold: Minimum Y value for white pixels (default: 240)

    Returns:
        Dict with detection result:
            {
                "detected": bool,
                "x": int, "y": int,
                "width": int, "height": int,
                "confidence": float,
                "white_border_quality": float,
                "dark_background": bool,
                "method": "yuyv"
            }
        Or None on critical error

    Example:
        >>> result = detect_white_frame_yuyv(yuyv_bytes, 1280, 720)
        >>> if result and result["detected"]:
        >>>     print(f"Frame at ({result['x']}, {result['y']}) "
        >>>           f"size {result['width']}x{result['height']} "
        >>>           f"confidence {result['confidence']:.2%}")
    """
    # Extract large region around the expected frame location
    # This includes the frame plus surrounding area for background validation
    search_margin = 30
    search_x = max(0, fixed_start_x - search_margin)
    search_y = max(0, fixed_start_y - search_margin)
    search_width = min(max_frame_width + search_margin * 2, frame_width - search_x)
    search_height = min(max_frame_height + search_margin * 2, frame_height - search_y)

    # Extract Y channel for the search region
    y_channel = extract_y_channel_from_yuyv(
        yuyv_data,
        frame_width,
        frame_height,
        search_x,
        search_y,
        search_width,
        search_height
    )

    if y_channel is None:
        return None

    # Convert fixed start point to coordinates within the extracted Y channel
    local_start_x = fixed_start_x - search_x
    local_start_y = fixed_start_y - search_y

    # Find white border edges starting from the fixed point
    edges = find_white_border_edges_yuyv(
        y_channel,
        local_start_x,
        local_start_y,
        max_frame_width,
        max_frame_height,
        white_threshold
    )

    # Default result
    result = {
        "detected": False,
        "x": fixed_start_x,
        "y": fixed_start_y,
        "width": 0,
        "height": 0,
        "confidence": 0.0,
        "white_border_quality": 0.0,
        "dark_background": False,
        "method": "yuyv"
    }

    if edges is None:
        return result

    local_x, local_y, det_width, det_height = edges

    # Convert back to absolute frame coordinates
    abs_x = search_x + local_x
    abs_y = search_y + local_y

    # Validate dark background around the frame
    dark_bg = validate_dark_background_yuyv(
        y_channel,
        local_x,
        local_y,
        det_width,
        det_height
    )

    # Analyze border quality
    # Sample the border pixels (top, left, right, bottom edges)
    border_pixels = []

    # Top border
    top_border = y_channel[local_y:local_y+3, local_x:local_x+det_width]
    if top_border.size > 0:
        border_pixels.append(top_border.flatten())

    # Left border
    left_border = y_channel[local_y:local_y+det_height, local_x:local_x+3]
    if left_border.size > 0:
        border_pixels.append(left_border.flatten())

    # Right border (if within bounds)
    if local_x + det_width < y_channel.shape[1]:
        right_border = y_channel[local_y:local_y+det_height, local_x+det_width-3:local_x+det_width]
        if right_border.size > 0:
            border_pixels.append(right_border.flatten())

    # Bottom border (if within bounds)
    if local_y + det_height < y_channel.shape[0]:
        bottom_border = y_channel[local_y+det_height-3:local_y+det_height, local_x:local_x+det_width]
        if bottom_border.size > 0:
            border_pixels.append(bottom_border.flatten())

    # Calculate border quality
    white_border_quality = 0.0
    if border_pixels:
        all_border = np.concatenate(border_pixels)
        white_border_quality = np.sum(all_border >= white_threshold) / len(all_border)

    # Calculate confidence score
    # High confidence requires:
    # 1. Good white border quality (>70%)
    # 2. Dark background validation
    # 3. Reasonable size
    confidence = 0.0
    if white_border_quality > 0.7 and det_width > 100 and det_height > 30:
        confidence = white_border_quality
        if dark_bg:
            confidence = min(1.0, confidence * 1.2)  # Boost confidence if background is correct

    # Detection successful if confidence > 0.7
    detected = confidence > 0.7

    result.update({
        "detected": detected,
        "x": int(abs_x),
        "y": int(abs_y),
        "width": int(det_width),
        "height": int(det_height),
        "confidence": float(confidence),
        "white_border_quality": float(white_border_quality),
        "dark_background": dark_bg
    })

    return result


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
