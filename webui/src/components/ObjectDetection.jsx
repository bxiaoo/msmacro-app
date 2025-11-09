import { useState, useEffect, useRef } from "react";
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
  const [retryCount, setRetryCount] = useState(0);
  const retryTimeoutRef = useRef(null);

  useEffect(() => {
    // Cleanup timeout on unmount or when dependencies change
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      setImgUrl(null);
      setError(null);
      setRetryCount(0);
      return;
    }

    // Don't try to fetch if we don't have a detection result yet
    if (!lastResult) {
      setError("waiting");
      setImgUrl(null);
      setRetryCount(0);
      return;
    }

    // Reset retry count when we get a new detection result
    setRetryCount(0);

    // Fetch preview with retry logic
    const fetchPreview = async (attempt = 0) => {
      const url = `/api/cv/detection-preview?t=${Date.now()}`;

      setLoading(true);

      try {
        const response = await fetch(url);

        if (!response.ok) {
          const contentType = response.headers.get('content-type');

          // Parse JSON error responses (from cv_get_raw_minimap)
          if (contentType?.includes('application/json')) {
            try {
              const errorData = await response.json();
              console.log('Detection preview JSON error:', errorData);

              // For 404, retry with backoff
              if (response.status === 404 && attempt < 5) {
                const delays = [500, 1000, 2000, 3000, 5000];
                const delay = delays[attempt];

                setError({ type: "retrying", attempt: attempt + 1 });
                setRetryCount(attempt + 1);

                retryTimeoutRef.current = setTimeout(() => {
                  fetchPreview(attempt + 1);
                }, delay);
                return;
              }

              // Set detailed error with all information
              setError({
                type: errorData.error || 'unknown',
                message: errorData.message || 'Unknown error occurred',
                details: errorData.details,
                status: response.status
              });
              setImgUrl(null);
              return;
            } catch (jsonErr) {
              console.error('Failed to parse JSON error:', jsonErr);
            }
          }

          // Parse text error responses (from detector state checks)
          if (contentType?.includes('text/')) {
            try {
              const errorText = await response.text();
              console.log('Detection preview text error:', errorText);

              // For 404, retry with backoff
              if (response.status === 404 && attempt < 5) {
                const delays = [500, 1000, 2000, 3000, 5000];
                const delay = delays[attempt];

                setError({ type: "retrying", attempt: attempt + 1 });
                setRetryCount(attempt + 1);

                retryTimeoutRef.current = setTimeout(() => {
                  fetchPreview(attempt + 1);
                }, delay);
                return;
              }

              setError({
                type: 'text_error',
                message: errorText || `HTTP ${response.status} error`,
                status: response.status
              });
              setImgUrl(null);
              return;
            } catch (textErr) {
              console.error('Failed to parse text error:', textErr);
            }
          }

          // Fallback for unknown content types
          if (response.status === 404 && attempt < 5) {
            const delays = [500, 1000, 2000, 3000, 5000];
            const delay = delays[attempt];

            setError({ type: "retrying", attempt: attempt + 1 });
            setRetryCount(attempt + 1);

            retryTimeoutRef.current = setTimeout(() => {
              fetchPreview(attempt + 1);
            }, delay);
            return;
          }

          // All retries exhausted or non-404 error
          setError({
            type: response.status === 404 ? 'not_available' : 'http_error',
            message: `HTTP ${response.status}: ${response.statusText}`,
            status: response.status
          });
          setImgUrl(null);
        } else {
          // Success
          setImgUrl(url);
          setError(null);
          setRetryCount(0);
        }
      } catch (err) {
        console.error("Failed to fetch detection preview:", err);
        setError({
          type: 'network_error',
          message: `Network error: ${err.message}`,
          hint: 'Check that the daemon is running and accessible'
        });
        setImgUrl(null);
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [lastResult?.timestamp, enabled]);

  if (!enabled) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Enable detection to see live preview with overlays</p>
      </div>
    );
  }

  // Handle different error states
  if (error?.type === "waiting" || error === "waiting") {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">Waiting for detection results...</p>
      </div>
    );
  }

  if (error?.type === "retrying" || error === "retrying") {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-blue-50 p-8 text-center">
        <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-2" />
        <p className="text-sm text-blue-700">Loading preview (attempt {retryCount}/5)...</p>
        <p className="text-xs text-blue-600 mt-1">
          {retryCount <= 2 ? 'Waiting for detection results...' :
           retryCount === 3 ? 'Still waiting - detection may be initializing...' :
           'Taking longer than expected - checking system...'}
        </p>
      </div>
    );
  }

  if (loading && !error) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <div className="w-8 h-8 border-4 border-gray-200 border-t-gray-600 rounded-full animate-spin mx-auto mb-2" />
        <p className="text-sm text-gray-500">Loading preview...</p>
      </div>
    );
  }

  // Display detailed error with actionable hints
  if (error && error !== "waiting") {
    const isNoMinimap = error.type === 'no_minimap' || error.type === 'not_available';
    const isNotStarted = error.message?.toLowerCase().includes('not started') ||
                         error.message?.toLowerCase().includes('not enabled');
    const isNetworkError = error.type === 'network_error';
    const isCaptureIssue = error.details?.capturing === false ||
                           error.message?.toLowerCase().includes('capture');

    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-red-50 p-6">
        <div className="text-center mb-3">
          <p className="text-sm font-medium text-red-600">
            {error.message || 'Failed to load detection preview'}
          </p>
        </div>

        {/* Actionable hints based on error type */}
        <div className="text-left space-y-2">
          {isNoMinimap && error.details?.active_config === null && (
            <p className="text-xs text-red-700 bg-red-100 p-2 rounded">
              → Go to <strong>Mini-Map</strong> tab to create and activate a region
            </p>
          )}

          {isNotStarted && (
            <p className="text-xs text-red-700 bg-red-100 p-2 rounded">
              → Click <strong>Start Detection</strong> button above
            </p>
          )}

          {isCaptureIssue && (
            <p className="text-xs text-red-700 bg-red-100 p-2 rounded">
              → Go to <strong>CV Capture</strong> tab to start video capture
            </p>
          )}

          {isNetworkError && error.hint && (
            <p className="text-xs text-red-700 bg-red-100 p-2 rounded">
              → {error.hint}
            </p>
          )}

          {/* Debug details (collapsible) */}
          {error.details && (
            <details className="text-xs">
              <summary className="cursor-pointer text-red-600 hover:text-red-800">
                Debug Info (click to expand)
              </summary>
              <pre className="mt-2 p-2 bg-red-100 rounded overflow-auto text-xs">
                {JSON.stringify({
                  type: error.type,
                  status: error.status,
                  details: error.details
                }, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    );
  }

  if (!imgUrl) {
    return (
      <div className="border border-gray-300 rounded overflow-hidden bg-gray-50 p-8 text-center">
        <p className="text-sm text-gray-500">No preview available</p>
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
