import { useState, useEffect, useRef } from "react";
import { Button } from "./ui/button";
import { clsx } from "clsx";

/**
 * Calibration Wizard for HSV color range tuning.
 * 
 * Workflow:
 * 1. User loads live frame from camera
 * 2. User clicks on player dot (or other player dot)
 * 3. Repeat for 5 frames
 * 4. System calculates optimal HSV ranges
 * 5. Preview detection mask
 * 6. Apply or retry
 */
export function CalibrationWizard({ colorType = "player", onComplete, onCancel }) {
  const [step, setStep] = useState("intro"); // intro, collect, preview, apply
  const [samples, setSamples] = useState([]);
  const [currentFrame, setCurrentFrame] = useState(null);
  const [frameTimestamp, setFrameTimestamp] = useState(Date.now());
  const [calibrationResult, setCalibrationResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [naturalSize, setNaturalSize] = useState({ width: 340, height: 86 });
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const panStartRef = useRef({ x: 0, y: 0 });
  const didDragRef = useRef(false);
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  const REQUIRED_SAMPLES = 5;

  // Load a fresh frame
  const loadFrame = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/cv/raw-minimap?t=${Date.now()}`);

      if (!response.ok) {
        let message = `Failed to load frame (HTTP ${response.status})`;
        try {
          const data = await response.json();
          if (data?.message) {
            message = data.message;
            if (data.details?.active_config === null) {
              message += " Configure and activate a CV map region first.";
            }
          }
        } catch {
          try {
            const text = await response.text();
            if (text) message = text;
          } catch {
            /* no-op */
          }
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const dataUrl = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
      });

      setCurrentFrame(dataUrl);
      setPan({ x: 0, y: 0 });
      setFrameTimestamp(Date.now());
    } catch (err) {
      setError(err.message);
      console.error("Failed to load frame:", err);
    } finally {
      setLoading(false);
    }
  };

  // Start collection process
  const startCollection = async () => {
    await loadFrame();
    setStep("collect");
    setSamples([]);
  };

  // Handle click on frame
  const handleFrameClick = async (e) => {
    if (step !== "collect" || samples.length >= REQUIRED_SAMPLES) return;
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }

    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const displayX = e.clientX - rect.left;
    const displayY = e.clientY - rect.top;

    // Convert screen point → image space (account for pan + zoom)
    const x = Math.round((displayX - pan.x) / zoom);
    const y = Math.round((displayY - pan.y) / zoom);

    if (Number.isNaN(x) || Number.isNaN(y)) {
      setError("Click inside the minimap area.");
      return;
    }

    const clampedX = Math.max(0, Math.min(naturalSize.width - 1, x));
    const clampedY = Math.max(0, Math.min(naturalSize.height - 1, y));

    // Add sample
    const newSample = {
      frame: currentFrame.split(',')[1], // Remove data:image/png;base64, prefix
      x: clampedX,
      y: clampedY,
      timestamp: Date.now()
    };

    const newSamples = [...samples, newSample];
    setSamples(newSamples);

    // Load next frame if more samples needed
    if (newSamples.length < REQUIRED_SAMPLES) {
      await loadFrame();
    } else {
      // All samples collected, calibrate
      await performCalibration(newSamples);
    }
  };

  // Perform calibration with collected samples
  const performCalibration = async (sampleList) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/cv/object-detection/calibrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          color_type: colorType,
          samples: sampleList
        })
      });

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error || "Calibration failed");
      }

      setCalibrationResult(result);
      setStep("preview");
    } catch (err) {
      setError(err.message);
      console.error("Calibration failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // Apply calibration
  const applyCalibration = async () => {
    setLoading(true);
    setError(null);
    try {
      let config;
      if (colorType === "player") {
        config = {
          player_hsv_lower: calibrationResult.hsv_lower,
          player_hsv_upper: calibrationResult.hsv_upper,
        };
      } else {
        config = {
          other_player_hsv_ranges: [
            [calibrationResult.hsv_lower, calibrationResult.hsv_upper],
          ],
        };
      }

      const response = await fetch('/api/cv/object-detection/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config })
      });

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error || "Failed to apply config");
      }

      setStep("apply");
      
      // Call onComplete callback
      if (onComplete) {
        onComplete(calibrationResult);
      }
    } catch (err) {
      setError(err.message);
      console.error("Failed to apply calibration:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleImgLoad = (e) => {
    const naturalWidth = e.target.naturalWidth || naturalSize.width;
    const naturalHeight = e.target.naturalHeight || naturalSize.height;
    setNaturalSize({ width: naturalWidth, height: naturalHeight });
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e) => {
    if (step !== "collect") return;
    e.preventDefault();
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    panStartRef.current = { ...pan };
    setIsDragging(true);
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
      didDragRef.current = true;
    }
    setPan({
      x: panStartRef.current.x + dx,
      y: panStartRef.current.y + dy,
    });
  };

  useEffect(() => {
    const handleMouseUp = () => setIsDragging(false);
    window.addEventListener("mouseup", handleMouseUp);
    return () => window.removeEventListener("mouseup", handleMouseUp);
  }, []);

  return (
    <div className="fixed inset-0 bg-gray-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">
            {colorType === "player" ? "Player" : "Other Players"} Color Calibration
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            Click on the {colorType === "player" ? "yellow player dot" : "red other player dots"} in 5 different frames
          </p>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Intro Step */}
          {step === "intro" && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="font-semibold text-blue-900 mb-2">How it works:</h3>
                <ol className="text-sm text-blue-800 space-y-2 list-decimal list-inside">
                  <li>Click on the {colorType} dot in 5 different frames</li>
                  <li>System samples the pixel colors around your clicks</li>
                  <li>Optimal HSV color ranges are calculated automatically</li>
                  <li>Preview the detection mask before applying</li>
                </ol>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="text-sm text-yellow-800">
                  <strong>Tips:</strong> Click precisely on the center of the {colorType} dot. 
                  Try to collect samples from different game scenarios (day/night, different positions, etc.).
                </p>
              </div>

              <Button onClick={startCollection} disabled={loading}>
                Start Calibration
              </Button>
            </div>
          )}

          {/* Collection Step */}
          {step === "collect" && (
            <div className="space-y-4">
              {/* Progress */}
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Sample {samples.length + 1} of {REQUIRED_SAMPLES}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setZoom(Math.max(1, zoom - 0.5))}
                    disabled={zoom <= 1}
                  >
                    Zoom -
                  </Button>
                  <span className="text-sm text-gray-600 px-2 py-1">{Math.round(zoom * 100)}%</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setZoom(Math.min(4, zoom + 0.5))}
                    disabled={zoom >= 4}
                  >
                    Zoom +
                  </Button>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(samples.length / REQUIRED_SAMPLES) * 100}%` }}
                />
              </div>

              {/* Frame Display */}
                  {currentFrame && (
                    <div
                      ref={containerRef}
                      className="border border-gray-300 rounded-lg overflow-hidden w-full min-h-[260px] bg-gray-100 cursor-grab active:cursor-grabbing"
                      onMouseDown={handleMouseDown}
                      onMouseMove={handleMouseMove}
                      onClick={handleFrameClick}
                    >
                      <img
                        ref={imgRef}
                        src={currentFrame}
                        alt="Minimap"
                        onLoad={handleImgLoad}
                        className="select-none pointer-events-none"
                        style={{
                          width: naturalSize.width,
                          height: naturalSize.height,
                          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                          transformOrigin: "top left",
                          userSelect: "none",
                        }}
                      />
                    </div>
                  )}

              {loading && (
                <div className="text-center text-gray-600">
                  Loading frame...
                </div>
              )}

              {/* Sample Markers */}
              {samples.length > 0 && (
                <div className="text-xs text-gray-600">
                  Collected: {samples.map((s, i) => `(${s.x}, ${s.y})`).join(", ")}
                </div>
              )}
            </div>
          )}

          {/* Preview Step */}
          {step === "preview" && calibrationResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {/* Original Frame */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Original Frame</h3>
                  <img
                    src={currentFrame}
                    alt="Original"
                    className="w-full h-auto border border-gray-300 rounded"
                  />
                </div>

                {/* Detection Mask */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Detection Mask</h3>
                  <img
                    src={`data:image/png;base64,${calibrationResult.preview_mask}`}
                    alt="Mask Preview"
                    className="w-full h-auto border border-gray-300 rounded"
                  />
                </div>
              </div>

              {/* HSV Ranges */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-2">Calibrated HSV Ranges</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Lower: </span>
                    <span className="font-mono">
                      [{calibrationResult.hsv_lower.join(", ")}]
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Upper: </span>
                    <span className="font-mono">
                      [{calibrationResult.hsv_upper.join(", ")}]
                    </span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <Button onClick={applyCalibration} disabled={loading}>
                  Apply Calibration
                </Button>
                <Button variant="outline" onClick={startCollection}>
                  Retry
                </Button>
              </div>
            </div>
          )}

          {/* Apply Success Step */}
          {step === "apply" && (
            <div className="space-y-4 text-center">
              <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900">
                Calibration Applied!
              </h3>
              <p className="text-sm text-gray-600">
                The new color ranges have been saved and are now active.
              </p>
              <Button onClick={() => onComplete && onComplete(calibrationResult)}>
                Done
              </Button>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 text-sm">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
