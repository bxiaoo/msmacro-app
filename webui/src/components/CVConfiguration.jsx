import { useState, useEffect, useRef } from 'react'
import { Camera, AlertCircle, CheckCircle, XCircle, Plus, Trash2, Minus, Download } from 'lucide-react'
import {
  getCVStatus,
  startCVCapture,
  listMapConfigs,
  createMapConfig,
  deleteMapConfig,
  activateMapConfig,
  deactivateMapConfig,
  getMiniMapPreviewURL,
  getCVScreenshotURL,
  saveCalibrationSample
} from '../api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Checkbox } from './ui/checkbox'
import { CalibrationGallery } from './CalibrationGallery'

export function CVConfiguration() {
  // CV status state
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [imageError, setImageError] = useState(false)
  const lastFrameLoggedRef = useRef(null)
  const lastErrorLoggedRef = useRef(null)

  // Map configuration state
  const [mapConfigs, setMapConfigs] = useState([])
  const [activeConfig, setActiveConfig] = useState(null)
  const [isCreating, setIsCreating] = useState(false)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [configName, setConfigName] = useState('')
  const [coords, setCoords] = useState({ tl_x: 68, tl_y: 56, width: 340, height: 86 })
  const [isTransitioning, setIsTransitioning] = useState(false)

  // Preview state - shows active minimap region only
  const [livePreviewUrl, setLivePreviewUrl] = useState(null)
  const [createPreviewUrl, setCreatePreviewUrl] = useState(null)
  const [fullScreenUrl, setFullScreenUrl] = useState(null)
  const [fullScreenError, setFullScreenError] = useState(false)
  const debounceTimerRef = useRef(null)

  // Calibration sample state
  const [sampleCount, setSampleCount] = useState(0)
  const [savingSample, setSavingSample] = useState(false)
  const [sampleMessage, setSampleMessage] = useState(null)

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

  // Load map configurations
  const loadMapConfigs = async () => {
    try {
      const data = await listMapConfigs()
      setMapConfigs(data.configs || [])
      const active = data.configs?.find(c => c.is_active)
      setActiveConfig(active || null)
    } catch (err) {
      console.error('Failed to load map configs:', err)
    }
  }

  const handleCreateConfig = () => {
    setIsCreating(true)
    setCoords({ tl_x: 68, tl_y: 56, width: 340, height: 86 })
    setConfigName('')
  }

  const handleCancelCreate = () => {
    setIsCreating(false)
    setConfigName('')
  }

  const handleSaveConfig = async () => {
    if (!configName.trim()) {
      alert('Please enter a configuration name')
      return
    }

    try {
      await createMapConfig(configName, coords.tl_x, coords.tl_y, coords.width, coords.height)
      await loadMapConfigs()
      setIsCreating(false)
      setShowSaveDialog(false)
      setConfigName('')
    } catch (err) {
      alert(`Failed to save configuration: ${err.message}`)
    }
  }

  const handleActivateConfig = async (config) => {
    try {
      setIsTransitioning(true)

      const wasActive = config.is_active
      if (wasActive) {
        await deactivateMapConfig()
      } else {
        await activateMapConfig(config.name)
      }
      await loadMapConfigs()

      // Poll until capture loop processes the config change
      // Expected: region_detected = true when activating, false when deactivating
      const expectedRegionDetected = !wasActive
      const maxAttempts = 10 // 10 attempts x 200ms = 2 seconds max
      let attempts = 0

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 200))

        try {
          const statusData = await getCVStatus()
          const currentRegionDetected = statusData?.frame?.region_detected || false

          if (currentRegionDetected === expectedRegionDetected) {
            // Capture loop has processed the change
            setStatus(statusData) // Update status with latest data
            break
          }
        } catch (err) {
          console.warn('Failed to poll status during transition:', err)
        }

        attempts++
      }

      if (attempts >= maxAttempts) {
        console.warn('Timeout waiting for region transition - continuing anyway')
      }

    } catch (err) {
      alert(`Failed to ${config.is_active ? 'deactivate' : 'activate'} configuration: ${err.message}`)
    } finally {
      setIsTransitioning(false)
    }
  }

  const handleDeleteConfig = async (configName) => {
    if (!confirm(`Delete configuration "${configName}"?`)) return

    try {
      await deleteMapConfig(configName)
      await loadMapConfigs()
    } catch (err) {
      alert(`Failed to delete configuration: ${err.message}`)
    }
  }

  const handleSaveCalibrationSample = async () => {
    setSavingSample(true)
    setSampleMessage(null)

    try {
      const result = await saveCalibrationSample()

      if (result.success) {
        setSampleCount(prev => prev + 1)
        setSampleMessage({
          type: 'success',
          text: `Sample ${result.filename} saved! (${result.resolution[0]}×${result.resolution[1]})`
        })

        // Clear success message after 3 seconds
        setTimeout(() => setSampleMessage(null), 3000)
      } else {
        setSampleMessage({
          type: 'error',
          text: result.message || 'Failed to save sample'
        })
      }
    } catch (err) {
      console.error('Failed to save calibration sample:', err)
      setSampleMessage({
        type: 'error',
        text: `Error: ${err.message}`
      })
    } finally {
      setSavingSample(false)
    }
  }

  const adjustCoord = (axis, delta) => {
    setCoords(prev => ({
      ...prev,
      [axis]: Math.max(1, prev[axis] + delta)
    }))
  }

  // Load map configs on mount
  useEffect(() => {
    loadMapConfigs()
  }, [])

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

  // Update create preview when coords change (debounced)
  useEffect(() => {
    if (isCreating) {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(() => {
        setCreatePreviewUrl(getMiniMapPreviewURL(coords.tl_x, coords.tl_y, coords.width, coords.height))
      }, 500)
    } else {
      setCreatePreviewUrl(null)
    }
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [coords, isCreating])

  // Update live preview for active config (every 2 seconds)
  useEffect(() => {
    if (activeConfig && status?.has_frame) {
      const updatePreview = () => {
        setLivePreviewUrl(`/api/cv/frame-lossless?t=${Date.now()}`)
        setImageError(false)
      }
      
      updatePreview()
      const interval = setInterval(updatePreview, 2000)
      return () => clearInterval(interval)
    } else {
      setLivePreviewUrl(null)
    }
  }, [activeConfig, status?.has_frame])

  // Update full-screen capture preview (every 2 seconds)
  useEffect(() => {
    if (status?.has_frame && status?.capturing) {
      const updateFullScreen = () => {
        setFullScreenUrl(getCVScreenshotURL())
        setFullScreenError(false)
      }
      
      updateFullScreen()
      const interval = setInterval(updateFullScreen, 2000)
      return () => clearInterval(interval)
    } else {
      setFullScreenUrl(null)
    }
  }, [status?.has_frame, status?.capturing])

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

  const renderEmptyState = () => (
    <div className="bg-gray-50 rounded-lg p-8 text-center">
      <Camera size={48} className="mx-auto mb-3 text-gray-400" />
      <p className="text-sm text-gray-700 mb-2">No saved mini-map configurations</p>
      <p className="text-xs text-gray-500 mb-4">
        CV detection is disabled. Create a config to enable mini-map detection.
      </p>
      <Button onClick={handleCreateConfig} variant="primary" size="sm">
        <Plus size={16} />
        Create Configuration
      </Button>
    </div>
  )

  const renderConfigList = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">Saved Configurations</h3>
        <Button onClick={handleCreateConfig} variant="primary" size="sm">
          <Plus size={16} />
          New
        </Button>
      </div>
      <div className="space-y-2">
        {mapConfigs.map((config) => (
          <div
            key={config.name}
            className="bg-gray-50 rounded-lg p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={config.is_active}
                  onChange={() => handleActivateConfig(config)}
                  disabled={isTransitioning}
                />
                <div>
                  <div className="text-sm font-medium text-gray-900">{config.name}</div>
                  <div className="text-xs text-gray-500">
                    Position: ({config.tl_x}, {config.tl_y}) · Size: {config.width}×{config.height}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={() => handleDeleteConfig(config.name)}
                  variant="ghost"
                  size="sm"
                  disabled={config.is_active || isTransitioning}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>

            {/* No inline preview - moved to top of list */}
          </div>
        ))}
      </div>
    </div>
  )

  const renderCreateForm = () => (
    <div className="bg-gray-50 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">Create Mini-Map Configuration</h3>
        <Button onClick={handleCancelCreate} variant="ghost" size="sm">
          Cancel
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Height (Vertical Size)</label>
          <div className="flex items-center gap-2">
            <Button onClick={() => adjustCoord('height', -10)} variant="default" size="sm">
              <Minus size={16} />
            </Button>
            <Input
              type="number"
              value={coords.height}
              onChange={(e) => setCoords({ ...coords, height: Math.max(1, parseInt(e.target.value) || 1) })}
              className="text-center"
            />
            <Button onClick={() => adjustCoord('height', 10)} variant="default" size="sm">
              <Plus size={16} />
            </Button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Width (Horizontal Size)</label>
          <div className="flex items-center gap-2">
            <Button onClick={() => adjustCoord('width', -10)} variant="default" size="sm">
              <Minus size={16} />
            </Button>
            <Input
              type="number"
              value={coords.width}
              onChange={(e) => setCoords({ ...coords, width: Math.max(1, parseInt(e.target.value) || 1) })}
              className="text-center"
            />
            <Button onClick={() => adjustCoord('width', 10)} variant="default" size="sm">
              <Plus size={16} />
            </Button>
          </div>
        </div>
      </div>

      {/* Real-time Preview */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Preview</h4>
        {createPreviewUrl ? (
          <div>
            <img
              key={createPreviewUrl}
              src={createPreviewUrl}
              alt="Mini-map preview"
              className="w-full h-auto rounded border border-gray-300"
              onError={() => {
                console.error('Failed to load mini-map preview')
              }}
            />
            <p className="text-xs text-gray-500 mt-2">
              Position: ({coords.tl_x}, {coords.tl_y}) · Size: {coords.width}×{coords.height}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <Camera size={32} className="mb-2" />
            <p className="text-sm">Loading preview...</p>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Button onClick={() => setShowSaveDialog(true)} variant="primary">
          Save Configuration
        </Button>
      </div>
    </div>
  )

  const renderSaveDialog = () => {
    if (!showSaveDialog) return null

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Save Configuration</h2>
          <Input
            type="text"
            placeholder="Configuration Name (e.g., Henesys Mini-Map)"
            value={configName}
            onChange={(e) => setConfigName(e.target.value)}
            className="mb-4"
          />
          <div className="flex gap-2 justify-end">
            <Button onClick={() => setShowSaveDialog(false)} variant="ghost">
              Cancel
            </Button>
            <Button onClick={handleSaveConfig} variant="primary">
              Save
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const renderMapConfigSection = () => {
    if (isCreating) {
      return renderCreateForm()
    }

    if (mapConfigs.length === 0) {
      return renderEmptyState()
    }

    return renderConfigList()
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

          {/*/!* Full-Screen Capture Preview *!/*/}
          {/*<div className="space-y-3">*/}
          {/*  <h2 className="text-lg font-semibold text-gray-900">Live Capture Preview</h2>*/}
          {/*  <div className="bg-gray-100 rounded-lg p-4">*/}
          {/*    {status?.has_frame && fullScreenUrl ? (*/}
          {/*      <div className="relative">*/}
          {/*        {fullScreenError ? (*/}
          {/*          <div className="flex flex-col items-center justify-center py-24 text-gray-400">*/}
          {/*            <AlertCircle size={48} className="mb-3 text-red-500" />*/}
          {/*            <p className="text-sm font-medium">Preview unavailable</p>*/}
          {/*            <p className="text-xs mt-1 text-gray-500">*/}
          {/*              Waiting for the next frame from the capture device…*/}
          {/*            </p>*/}
          {/*          </div>*/}
          {/*        ) : (*/}
          {/*          <>*/}
          {/*            <img*/}
          {/*              key={fullScreenUrl}*/}
          {/*              src={fullScreenUrl}*/}
          {/*              alt="Full Screen Capture"*/}
          {/*              className="w-full h-auto rounded border border-gray-300 shadow-sm"*/}
          {/*              style={{ maxWidth: '100%', margin: '0 auto', display: 'block' }}*/}
          {/*              onLoad={() => setFullScreenError(false)}*/}
          {/*              onError={() => {*/}
          {/*                console.error('Failed to load full screen preview')*/}
          {/*                setFullScreenError(true)*/}
          {/*              }}*/}
          {/*            />*/}
          {/*            <div className="mt-2 text-xs text-gray-500 text-center">*/}
          {/*              Updates every 2 seconds · Full capture: {status?.frame?.width || 1280}×{status?.frame?.height || 720}*/}
          {/*            </div>*/}
          {/*          </>*/}
          {/*        )}*/}
          {/*      </div>*/}
          {/*    ) : (*/}
          {/*      <div className="flex flex-col items-center justify-center py-24 text-gray-400">*/}
          {/*        <Camera size={64} className="mb-3 text-gray-300" />*/}
          {/*        <p className="text-sm font-medium">No frames captured yet</p>*/}
          {/*        <p className="text-xs mt-1 text-gray-500">*/}
          {/*          {status?.capturing ? 'Waiting for capture device…' : 'Start CV capture to see preview'}*/}
          {/*        </p>*/}
          {/*      </div>*/}
          {/*    )}*/}
          {/*  </div>*/}
          {/*</div>*/}

          {/* Map Configuration Section */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Mini-Map Configuration</h2>
            {renderMapConfigSection()}
          </div>

          {/* Device Info Grid (only when active config exists) */}
          {activeConfig && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderDeviceInfo()}
              {renderStats()}
            </div>
          )}

            {/* Live Minimap Preview (only when active config exists) */}
            {activeConfig && (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-gray-900">Live Minimap Preview</h2>
                        <div className="flex items-center gap-3">
                            {sampleCount > 0 && (
                                <span className="text-sm text-gray-600 bg-blue-50 px-3 py-1 rounded-full">
                                    Samples: {sampleCount}
                                </span>
                            )}
                            <Button
                                onClick={handleSaveCalibrationSample}
                                disabled={savingSample || !status?.has_frame}
                                className="flex items-center gap-2"
                            >
                                <Download size={16} />
                                {savingSample ? 'Saving...' : 'Save Sample'}
                            </Button>
                        </div>
                    </div>

                    {/* Sample save message */}
                    {sampleMessage && (
                        <div className={`p-3 rounded-lg text-sm ${
                            sampleMessage.type === 'success'
                                ? 'bg-green-50 text-green-800 border border-green-200'
                                : 'bg-red-50 text-red-800 border border-red-200'
                        }`}>
                            {sampleMessage.text}
                        </div>
                    )}

                    <div className="bg-gray-100 rounded-lg p-4">
                        {isTransitioning ? (
                            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                                <div className="w-12 h-12 border-4 border-gray-300 border-t-blue-600 rounded-full animate-spin mb-3" />
                                <p className="text-sm font-medium">Updating region...</p>
                                <p className="text-xs mt-1 text-gray-500">
                                    Waiting for capture loop to process the new configuration
                                </p>
                            </div>
                        ) : status?.has_frame && livePreviewUrl ? (
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
                                            key={livePreviewUrl}
                                            src={livePreviewUrl}
                                            alt="Live Minimap"
                                            className="w-full h-auto rounded border border-gray-300 shadow-sm"
                                            style={{ maxWidth: '800px', margin: '0 auto', display: 'block' }}
                                            onLoad={() => setImageError(false)}
                                            onError={() => {
                                                console.error('Failed to load live preview')
                                                setImageError(true)
                                            }}
                                        />
                                        <div className="mt-2 text-xs text-gray-500 text-center">
                                            Updates every 2 seconds · Active: {activeConfig.name} · {activeConfig.width}×{activeConfig.height}
                                        </div>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                                <Camera size={48} className="mb-3 text-gray-300" />
                                <p className="text-sm font-medium">No frames captured yet</p>
                                <p className="text-xs mt-1 text-gray-500">
                                    {status?.capturing ? 'Waiting for capture device…' : 'Start CV capture to see preview'}
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Calibration Sample Gallery */}
            {activeConfig && (
                <div className="space-y-3">
                    <h2 className="text-lg font-semibold text-gray-900">Calibration Samples</h2>
                    <div className="bg-gray-50 rounded-lg p-4">
                        <CalibrationGallery refreshTrigger={sampleCount} />
                    </div>
                </div>
            )}

        </div>
      </div>

      {/* Save Dialog Modal */}
      {renderSaveDialog()}
    </div>
  )
}
