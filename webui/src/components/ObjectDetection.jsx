import { useState, useEffect } from "react";
import { 
  getObjectDetectionStatus, 
  startObjectDetection, 
  stopObjectDetection 
} from "../api";
import { Button } from "./ui/button";
import { clsx } from "clsx";
import { CalibrationWizard } from "./CalibrationWizard";

function ObjectDetectionPreview({ lastResult, enabled }) {
  const [imgUrl, setImgUrl] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setImgUrl(null);
      setError(null);
      return;
    }

    // Don't try to fetch if we don't have a detection result yet
    if (!lastResult) {
      setError("waiting");
      setImgUrl(null);
      return;
    }

    // Use detection preview endpoint which includes all overlays:
    // - Player position (yellow crosshair + circle)
    // - Other players positions (red circles + crosshairs)
    // - Detection confidence labels
    // - Frame count
    const url = `/api/cv/detection-preview?t=${Date.now()}`;

    // Validate the preview is available before setting it
    setLoading(true);
    fetch(url)
      .then(response => {
        if (!response.ok) {
          if (response.status === 404) {
            setError("not_available");
          } else {
            setError("error");
          }
          setImgUrl(null);
        } else {
          setImgUrl(url);
          setError(null);
        }
      })
      .catch(() => {
        setError("error");
        setImgUrl(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [lastResult?.timestamp, enabled]);

  if (!enabled) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Enable detection to see live preview with overlays</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Loading preview...</p>
      </div>
    );
  }

  if (error === "waiting") {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Waiting for detection results...</p>
      </div>
    );
  }

  if (error === "not_available") {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Preview not available (no minimap frame captured yet)</p>
      </div>
    );
  }

  if (error === "error" || !imgUrl) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-red-50 p-8 text-center">
        <p className="text-sm text-red-600">Failed to load detection preview</p>
      </div>
    );
  }

  return (
    <div className="border border-gray-300 rounded overflow-hidden bg-white">
      <img
        src={imgUrl}
        alt="Detection Preview"
        className="block w-full h-auto"
        style={{ imageRendering: 'pixelated', minHeight: '200px', objectFit: 'contain' }}
        onError={(e) => {
          console.error("Failed to load detection preview");
          setError("error");
        }}
      />
    </div>
  );
}

