import { useState, useEffect, useRef } from 'react'
import { Camera, AlertCircle, CheckCircle, XCircle, Plus, Trash2, Minus } from 'lucide-react'
import {
  getCVStatus,
  getCVScreenshotURL,
  startCVCapture,
  listMapConfigs,
  createMapConfig,
  deleteMapConfig,
  activateMapConfig,
  deactivateMapConfig
} from '../api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Checkbox } from './ui/checkbox'

export function CVConfiguration() {
  // CV status state
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [imageError, setImageError] = useState(false)
  const lastFrameLoggedRef = useRef(null)
  const lastErrorLoggedRef = useRef(null)

  // Map configuration state
  const [mapConfigs, setMapConfigs] = useState([])
  const [activeConfig, setActiveConfig] = useState(null)
  const [isCreating, setIsCreating] = useState(false)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [configName, setConfigName] = useState('')
  const [coords, setCoords] = useState({ x: 68, y: 56, width: 340, height: 86 })

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
    setCoords({ x: 68, y: 56, width: 340, height: 86 })
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
      await createMapConfig(configName, coords.x, coords.y, coords.width, coords.height)
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
      if (config.is_active) {
        await deactivateMapConfig()
      } else {
        await activateMapConfig(config.name)
      }
      await loadMapConfigs()
    } catch (err) {
      alert(`Failed to ${config.is_active ? 'deactivate' : 'activate'} configuration: ${err.message}`)
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

  const adjustCoord = (axis, delta) => {
    setCoords(prev => ({
      ...prev,
      [axis]: Math.max(0, prev[axis] + delta)
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
            className="bg-gray-50 rounded-lg p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <Checkbox
                checked={config.is_active}
                onChange={() => handleActivateConfig(config)}
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
                disabled={config.is_active}
              >
                <Trash2 size={16} />
              </Button>
            </div>
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

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Y Axis (Vertical)</label>
          <div className="flex items-center gap-2">
            <Button onClick={() => adjustCoord('y', -10)} variant="default" size="sm">
              <Minus size={16} />
            </Button>
            <Input
              type="number"
              value={coords.y}
              onChange={(e) => setCoords({ ...coords, y: parseInt(e.target.value) || 0 })}
              className="text-center"
            />
            <Button onClick={() => adjustCoord('y', 10)} variant="default" size="sm">
              <Plus size={16} />
            </Button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">X Axis (Horizontal)</label>
          <div className="flex items-center gap-2">
            <Button onClick={() => adjustCoord('x', -10)} variant="default" size="sm">
              <Minus size={16} />
            </Button>
            <Input
              type="number"
              value={coords.x}
              onChange={(e) => setCoords({ ...coords, x: parseInt(e.target.value) || 0 })}
              className="text-center"
            />
            <Button onClick={() => adjustCoord('x', 10)} variant="default" size="sm">
              <Plus size={16} />
            </Button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <p className="text-xs text-gray-500">
          Size: {coords.width}×{coords.height} (default for mini-maps)
        </p>
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

          {/* Map Configuration Section */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Mini-Map Configuration</h2>
            {renderMapConfigSection()}
          </div>

          {/* Screenshot Preview (only when active config exists) */}
          {activeConfig && (
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
                          Updates every 2 seconds · Active: {activeConfig.name}
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
          )}

          {/* Device Info Grid (only when active config exists) */}
          {activeConfig && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {renderDeviceInfo()}
              {renderStats()}
            </div>
          )}

        </div>
      </div>

      {/* Save Dialog Modal */}
      {renderSaveDialog()}
    </div>
  )
}
