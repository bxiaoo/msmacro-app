import { useState, useEffect, useRef } from 'react'
import { Camera, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import { getCVStatus, getCVScreenshotURL, startCVCapture } from '../api'

export function CVConfiguration() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [imageError, setImageError] = useState(false)
  const lastFrameLoggedRef = useRef(null)
  const lastErrorLoggedRef = useRef(null)

  const formatTimestamp = (ts) => {
    if (ts === null || ts === undefined) return '—'
    const value = Number(ts)
    if (!Number.isFinite(value)) return String(ts)
    try {
      return new Date(value * 1000).toLocaleString()
    } catch {
      return String(ts)
    }
  }

  // Auto-start capture on mount
  useEffect(() => {
    const initCapture = async () => {
      try {
        // Try to start capture (will fail gracefully if no device)
        await startCVCapture()
      } catch (err) {
        console.log('CV capture start failed (may be expected):', err)
      }
    }
    initCapture()
  }, [])

  // Poll status and refresh screenshot every 2 seconds
  useEffect(() => {
    const pollStatus = async () => {
      try {
        const data = await getCVStatus()
        setStatus(data)
        setError(null)
        setLoading(false)

        if (data.frame && data.frame.timestamp !== lastFrameLoggedRef.current) {
          console.debug('CV frame metadata:', data.frame)
          lastFrameLoggedRef.current = data.frame.timestamp
        }

        if (data.last_error) {
          const signature = `${data.last_error.message ?? ''}|${data.last_error.timestamp ?? ''}`
          if (signature !== lastErrorLoggedRef.current) {
            console.warn('CV capture error:', data.last_error)
            lastErrorLoggedRef.current = signature
          }
        } else if (lastErrorLoggedRef.current) {
          console.info('CV capture recovered')
          lastErrorLoggedRef.current = null
        }

        // Refresh screenshot if we have frames
        if (data.has_frame) {
          setPreviewUrl(getCVScreenshotURL())
          setImageError(false)
        } else {
          setPreviewUrl(null)
        }
      } catch (err) {
        setError(err.message || 'Failed to get CV status')
        setLoading(false)
      }
    }

    // Initial poll
    pollStatus()

    // Poll every 2 seconds
    const interval = setInterval(pollStatus, 2000)

    return () => clearInterval(interval)
  }, [])

  const renderStatusBadge = () => {
    if (loading) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full">
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" />
          <span className="text-sm text-gray-600">Loading...</span>
        </div>
      )
    }

    if (!status?.connected) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-full">
          <XCircle size={16} className="text-red-600" />
          <span className="text-sm text-red-700">Device Disconnected</span>
        </div>
      )
    }

    if (!status?.capturing) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-100 rounded-full">
          <AlertCircle size={16} className="text-yellow-600" />
          <span className="text-sm text-yellow-700">Not Capturing</span>
        </div>
      )
    }

    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-green-100 rounded-full">
        <CheckCircle size={16} className="text-green-600" />
        <span className="text-sm text-green-700">Connected</span>
      </div>
    )
  }

  const renderDeviceInfo = () => {
    if (!status?.device) return null

    return (
      <div className="bg-gray-50 rounded-lg p-4 space-y-2">
        <h3 className="text-sm font-medium text-gray-700">Device Information</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="text-gray-600">Name:</div>
          <div className="text-gray-900 font-mono">{status.device.name || 'Unknown'}</div>

          <div className="text-gray-600">Path:</div>
          <div className="text-gray-900 font-mono">{status.device.path}</div>

          {status.capture && (
            <>
              <div className="text-gray-600">Resolution:</div>
              <div className="text-gray-900 font-mono">
                {status.capture.width} x {status.capture.height}
              </div>

              <div className="text-gray-600">FPS:</div>
              <div className="text-gray-900 font-mono">{status.capture.fps.toFixed(1)}</div>
            </>
          )}
        </div>
      </div>
    )
  }

  const renderStats = () => {
    if (!status) return null

    return (
      <div className="bg-gray-50 rounded-lg p-4 space-y-2">
        <h3 className="text-sm font-medium text-gray-700">Capture Statistics</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="text-gray-600">Frames Captured:</div>
          <div className="text-gray-900 font-mono">{status.frames_captured || 0}</div>

          <div className="text-gray-600">Frames Failed:</div>
          <div className="text-gray-900 font-mono">{status.frames_failed || 0}</div>

          {status.frame && (
            <>
              <div className="text-gray-600">Resolution:</div>
              <div className="text-gray-900 font-mono">
                {status.frame.width} × {status.frame.height}
              </div>

              <div className="text-gray-600">Captured At:</div>
              <div className="text-gray-900 font-mono">
                {formatTimestamp(status.frame.timestamp)}
              </div>

              <div className="text-gray-600">Frame Age:</div>
              <div className="text-gray-900 font-mono">
                {status.frame.age_seconds.toFixed(1)}s
              </div>

              <div className="text-gray-600">Frame Size:</div>
              <div className="text-gray-900 font-mono">
                {(status.frame.size_bytes / 1024).toFixed(1)} KB
              </div>
            </>
          )}
        </div>
        <div className="pt-3 mt-3 border-t border-gray-200">
          {status.last_error ? (
            <div>
              <p className="text-sm font-medium text-red-600">Last Capture Error</p>
              <p className="text-xs text-red-500 mt-1">{status.last_error.message}</p>
              <p className="text-xs text-gray-500 mt-1">
                {status.last_error.timestamp ? formatTimestamp(status.last_error.timestamp) : 'Timestamp unavailable'}
                {status.last_error.detail ? ` · ${status.last_error.detail}` : ''}
              </p>
            </div>
          ) : (
            <p className="text-xs text-gray-500">No recent capture errors.</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <Camera size={24} className="text-gray-700" />
          <h1 className="text-xl font-semibold text-gray-900">CV Configuration</h1>
        </div>
        {renderStatusBadge()}
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle size={20} className="text-red-600 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-medium text-red-800">Error</h3>
                  <p className="text-sm text-red-700 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Screenshot Preview */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Live Preview</h2>
            <div className="bg-gray-100 rounded-lg p-4">
              {status?.has_frame && previewUrl ? (
                <div className="relative">
                  {imageError ? (
                    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                      <AlertCircle size={36} className="mb-2 text-red-500" />
                      <p className="text-sm">Preview unavailable</p>
                      <p className="text-xs mt-1 text-gray-500">
                        Waiting for the next frame from the capture device…
                      </p>
                    </div>
                  ) : (
                    <>
                      <img
                        key={previewUrl}
                        src={previewUrl}
                        alt="Captured Screenshot"
                        className="w-full h-auto rounded border border-gray-300 shadow-sm"
                        onLoad={() => setImageError(false)}
                        onError={() => {
                          console.error('Failed to load screenshot')
                          setImageError(true)
                        }}
                      />
                      <div className="mt-2 text-xs text-gray-500 text-center">
                        Updates every 2 seconds
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <Camera size={48} className="mb-3" />
                  <p className="text-sm">No frame available</p>
                  <p className="text-xs mt-1">
                    {status?.connected
                      ? 'Waiting for capture to start...'
                      : 'Connect an HDMI capture device'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Device Info Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renderDeviceInfo()}
            {renderStats()}
          </div>

          {/* Future CV Features Notice */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="text-blue-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-medium text-blue-800">Future CV Automation</h3>
                <p className="text-sm text-blue-700 mt-1">
                  This tab currently shows the captured screen for verification. Future updates will add:
                </p>
                <ul className="text-sm text-blue-700 mt-2 ml-4 list-disc space-y-1">
                  <li>Template matching for screen state detection</li>
                  <li>OCR for text-based triggers</li>
                  <li>Color/shape detection</li>
                  <li>CV-based conditional macro execution</li>
                </ul>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
