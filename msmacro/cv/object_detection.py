"""
Minimap object detection for player and other_player positions.

Detects colored points (yellow=player, red=other_player) on minimap
and returns position information for automated navigation.

IMPORTANT: HSV color ranges are PLACEHOLDERS for JPEG development.
These values MUST be calibrated on test Pi with real YUYV frames
before production deployment.
"""

import time
import logging
from dataclasses import dataclass, asdict
from typing import Tuple, List, Optional, Dict, Any
import numpy as np
import cv2


logger = logging.getLogger(__name__)


@dataclass
class PlayerPosition:
    """Player position on minimap."""
    detected: bool
    x: int = 0  # X coordinate relative to minimap top-left
    y: int = 0  # Y coordinate relative to minimap top-left
    confidence: float = 0.0  # Circularity score (0-1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OtherPlayersStatus:
    """Other players detection status."""
    detected: bool  # True if any other players present
    count: int = 0  # Number of other players detected
    positions: List[Tuple[int, int]] = None  # [(x, y), ...] positions for visualization

    def __post_init__(self):
        if self.positions is None:
            self.positions = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'detected': self.detected,
            'count': self.count,
            'positions': [{'x': x, 'y': y} for x, y in self.positions]
        }


@dataclass
class DetectionResult:
    """Complete detection result."""
    player: PlayerPosition
    other_players: OtherPlayersStatus
    timestamp: float  # Unix timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "player": self.player.to_dict(),
            "other_players": self.other_players.to_dict(),
            "timestamp": self.timestamp
        }


@dataclass
class DetectorConfig:
    """Object detector configuration."""
    # Player detection (yellow-green point) - OPTIMIZED CALIBRATED VALUES (Option C)
    # Based on annotation analysis and validation with 22 samples (Nov 21, 2025)
    # Validation: 100% precision, 100% recall, 2.5px avg error
    # Option C balances tight color filtering (2.25× tighter S/V) with morphology survival
    player_hsv_lower: Tuple[int, int, int] = (20, 180, 180)   # H=20-40, S≥180, V≥180
    player_hsv_upper: Tuple[int, int, int] = (40, 255, 255)   # Tight hue, high S/V for fewer false positives

    # Other players detection (red points) - CALIBRATED VALUES
    # Red wraps around in HSV, need two ranges
    # Based on analysis of 20 calibration samples (Nov 9, 2025)
    other_player_hsv_ranges: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None

    # Blob filtering - FINAL CALIBRATED VALUES
    # Based on iterative testing with visual verification (Nov 9, 2025)
    # Final algorithm uses strict filtering for high precision:
    # - Yellow blobs: 4-16px diameter, circularity ≥0.71
    # - Red blobs: 4-80px diameter, circularity ≥0.65
    # Combined with HSV filter and adaptive scoring for robust detection
    min_blob_size: int = 4      # Minimum player dot size (4px diameter)
    max_blob_size: int = 16     # Maximum player dot size (16px diameter)
    min_blob_size_other: int = 4   # Red dots minimum (>= 4px diameter)
    max_blob_size_other: int = 80  # Red dots upper bound
    min_circularity: float = 0.71  # Strict circularity for round player dots
    min_circularity_other: float = 0.65  # Tightened to reduce small red false positives

    # Aspect ratio filtering (NEW)
    # Player dots should be roughly circular (width ≈ height)
    min_aspect_ratio: float = 0.5   # Reject if width/height < 0.5 (too tall)
    max_aspect_ratio: float = 2.0   # Reject if width/height > 2.0 (too wide)

    # Contrast validation (NEW) - DISABLED by default
    # HSV + size + circularity + aspect filtering already provides excellent precision
    # Contrast validation can cause false negatives in low-contrast scenes
    enable_contrast_validation: bool = False
    min_contrast_ratio: float = 1.15  # Blob must be 15% brighter (if enabled)

    # Temporal smoothing
    temporal_smoothing: bool = True
    smoothing_alpha: float = 0.3  # EMA alpha (0-1, higher = less smoothing)

    def __post_init__(self):
        """Initialize default values."""
        if self.other_player_hsv_ranges is None:
            # Calibrated red ranges (Nov 9, 2025 - Ground truth validation)
            # Tightened based on actual red dots: H=7 (S=114,V=123) and H=168 (S=191,V=168)
            # Filters out cyan/green/blue false positives (H=60-140)
            self.other_player_hsv_ranges = [
                ((0, 100, 100), (10, 255, 255)),     # Lower red range (pure red only)
                ((165, 100, 100), (179, 255, 255))   # Upper red range (H max is 179 in OpenCV)
            ]