export function ObjectDetection() {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);
  const [showCalibration, setShowCalibration] = useState(false);
  const [calibrationType, setCalibrationType] = useState("player");

  // Fetch initial status
  useEffect(() => {
    fetchStatus();
  }, []);

  // Poll for updates when enabled
  useEffect(() => {
    if (!enabled) return;

    const interval = setInterval(fetchStatus, 1000); // Poll every second
    return () => clearInterval(interval);
  }, [enabled]);

  const fetchStatus = async () => {
    try {
      const data = await getObjectDetectionStatus();
      setEnabled(data.enabled);
      setLastResult(data.last_result);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch detection status:", err);
      setError(err.message);
    }
  };

  const handleToggle = async () => {
    setLoading(true);
    setError(null);

    try {
      if (enabled) {
        await stopObjectDetection();
        setEnabled(false);
        setLastResult(null);
      } else {
        await startObjectDetection();
        setEnabled(true);
      }
    } catch (err) {
      console.error("Failed to toggle detection:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = () => {
    if (!enabled) return "text-gray-500";
    if (lastResult?.player?.detected) return "text-green-600";
    return "text-yellow-600";
  };

  const getStatusText = () => {
    if (!enabled) return "Disabled";
    if (!lastResult) return "Starting...";
    if (lastResult.player?.detected) return "Player Detected";
    return "No Detection";
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Object Detection</h2>
          <p className="text-sm text-gray-600 mt-1">
            Track player position on minimap
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={clsx("flex items-center gap-2", getStatusColor())}>
            <div className={clsx(
              "w-3 h-3 rounded-full",
              enabled && lastResult?.player?.detected ? "bg-green-500 animate-pulse" :
              enabled ? "bg-yellow-500" :
              "bg-gray-400"
            )} />
            <span className="font-medium">{getStatusText()}</span>
          </div>
          <Button
            onClick={handleToggle}
            disabled={loading}
            variant={enabled ? "destructive" : "default"}
          >
            {loading ? "..." : enabled ? "Stop Detection" : "Start Detection"}
          </Button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      {/* Calibration Section */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
        <h3 className="font-semibold text-indigo-900 mb-2">Color Calibration</h3>
        <p className="text-sm text-indigo-800 mb-3">
          Click to calibrate HSV color ranges for accurate detection with real YUYV frames.
        </p>
        <div className="flex gap-3">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setCalibrationType("player");
              setShowCalibration(true);
            }}
          >
            Calibrate Player Color
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setCalibrationType("other_player");
              setShowCalibration(true);
            }}
          >
            Calibrate Other Players
          </Button>
        </div>
      </div>

      {/* Warning about placeholder HSV */}
      {enabled && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800 text-sm font-medium">
            ⚠️ Using placeholder HSV ranges
          </p>
          <p className="text-yellow-700 text-xs mt-1">
            These values are for JPEG development only. Calibrate on test Pi with real YUYV frames for production use.
          </p>
        </div>
      )}

      {/* Detection Results */}
      {enabled && (
        <div className="grid grid-cols-2 gap-4">
          {/* Player Detection Card */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              Player Position
            </h3>
            
            {lastResult?.player?.detected ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">X Position:</span>
                  <span className="text-sm font-mono font-medium text-gray-900">
                    {lastResult.player.x} px
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">Y Position:</span>
                  <span className="text-sm font-mono font-medium text-gray-900">
                    {lastResult.player.y} px
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">Confidence:</span>
                  <span className="text-sm font-mono font-medium text-gray-900">
                    {(lastResult.player.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                
                {/* Visual position indicator */}
                <div className="mt-4 p-3 bg-gray-50 rounded">
                  <div className="relative w-full h-20 bg-gray-200 rounded">
                    {/* Minimap dimensions: 340x86 */}
                    <div
                      className="absolute w-2 h-2 bg-yellow-500 rounded-full border-2 border-white shadow-lg"
                      style={{
                        left: `${(lastResult.player.x / 340) * 100}%`,
                        top: `${(lastResult.player.y / 86) * 100}%`,
                        transform: 'translate(-50%, -50%)'
                      }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 text-center mt-1">
                    Minimap (340×86)
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-6">
                <div className="w-12 h-12 mx-auto mb-2 bg-gray-100 rounded-full flex items-center justify-center">
                  <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <p className="text-sm text-gray-500">No player detected</p>
              </div>
            )}
          </div>

          {/* Other Players Detection Card */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              Other Players
            </h3>
            
            {lastResult?.other_players?.detected ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">Status:</span>
                  <span className="text-sm font-medium text-red-600">
                    ⚠️ Detected
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">Count:</span>
                  <span className="text-sm font-mono font-medium text-gray-900">
                    {lastResult.other_players.count}
                  </span>
                </div>
                
                <div className="mt-4 p-3 bg-red-50 rounded border border-red-200">
                  <p className="text-xs text-red-800 font-medium">
                    Other players nearby!
                  </p>
                  <p className="text-xs text-red-600 mt-1">
                    Consider defensive actions or repositioning
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-6">
                <div className="w-12 h-12 mx-auto mb-2 bg-green-50 rounded-full flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-sm text-green-600 font-medium">Clear</p>
                <p className="text-xs text-gray-500 mt-1">No other players detected</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stats */}
      {enabled && lastResult && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4">
          <h3 className="text-sm font-semibold text-gray-700">Detection Stats & Preview</h3>
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-gray-600">Last Update:</span>
              <p className="font-mono text-gray-900">
                {new Date(lastResult.timestamp * 1000).toLocaleTimeString()}
              </p>
            </div>
            <div>
              <span className="text-gray-600">Player Status:</span>
              <p className="font-medium text-gray-900">
                {lastResult.player?.detected ? "✓ Detected" : "✗ Not Found"}
              </p>
            </div>
            <div>
              <span className="text-gray-600">Other Players:</span>
              <p className="font-medium text-gray-900">
                {lastResult.other_players?.count || 0} found
              </p>
            </div>
          </div>
          {/* Live minimap preview with overlays */}
          <ObjectDetectionPreview lastResult={lastResult} enabled={enabled} />
        </div>
      )}

      {/* Info when disabled */}
      {!enabled && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            Object Detection is Off
          </h3>
          <p className="text-sm text-blue-700 mb-4">
            Enable detection to track player position on the minimap
          </p>
          <ul className="text-xs text-blue-600 text-left max-w-md mx-auto space-y-1">
            <li>• Detects yellow player point (single object)</li>
            <li>• Detects red other_player points (multiple objects)</li>
            <li>• Returns precise (x, y) coordinates</li>
            <li>• Updates continuously at 2 FPS</li>
          </ul>
        </div>
      )}

      {/* Calibration Wizard Modal */}
      {showCalibration && (
        <CalibrationWizard
          colorType={calibrationType}
          onComplete={(result) => {
            console.log("Calibration complete:", result);
            setShowCalibration(false);
            fetchStatus(); // Refresh to show updated detection
          }}
          onCancel={() => setShowCalibration(false)}
        />
      )}
    </div>
  );
}
