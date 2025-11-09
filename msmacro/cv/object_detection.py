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
    # Player detection (yellow point) - PLACEHOLDER VALUES FOR JPEG DEVELOPMENT
    # These are widened ranges to handle JPEG compression artifacts
    # MUST be recalibrated on test Pi with real YUYV frames for production
    player_hsv_lower: Tuple[int, int, int] = (15, 60, 80)    # Widened from (20, 100, 100)
    player_hsv_upper: Tuple[int, int, int] = (40, 255, 255)  # Widened from (30, 255, 255)

    # Other players detection (red points) - PLACEHOLDER VALUES FOR JPEG DEVELOPMENT
    # Red wraps around in HSV, need two ranges
    # MUST be recalibrated on test Pi with real YUYV frames for production
    other_player_hsv_ranges: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = None

    # Blob filtering
    min_blob_size: int = 3  # Minimum diameter in pixels
    max_blob_size: int = 15  # Maximum diameter in pixels
    min_circularity: float = 0.6  # Minimum circularity for player
    min_circularity_other: float = 0.5  # Minimum circularity for other players

    # Temporal smoothing
    temporal_smoothing: bool = True
    smoothing_alpha: float = 0.3  # EMA alpha (0-1, higher = less smoothing)

    def __post_init__(self):
        """Initialize default values."""
        if self.other_player_hsv_ranges is None:
            # Default red ranges for JPEG (PLACEHOLDER - widened for compression tolerance)
            self.other_player_hsv_ranges = [
                ((0, 70, 70), (12, 255, 255)),      # Lower red (widened)
                ((168, 70, 70), (180, 255, 255))    # Upper red (widened)
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
        
        logger.info("MinimapObjectDetector initialized")
        logger.warning("Using PLACEHOLDER HSV ranges - MUST calibrate on test Pi with YUYV frames")
    
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
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # Remove noise
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # Fill holes
        
        return mask
    
    def _find_circular_blobs(self,
                            mask: np.ndarray,
                            min_size: int,
                            max_size: int,
                            min_circularity: float) -> List[Dict[str, Any]]:
        """
        Find circular blobs in binary mask.
        
        Args:
            mask: Binary mask image
            min_size: Minimum blob diameter in pixels
            max_size: Maximum blob diameter in pixels
            min_circularity: Minimum circularity (0-1)
        
        Returns:
            List of blobs with keys: 'center', 'radius', 'circularity', 'area'
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
            
            # Get centroid
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            blobs.append({
                'center': (cx, cy),
                'radius': radius,
                'circularity': circularity,
                'area': area,
                'contour': contour
            })
        
        return blobs
    
    def _detect_player(self, frame: np.ndarray) -> PlayerPosition:
        """
        Detect single yellow player point.
        
        Args:
            frame: BGR minimap image
        
        Returns:
            PlayerPosition with detected status and coordinates
        """
        # Create color mask for yellow
        mask = self._create_color_mask(
            frame,
            self.config.player_hsv_lower,
            self.config.player_hsv_upper
        )
        
        # Find circular blobs
        blobs = self._find_circular_blobs(
            mask,
            self.config.min_blob_size,
            self.config.max_blob_size,
            self.config.min_circularity
        )
        
        if not blobs:
            self._last_player_pos = None
            return PlayerPosition(detected=False)
        
        # Take blob closest to center (most likely player)
        # This handles case where multiple yellow-ish points exist
        frame_center = (frame.shape[1] // 2, frame.shape[0] // 2)
        
        def distance_to_center(blob):
            cx, cy = blob['center']
            dx = cx - frame_center[0]
            dy = cy - frame_center[1]
            return dx**2 + dy**2
        
        best_blob = min(blobs, key=distance_to_center)
        cx, cy = best_blob['center']
        
        # Apply temporal smoothing if enabled
        if self.config.temporal_smoothing and self._last_player_pos is not None:
            alpha = self.config.smoothing_alpha
            prev_x, prev_y = self._last_player_pos
            cx = int(alpha * cx + (1 - alpha) * prev_x)
            cy = int(alpha * cy + (1 - alpha) * prev_y)
        
        self._last_player_pos = (cx, cy)
        
        return PlayerPosition(
            detected=True,
            x=cx,
            y=cy,
            confidence=best_blob['circularity']
        )
    
    def _detect_other_players(self, frame: np.ndarray) -> OtherPlayersStatus:
        """
        Detect multiple red other_player points.
        
        Args:
            frame: BGR minimap image
        
        Returns:
            OtherPlayersStatus with detected flag and count
        """
        all_blobs = []
        
        # Red wraps around HSV, need multiple ranges
        for hsv_lower, hsv_upper in self.config.other_player_hsv_ranges:
            mask = self._create_color_mask(frame, hsv_lower, hsv_upper)
            blobs = self._find_circular_blobs(
                mask,
                self.config.min_blob_size,
                self.config.max_blob_size,
                self.config.min_circularity_other
            )
            all_blobs.extend(blobs)
        
        # Remove duplicates (same position detected in multiple ranges)
        unique_blobs = self._deduplicate_blobs(all_blobs, distance_threshold=5)

        # Extract positions for visualization/debugging
        positions = [tuple(blob['center']) for blob in unique_blobs]

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