class MinimapObjectDetector:
    """Detects player and other_player objects on minimap."""
    
    def __init__(self, config: Optional[DetectorConfig] = None):
        """
        Initialize detector with color ranges and filter parameters.
        
        Args:
            config: Optional detector configuration
        """
        self.config = config or DetectorConfig()

        # Temporal smoothing state
        self._last_player_pos: Optional[Tuple[int, int]] = None
        self._detection_count = 0

        # Performance tracking
        self._total_time_ms = 0.0
        self._max_time_ms = 0.0
        self._min_time_ms = float('inf')

    def _calculate_adaptive_blob_sizes(self, frame: np.ndarray, blob_type: str = 'player') -> Tuple[int, int]:
        """
        Return blob size range based on calibrated values.

        SIZE FILTERING ENABLED: Returns calibrated ranges based on analysis
        of 20 calibration samples:
        - Player (yellow): median 10.5px, filter to 4-100px diameter
        - Other players (red): median 16px, filter to 4-80px diameter

        Combined with HSV, circularity, aspect ratio, and contrast filters
        for robust multi-stage detection pipeline.

        Args:
            frame: Minimap crop (for logging dimensions only)
            blob_type: 'player' or 'other' to select appropriate size range

        Returns:
            (min_diameter, max_diameter) - Calibrated size range in pixels
        """
        height, width = frame.shape[:2]

        # Return calibrated size range
        if blob_type == 'other':
            adaptive_min = self.config.min_blob_size_other  # = 4px (red dots are larger)
            adaptive_max = self.config.max_blob_size_other  # = 80px
        else:
            adaptive_min = self.config.min_blob_size  # = 2px (includes small yellow dots)
            adaptive_max = self.config.max_blob_size  # = 100px

        return adaptive_min, adaptive_max

    def _calculate_size_score(
        self,
        diameter: float,
        preferred_min: float = 4.0,
        preferred_max: float = 10.0
    ) -> float:
        """
        Calculate adaptive size score with preference for typical player dot sizes.

        The scoring function:
        - Returns 1.0 for blobs in the preferred range (4-10px)
        - Returns reduced scores for smaller blobs (proportional to size)
        - Returns reduced scores for larger blobs (inverse proportional to excess)

        This helps select the most likely player dot when multiple candidates exist,
        as player dots typically appear at 4-10px diameter based on calibration data.

        Args:
            diameter: Blob diameter in pixels
            preferred_min: Lower bound of preferred size range (default: 4.0px)
            preferred_max: Upper bound of preferred size range (default: 10.0px)

        Returns:
            Score from 0.1 to 1.0 (1.0 = optimal size, 0.1 = minimum score)

        Examples:
            - diameter=7px (in range) → 1.0
            - diameter=2px (too small) → 0.5
            - diameter=20px (too large) → ~0.33
        """
        if preferred_min <= diameter <= preferred_max:
            return 1.0
        elif diameter < preferred_min:
            # Penalize smaller blobs proportionally
            return max(0.1, diameter / preferred_min)
        else:
            # Penalize larger blobs inversely
            excess = diameter - preferred_max
            return max(0.1, 1.0 / (1.0 + excess / preferred_max))

    def _validate_and_clamp_position(
        self,
        x: int,
        y: int,
        frame_shape: Tuple[int, int],
        margin: int = 2
    ) -> Tuple[int, int, bool]:
        """
        Validate position is within frame bounds and clamp to safe margin.

        Prevents out-of-bounds coordinates that cause visualization crashes
        and provides diagnostic logging for detection issues.

        Args:
            x, y: Detected position coordinates
            frame_shape: (height, width) of frame
            margin: Minimum pixels from edge (safety margin to avoid partial detections)

        Returns:
            (clamped_x, clamped_y, is_valid) where:
                - clamped_x, clamped_y: Position guaranteed to be in bounds
                - is_valid: True if position was originally valid, False if clamped

        Example:
            - Position (100, 50) in 200x100 frame, margin=2 → (100, 50, True)
            - Position (-5, 50) in 200x100 frame, margin=2 → (2, 50, False)
            - Position (199, 50) in 200x100 frame, margin=2 → (197, 50, False)
        """
        height, width = frame_shape

        # Check if completely out of bounds
        if x < 0 or x >= width or y < 0 or y >= height:
            logger.warning(
                f"Position ({x},{y}) OUT OF BOUNDS for frame {width}x{height} | "
                f"Clamping to valid range"
            )
            # Clamp to frame boundaries
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            return (x, y, False)

        # Check if too close to edge (may be partial/unreliable detection)
        near_edge = (x < margin or x >= width - margin or
                     y < margin or y >= height - margin)

        if near_edge:
            logger.debug(
                f"Position ({x},{y}) near edge (margin={margin}px) | "
                f"Clamping to safe zone"
            )
            # Clamp with margin for safety
            x = max(margin, min(width - margin - 1, x))
            y = max(margin, min(height - margin - 1, y))
            # Still return True since it was technically in bounds
            return (x, y, True)

        return (x, y, True)

    def _validate_contrast(self, frame: np.ndarray, cx: int, cy: int, radius: float) -> bool:
        """
        Validate blob has sufficient contrast against surrounding area.

        Player dots should be significantly brighter than the surrounding minimap
        area to reduce false positives from low-contrast terrain features.

        Args:
            frame: Original BGR frame
            cx, cy: Blob center coordinates
            radius: Blob radius in pixels

        Returns:
            True if blob passes contrast validation, False otherwise

        Example:
            - Bright player dot on dark background → True (high contrast)
            - Dim UI element on similar background → False (low contrast)
        """
        frame_h, frame_w = frame.shape[:2]

        # Sample blob interior (convert to grayscale for brightness)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Sample blob pixels (circular region)
        blob_pixels = []
        for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
            for r in np.linspace(0, radius, 3):
                x = int(cx + r * np.cos(angle))
                y = int(cy + r * np.sin(angle))
                if 0 <= x < frame_w and 0 <= y < frame_h:
                    blob_pixels.append(gray[y, x])

        if not blob_pixels:
            return False

        blob_brightness = np.mean(blob_pixels)

        # Sample surrounding pixels (ring around blob at radius+2 to radius+5)
        surround_pixels = []
        for angle in np.linspace(0, 2*np.pi, 12, endpoint=False):
            for r in np.linspace(radius + 2, radius + 5, 3):
                x = int(cx + r * np.cos(angle))
                y = int(cy + r * np.sin(angle))
                if 0 <= x < frame_w and 0 <= y < frame_h:
                    surround_pixels.append(gray[y, x])

        if not surround_pixels:
            return False

        surround_brightness = np.mean(surround_pixels)

        # Avoid division by zero
        if surround_brightness < 1:
            return True  # If surrounding is nearly black, accept any blob

        # Calculate contrast ratio
        contrast_ratio = blob_brightness / surround_brightness

        # Validate against threshold (default: 1.3 = blob must be 30% brighter)
        passes = contrast_ratio >= self.config.min_contrast_ratio

        logger.debug(
            f"Contrast validation | blob_bright={blob_brightness:.1f} "
            f"surround_bright={surround_brightness:.1f} "
            f"ratio={contrast_ratio:.2f} "
            f"threshold={self.config.min_contrast_ratio:.2f} "
            f"result={'PASS' if passes else 'FAIL'}"
        )

        return passes

    def _validate_ring_structure(self, frame: np.ndarray, blob: Dict[str, Any], gray_frame: np.ndarray) -> float:
        """
        Validate blob has expected dark ring structure.

        Markers have documented multi-layer structure:
        - Inner colored blob (yellow for player, red for enemies)
        - Dark contour (~1-2px black/brown ring) around the colored blob

        This method samples pixels in a ring around detected blob center
        to verify the dark contour presence, providing additional confidence scoring.

        Note: White outer ring detection removed as it may not be clearly visible
        in all capture conditions. Dark ring is more reliable.

        Args:
            frame: Original BGR frame (for dimensions only)
            blob: Detected blob dict with 'center' and 'radius' keys
            gray_frame: Grayscale version of frame (performance: shared across all blobs)

        Returns:
            Confidence boost to add to circularity score (0.0-0.2):
            - 0.2: Dark ring detected
            - 0.0: No dark ring detected or edge-case failure

        Performance: ~0.01ms per blob (24 pixel samples + arithmetic, no conversion)

        Example:
            blob = {'center': (100, 50), 'radius': 6.0}
            boost = _validate_ring_structure(frame, blob, gray_frame)
            # boost = 0.2 if marker has dark ring
        """
        cx, cy = int(blob['center'][0]), int(blob['center'][1])
        radius = blob['radius']

        # Bounds check: skip validation if too close to edge
        frame_h, frame_w = frame.shape[:2]
        check_radius = int(radius + 3)  # Need radius+3px for dark ring sampling
        if (cx - check_radius < 0 or cx + check_radius >= frame_w or
            cy - check_radius < 0 or cy + check_radius >= frame_h):
            logger.debug(
                f"Ring validation skipped | blob at ({cx},{cy}) radius={radius:.1f} "
                f"too close to edge (frame={frame_w}x{frame_h})"
            )
            return 0.0

        # Sample dark ring (just outside color blob at radius+1 to radius+2)
        dark_ring_samples = []
        for r in [radius + 1, radius + 2]:
            for angle in np.linspace(0, 2*np.pi, 12, endpoint=False):  # 12 points per ring
                x = int(cx + r * np.cos(angle))
                y = int(cy + r * np.sin(angle))
                if 0 <= x < frame_w and 0 <= y < frame_h:
                    dark_ring_samples.append(gray_frame[y, x])

        # Validate we got enough samples
        if not dark_ring_samples:
            logger.debug("Ring validation failed | insufficient dark ring samples")
            return 0.0

        # Calculate average brightness for dark ring
        avg_dark = np.mean(dark_ring_samples)

        # Validate dark ring structure (threshold from marker analysis)
        has_dark_ring = avg_dark < 120  # Dark pixels (0-255 scale)

        # Calculate confidence boost
        if has_dark_ring:
            logger.debug(f"Ring validation SUCCESS | dark={avg_dark:.0f} | boost=+0.20")
            return 0.2
        else:
            logger.debug(f"Ring validation FAIL | dark={avg_dark:.0f} | boost=+0.00")
            return 0.0

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect objects in minimap frame.
        
        Args:
            frame: BGR image (ONLY the minimap region, already cropped from full screen)
        
        Returns:
            DetectionResult with player position and other_players status.
            All coordinates are relative to minimap top-left corner (0, 0).
        """
        start_time = time.perf_counter()
        self._detection_count += 1

        try:
            # Detect player and other players (each with appropriate size range)
            player = self._detect_player(frame)
            other_players = self._detect_other_players(frame)
            
            result = DetectionResult(
                player=player,
                other_players=other_players,
                timestamp=time.time()
            )
        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
            result = DetectionResult(
                player=PlayerPosition(detected=False),
                other_players=OtherPlayersStatus(detected=False),
                timestamp=time.time()
            )
        finally:
            # Track performance
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self._total_time_ms += elapsed_ms
            self._max_time_ms = max(self._max_time_ms, elapsed_ms)
            self._min_time_ms = min(self._min_time_ms, elapsed_ms)
            
            # Log warning if detection exceeds 15ms target (YUYV on Pi 4)
            if elapsed_ms > 15.0:
                logger.warning(f"Detection slow: {elapsed_ms:.2f}ms (target <15ms for YUYV on Pi 4)")
        
        return result
    
    def _create_color_mask(self,
                          frame: np.ndarray,
                          hsv_lower: Tuple[int, int, int],
                          hsv_upper: Tuple[int, int, int]) -> np.ndarray:
        """
        Create binary mask for color range.

        Args:
            frame: BGR image
            hsv_lower: (h_min, s_min, v_min)
            hsv_upper: (h_max, s_max, v_max)

        Returns:
            Binary mask (0 or 255)
        """
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Create mask
        lower = np.array(hsv_lower, dtype=np.uint8)
        upper = np.array(hsv_upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        # Morphological operations to clean noise
        # NOTE: 3x3 kernel may remove very small dots (<3px), but necessary for noise reduction
        # If detection fails on small dots, consider reducing kernel size to 2x2
        kernel = np.ones((4, 4), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # Remove noise
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # Fill holes

        return mask
    
    def _find_circular_blobs(self,
                            mask: np.ndarray,
                            frame: Optional[np.ndarray] = None,
                            hsv_frame: Optional[np.ndarray] = None,
                            min_size: int = 4,
                            max_size: int = 100,
                            min_circularity: float = 0.65) -> List[Dict[str, Any]]:
        """
        Find circular blobs in binary mask with multi-stage filtering.

        Filtering pipeline:
        1. Size filtering (diameter range)
        2. Circularity filtering (shape validation)
        3. Aspect ratio filtering (width/height ratio)
        4. Contrast validation (optional, brightness check)

        Args:
            mask: Binary mask image
            frame: Optional original BGR frame for contrast validation
            hsv_frame: Optional HSV frame for sampling S/V values at blob centers
            min_size: Minimum blob diameter in pixels
            max_size: Maximum blob diameter in pixels
            min_circularity: Minimum circularity (0-1)

        Returns:
            List of blobs with keys: 'center', 'radius', 'circularity', 'area',
            'aspect_ratio', 'diameter', 'saturation', 'value'
        """
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        blobs = []
        for contour in contours:
            # Calculate properties
            area = cv2.contourArea(contour)
            if area == 0:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue

            # Circularity = 4π*area / perimeter²
            # Perfect circle = 1.0, less circular = lower value
            circularity = 4 * np.pi * area / (perimeter ** 2)

            # Size filtering (approximate as circle)
            radius = np.sqrt(area / np.pi)
            diameter = radius * 2

            if diameter < min_size or diameter > max_size:
                continue

            # Circularity filtering
            if circularity < min_circularity:
                continue

            # Aspect ratio filtering (NEW)
            # Bounding box should be roughly square for circular dots
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue

            aspect_ratio = w / h
            if (aspect_ratio < self.config.min_aspect_ratio or
                aspect_ratio > self.config.max_aspect_ratio):
                logger.debug(
                    f"Blob rejected | aspect_ratio={aspect_ratio:.2f} outside "
                    f"[{self.config.min_aspect_ratio}, {self.config.max_aspect_ratio}]"
                )
                continue

            # Get centroid
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Sample HSV values at blob center for combined scoring
            if hsv_frame is not None:
                h_center, s_center, v_center = hsv_frame[cy, cx]
                saturation = int(s_center)
                value = int(v_center)
            else:
                # Default to maximum if HSV not provided
                saturation = 255
                value = 255

            # Contrast validation (NEW - optional)
            if self.config.enable_contrast_validation and frame is not None:
                if not self._validate_contrast(frame, cx, cy, radius):
                    logger.debug(
                        f"Blob rejected | insufficient contrast at ({cx},{cy})"
                    )
                    continue

            blobs.append({
                'center': (cx, cy),
                'radius': radius,
                'diameter': diameter,
                'circularity': circularity,
                'area': area,
                'aspect_ratio': aspect_ratio,
                'saturation': saturation,
                'value': value,
                'contour': contour
            })

        return blobs
    
    def _detect_player(self, frame: np.ndarray) -> PlayerPosition:
        """
        Detect single yellow player point using multi-stage filtering and combined scoring.

        Filtering pipeline:
        1. HSV color masking (yellow range: H=26-85, S>67, V>64)
        2. Morphological operations (noise removal)
        3. Blob detection with size + circularity + aspect + contrast filters
        4. Combined score selection: max(size_score × saturation × value × circularity)

        Args:
            frame: BGR minimap image

        Returns:
            PlayerPosition with detected status and coordinates
        """

        # Get calibrated blob size range for player
        adaptive_min, adaptive_max = self._calculate_adaptive_blob_sizes(frame, blob_type='player')

        # Convert to HSV for S/V sampling at blob centers
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Create color mask for yellow
        mask = self._create_color_mask(
            frame,
            self.config.player_hsv_lower,
            self.config.player_hsv_upper
        )

        # Find circular blobs with multi-stage filtering
        blobs = self._find_circular_blobs(
            mask,
            frame=frame,  # For contrast validation
            hsv_frame=hsv,  # For S/V sampling
            min_size=adaptive_min,
            max_size=adaptive_max,
            min_circularity=self.config.min_circularity
        )
        
        if not blobs:
            self._last_player_pos = None
            return PlayerPosition(detected=False)

        # Select blob with highest combined score
        # Combined score = size_score × saturation × value × circularity
        # This prioritizes blobs that are:
        # - Optimal size (4-10px preferred)
        # - High saturation (bright yellow color)
        # - High brightness (visible against background)
        # - Circular shape (round dots, not artifacts)
        def combined_score(blob):
            size_score = self._calculate_size_score(blob['diameter'])
            return (size_score *
                    float(blob['saturation']) *
                    float(blob['value']) *
                    blob['circularity'])

        best_blob = max(blobs, key=combined_score)
        cx, cy = best_blob['center']

        # Validate and clamp position to ensure it's within bounds
        cx, cy, is_valid = self._validate_and_clamp_position(
            cx, cy, frame.shape[:2], margin=2
        )

        if not is_valid:
            logger.warning(
                f"Player position clamped | "
                f"blob_center={best_blob['center']} → ({cx},{cy})"
            )

        # Apply temporal smoothing if enabled
        if self.config.temporal_smoothing and self._last_player_pos is not None:
            alpha = self.config.smoothing_alpha
            prev_x, prev_y = self._last_player_pos
            cx = int(alpha * cx + (1 - alpha) * prev_x)
            cy = int(alpha * cy + (1 - alpha) * prev_y)
        
        self._last_player_pos = (cx, cy)

        # RING VALIDATION DISABLED: Use circularity score only
        # Detection relies on HSV color matching + circularity filtering
        confidence = best_blob['circularity']

        return PlayerPosition(
            detected=True,
            x=cx,
            y=cy,
            confidence=confidence
        )
    
    def _detect_other_players(self, frame: np.ndarray) -> OtherPlayersStatus:
        """
        Detect multiple red other_player points using multi-stage filtering.

        Red color wraps around HSV hue (0-15 and 165-180), so we apply
        detection with two separate HSV ranges and merge results.

        Filtering pipeline:
        1. HSV color masking (two red ranges)
        2. Morphological operations (noise removal)
        3. Blob detection with size + circularity + aspect + contrast filters
        4. Deduplication (merge overlapping detections)

        Args:
            frame: BGR minimap image

        Returns:
            OtherPlayersStatus with detected flag and count
        """

        # Get calibrated blob size range for other players (smaller than player)
        adaptive_min, adaptive_max = self._calculate_adaptive_blob_sizes(frame, blob_type='other')

        # Convert to HSV for S/V sampling
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        all_blobs = []

        # Red wraps around HSV, need multiple ranges
        for hsv_lower, hsv_upper in self.config.other_player_hsv_ranges:
            mask = self._create_color_mask(frame, hsv_lower, hsv_upper)
            blobs = self._find_circular_blobs(
                mask,
                frame=frame,  # For contrast validation
                hsv_frame=hsv,  # For S/V sampling
                min_size=adaptive_min,
                max_size=adaptive_max,
                min_circularity=self.config.min_circularity_other
            )
            all_blobs.extend(blobs)
        
        # Remove duplicates (same position detected in multiple ranges)
        unique_blobs = self._deduplicate_blobs(all_blobs, distance_threshold=5)

        # Extract and validate positions (ring validation disabled)
        positions = []
        for blob in unique_blobs:
            cx, cy = blob['center']

            # RING VALIDATION DISABLED: Use circularity score only
            # Detection relies on HSV color matching + circularity filtering
            confidence = blob['circularity']
            blob['confidence'] = confidence

            logger.debug(f"Other player at ({cx},{cy}) | circularity={confidence:.3f}")

            # Validate and clamp position to ensure it's within bounds
            cx, cy, is_valid = self._validate_and_clamp_position(
                cx, cy, frame.shape[:2], margin=2
            )

            if not is_valid:
                logger.warning(
                    f"Other player position clamped | "
                    f"blob_center={blob['center']} → ({cx},{cy})"
                )

            positions.append((cx, cy))

        return OtherPlayersStatus(
            detected=len(unique_blobs) > 0,
            count=len(unique_blobs),
            positions=positions
        )
    
    def _deduplicate_blobs(self, blobs: List[Dict], distance_threshold: float = 5.0) -> List[Dict]:
        """
        Remove duplicate blobs that are close to each other.
        
        Args:
            blobs: List of blob dictionaries
            distance_threshold: Maximum distance (pixels) to consider duplicates
        
        Returns:
            Deduplicated list of blobs
        """
        if not blobs:
            return []
        
        # Sort by circularity (best first)
        sorted_blobs = sorted(blobs, key=lambda b: b['circularity'], reverse=True)
        
        unique = []
        for blob in sorted_blobs:
            cx, cy = blob['center']
            
            # Check if too close to existing unique blob
            is_duplicate = False
            for unique_blob in unique:
                ux, uy = unique_blob['center']
                distance = np.sqrt((cx - ux)**2 + (cy - uy)**2)
                if distance < distance_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(blob)
        
        return unique
    
    def visualize(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
        """
        Draw detection results on frame for debugging.

        Args:
            frame: Original BGR frame
            result: Detection result

        Returns:
            Frame with detection visualization (returns original frame copy on error)
        """
        logger.debug(
            f"Visualizing detection | frame_shape={frame.shape if frame is not None else None} | "
            f"player_detected={result.player.detected if result else None} | "
            f"other_count={result.other_players.count if result and result.other_players else 0}"
        )

        try:
            # Validate inputs
            if frame is None or frame.size == 0:
                logger.error("visualize() called with null or empty frame")
                return np.zeros((100, 100, 3), dtype=np.uint8)  # Return blank frame

            if result is None:
                logger.error("visualize() called with null result")
                return frame.copy()

            vis = frame.copy()
            frame_height, frame_width = vis.shape[:2]

            # Draw player
            if result.player.detected:
                x, y = result.player.x, result.player.y

                # Validate coordinates are within frame bounds
                if not (0 <= x < frame_width and 0 <= y < frame_height):
                    logger.warning(
                        f"Player position ({x},{y}) out of frame bounds ({frame_width}x{frame_height}) - "
                        f"skipping visualization"
                    )
                else:
                    # Draw crosshair
                    cv2.drawMarker(vis, (x, y), (0, 255, 255),
                                  markerType=cv2.MARKER_CROSS,
                                  markerSize=10, thickness=2)

                    # Draw circle
                    cv2.circle(vis, (x, y), 8, (0, 255, 255), 2)

                    # Draw label
                    label = f"Player ({x},{y}) {result.player.confidence:.2f}"
                    cv2.putText(vis, label,
                               (x + 12, y - 12),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            # Draw other players
            if result.other_players.detected:
                valid_positions = []
                invalid_positions = []

                # Validate all positions first
                for x, y in result.other_players.positions:
                    if 0 <= x < frame_width and 0 <= y < frame_height:
                        valid_positions.append((x, y))
                    else:
                        invalid_positions.append((x, y))

                # Log invalid positions
                if invalid_positions:
                    logger.warning(
                        f"{len(invalid_positions)} other player position(s) out of bounds: "
                        f"{invalid_positions} (frame: {frame_width}x{frame_height})"
                    )

                # Draw each valid other player position as red circle
                for x, y in valid_positions:
                    cv2.circle(vis, (x, y), 6, (0, 0, 255), 2)  # Red circle
                    cv2.drawMarker(vis, (x, y), (0, 0, 255),
                                  markerType=cv2.MARKER_CROSS,
                                  markerSize=8, thickness=1)

                # Draw count label
                label = f"Other Players: {result.other_players.count}"
                cv2.putText(vis, label,
                           (10, 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # Draw frame count
            cv2.putText(vis, f"Frame: {self._detection_count}",
                       (10, vis.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            logger.debug("Visualization successful")
            return vis

        except Exception as e:
            logger.error(
                f"Visualization failed: {e} | "
                f"frame_shape={frame.shape if frame is not None else 'None'} | "
                f"player_detected={result.player.detected if result else 'N/A'} | "
                f"player_pos={f'({result.player.x},{result.player.y})' if (result and result.player.detected) else 'N/A'}",
                exc_info=True
            )
            # Return original frame copy to prevent cascading failures
            try:
                return frame.copy() if frame is not None else np.zeros((100, 100, 3), dtype=np.uint8)
            except:
                # Ultimate fallback
                return np.zeros((100, 100, 3), dtype=np.uint8)
    
    def get_debug_masks(self, frame: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Get color masks for debugging (visualize what colors are detected).
        
        Args:
            frame: BGR minimap image
        
        Returns:
            Dictionary with 'player_mask' and 'other_players_mask' keys
        """
        # Player mask
        player_mask = self._create_color_mask(
            frame,
            self.config.player_hsv_lower,
            self.config.player_hsv_upper
        )
        
        # Other players masks (combined)
        other_players_mask = np.zeros_like(player_mask)
        for hsv_lower, hsv_upper in self.config.other_player_hsv_ranges:
            mask = self._create_color_mask(frame, hsv_lower, hsv_upper)
            other_players_mask = cv2.bitwise_or(other_players_mask, mask)
        
        return {
            'player_mask': player_mask,
            'other_players_mask': other_players_mask
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get detection performance statistics.
        
        Returns:
            Dictionary with avg_ms, max_ms, min_ms, count
        """
        if self._detection_count == 0:
            return {
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "min_ms": 0.0,
                "count": 0
            }
        
        return {
            "avg_ms": self._total_time_ms / self._detection_count,
            "max_ms": self._max_time_ms,
            "min_ms": self._min_time_ms if self._min_time_ms != float('inf') else 0.0,
            "count": self._detection_count
        }
    
    def reset_performance_stats(self):
        """Reset performance tracking counters."""
        self._total_time_ms = 0.0
        self._max_time_ms = 0.0
        self._min_time_ms = float('inf')
        self._detection_count = 0


# Global singleton instance
_detector: Optional[MinimapObjectDetector] = None
_detector_lock = __import__('threading').Lock()


def get_detector() -> Optional[MinimapObjectDetector]:
    """
    Get the global MinimapObjectDetector singleton instance.

    Returns:
        MinimapObjectDetector instance if initialized, None otherwise
    """
    global _detector
    return _detector


def set_detector(detector: Optional[MinimapObjectDetector]) -> None:
    """
    Set the global MinimapObjectDetector singleton instance.

    Args:
        detector: MinimapObjectDetector instance or None to clear
    """
    global _detector
    with _detector_lock:
        _detector = detector
        if detector:
            logger.info("Object detector instance set")
        else:
            logger.info("Object detector instance cleared")
