import { useState, useEffect } from 'react'
import { Target, Pencil, Trash2 } from 'lucide-react'
import { getDeparturePointsStatus, getCVStatus, startCVCapture, activateMapConfig, activateCVItem, getObjectDetectionStatus, startObjectDetection, listMapConfigs } from '../../api'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { RotationSelector } from '../shared/RotationSelector'

const TOLERANCE_MODES = [
  { value: 'both', label: 'Both X & Y ±' },
  { value: 'y_axis', label: 'Y-axis ±' },
  { value: 'x_axis', label: 'X-axis ±' },
  { value: 'y_greater', label: 'Y >' },
  { value: 'y_less', label: 'Y <' },
  { value: 'x_greater', label: 'X >' },
  { value: 'x_less', label: 'X <' },
]

export function CVItemDepartureStep({
  cvItemName,
  mapConfigName,
  departurePoints,
  onDeparturePointsChange
}) {
  const [playerPosition, setPlayerPosition] = useState(null)
  const [playerDetected, setPlayerDetected] = useState(false)
  const [livePreviewUrl, setLivePreviewUrl] = useState(null)
  const [expandedPoint, setExpandedPoint] = useState(null)
  const [mapConfig, setMapConfig] = useState(null)
  const [initStatus, setInitStatus] = useState({
    cvReady: false,
    mapActive: false,
    odReady: false,
    error: null,
    initializing: true
  })

  // Load map config for aspect ratio calculation
  useEffect(() => {
    const loadMapConfig = async () => {
      if (!mapConfigName) return
      try {
        const data = await listMapConfigs()
        const configs = Array.isArray(data) ? data : data.configs || []
        const config = configs.find(c => c.name === mapConfigName)
        setMapConfig(config)
      } catch (error) {
        console.error('Failed to load map config:', error)
      }
    }
    loadMapConfig()
  }, [mapConfigName])

  // Initialize by activating the full CV item
  useEffect(() => {
    // ALWAYS log, even if cvItemName is undefined
    console.log('='.repeat(70))
    console.log('[CVItemDepartureStep] useEffect TRIGGERED')
    console.log('[CVItemDepartureStep] cvItemName:', cvItemName)
    console.log('[CVItemDepartureStep] cvItemName type:', typeof cvItemName)
    console.log('[CVItemDepartureStep] cvItemName is truthy:', !!cvItemName)
    console.log('='.repeat(70))

    const initializeStep = async () => {
      try {
        console.log('📹 [CVItemDepartureStep] Initializing with CV item:', cvItemName)
        setInitStatus(prev => ({ ...prev, initializing: true, error: null }))

        // Activate the full CV item
        // This handles: CV capture start, map config activation, reload, OD start
        if (cvItemName) {
          await activateCVItem(cvItemName)
          console.log('✅ [CVItemDepartureStep] CV item activated:', cvItemName)

          // Mark all systems as ready since activateCVItem handles everything
          setInitStatus({
            cvReady: true,
            mapActive: true,
            odReady: true,
            error: null,
            initializing: false
          })

          console.log('✅ [CVItemDepartureStep] Initialization complete')
        } else {
          console.warn('⚠️ [CVItemDepartureStep] No CV item name provided')
          setInitStatus(prev => ({
            ...prev,
            initializing: false,
            error: 'No CV item name provided'
          }))
        }

      } catch (error) {
        console.error('❌ [CVItemDepartureStep] Activation failed:', error)
        setInitStatus(prev => ({
          ...prev,
          initializing: false,
          error: error.message || 'Activation failed'
        }))
      }
    }

    initializeStep()
  }, [cvItemName])

  // Poll player position and update preview (only when initialized)
  useEffect(() => {
    // Don't start polling until initialization is complete
    if (initStatus.initializing || initStatus.error || !initStatus.cvReady || !initStatus.odReady) {
      console.log('⏳ [CVItemDepartureStep] Waiting for initialization...', initStatus)
      return
    }

    console.log('🔄 [CVItemDepartureStep] Starting polling loop')

    const interval = setInterval(async () => {
      try {
        const status = await getDeparturePointsStatus()
        setPlayerPosition(status.player_position)
        setPlayerDetected(status.player_detected || false)

        // Update live preview URL with cache busting
        if (mapConfigName) {
          setLivePreviewUrl(`/api/cv/detection-preview?t=${Date.now()}`)
        }
      } catch (error) {
        console.error('Failed to get departure points status:', error)
      }
    }, 500)

    return () => {
      console.log('🛑 [CVItemDepartureStep] Stopping polling loop')
      clearInterval(interval)
    }
  }, [mapConfigName, initStatus])

  const handleCapture = () => {
    if (!playerDetected || !playerPosition) {
      alert('No player position detected')
      return
    }

    const newPoint = {
      id: `point-${Date.now()}`,
      name: `Point ${departurePoints.length + 1}`,
      x: playerPosition.x,
      y: playerPosition.y,
      order: departurePoints.length,
      tolerance_mode: 'y_axis',
      tolerance_value: 3,
      rotation_paths: [],
      rotation_mode: 'random',
      is_teleport_point: false,
      auto_play: true,
      pathfinding_sequence: null,
      created_at: Date.now() / 1000
    }

    onDeparturePointsChange([...departurePoints, newPoint])
  }

  const handleUpdatePoint = (index, updates) => {
    const newPoints = [...departurePoints]
    newPoints[index] = { ...newPoints[index], ...updates }
    onDeparturePointsChange(newPoints)
  }

  const handleDeletePoint = (index) => {
    onDeparturePointsChange(departurePoints.filter((_, i) => i !== index))
  }

  return (
    <div className="flex flex-col gap-4 w-full">
      {/* Initialization Status Banner */}
      {initStatus.initializing && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-blue-800 font-semibold text-sm">🔄 Initializing step 2...</p>
          <div className="mt-2 space-y-1 text-xs text-blue-700">
            <p>✓ CV Capture: {initStatus.cvReady ? 'Ready' : 'Starting...'}</p>
            <p>✓ Map Config: {initStatus.mapActive ? 'Activated' : 'Activating...'}</p>
            <p>✓ Object Detection: {initStatus.odReady ? 'Ready' : 'Starting...'}</p>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {initStatus.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 font-semibold text-sm">❌ Initialization failed</p>
          <p className="text-red-700 text-xs mt-1">{initStatus.error}</p>
          <p className="text-red-600 text-xs mt-2">
            Please check that the daemon is running and the camera is connected.
          </p>
        </div>
      )}

      {/* Live Map Preview */}
      <div className="flex flex-col gap-2">
        <h3 className="font-semibold text-base text-gray-900">Live Map Preview</h3>
        <div className="bg-gray-100 rounded p-4 border border-gray-200">
          {livePreviewUrl && !initStatus.initializing && !initStatus.error ? (
            mapConfig ? (
              <div
                className="relative w-full rounded overflow-hidden"
                style={{ paddingBottom: `${(mapConfig.height / mapConfig.width) * 100}%` }}
              >
                <img
                  key={livePreviewUrl}
                  src={livePreviewUrl}
                  alt="Live minimap"
                  className="absolute top-0 left-0 w-full h-full object-cover"
                  onError={() => console.error('Failed to load preview')}
                />
              </div>
            ) : (
              <img
                key={livePreviewUrl}
                src={livePreviewUrl}
                alt="Live minimap"
                className="w-full h-auto rounded"
                onError={() => console.error('Failed to load preview')}
              />
            )
          ) : (
            <div className="flex items-center justify-center py-16 text-gray-400">
              <p className="text-sm">
                {initStatus.initializing ? 'Initializing...' :
                 initStatus.error ? 'Preview unavailable' :
                 'No preview available'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Player Position Badge */}
      {playerDetected && playerPosition && (
        <div className="bg-emerald-200 border border-emerald-300 rounded px-3 py-2">
          <span className="font-semibold text-sm text-emerald-900">
            Player current position ({playerPosition.x}, {playerPosition.y})
          </span>
        </div>
      )}

      {/* Capture Button */}
      <button
        onClick={handleCapture}
        disabled={!playerDetected}
        className={`w-full bg-gray-900 text-white rounded h-11 flex items-center justify-center gap-2 font-medium ${
          playerDetected ? 'hover:bg-gray-800' : 'opacity-50 cursor-not-allowed'
        }`}
      >
        <Target size={20} />
        Capture new departure point
      </button>

      {/* Departure Points List */}
      <div className="flex flex-col gap-2">
        <h3 className="font-bold text-base text-gray-900">
          Departure list ({departurePoints.length})
        </h3>

        {departurePoints.length === 0 ? (
          <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500 border-2 border-dashed border-gray-300">
            <p className="text-sm">No departure points</p>
            <p className="text-xs mt-1">Click "Capture" when player is at desired waypoint</p>
          </div>
        ) : (
          <div className="space-y-2">
            {departurePoints.map((point, index) => {
              const isExpanded = expandedPoint === index
              const toleranceMode = TOLERANCE_MODES.find(m => m.value === point.tolerance_mode)

              return (
                <div
                  key={point.id}
                  className="bg-white border-2 border-gray-300 rounded-lg p-3"
                >
                  {/* Collapsed view */}
                  {!isExpanded ? (
                    <div className="flex items-center gap-2">
                      {/* Index */}
                      <div className="bg-gray-100 rounded-full w-6 h-6 flex items-center justify-center font-bold text-sm text-gray-900 shrink-0">
                        {index + 1}
                      </div>

                      {/* Info */}
                      <div className="flex-1">
                        <div className="flex gap-1 items-baseline">
                          <p className="font-bold text-base text-gray-900">{point.name}</p>
                          <p className="font-semibold text-xs text-gray-600">
                            ({point.x}, {point.y})
                          </p>
                        </div>
                        <div className="flex gap-4 text-xs text-gray-500">
                          <span>Mode {toleranceMode?.label}</span>
                          <span>Tolerance {point.tolerance_value}px</span>
                        </div>
                      </div>

                      {/* Actions */}
                      <button
                        onClick={() => setExpandedPoint(index)}
                        className="p-2.5 hover:bg-gray-100 rounded-sm transition-colors"
                        title="Edit"
                      >
                        <Pencil size={20} className="text-gray-900" />
                      </button>
                      <button
                        onClick={() => handleDeletePoint(index)}
                        className="p-2.5 hover:bg-gray-100 rounded-sm transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={20} className="text-gray-900" />
                      </button>
                    </div>
                  ) : (
                    /* Expanded view */
                    <div className="flex flex-col gap-3">
                      {/* Header with index and name */}
                      <div className="flex items-center gap-3">
                        <div className="bg-gray-100 rounded-full w-7 h-7 flex items-center justify-center font-bold text-sm text-gray-900">
                          {index + 1}
                        </div>
                        <div className="flex gap-1 items-baseline">
                          <p className="font-bold text-base text-gray-900">{point.name}</p>
                          <p className="font-semibold text-xs text-gray-700">
                            ({point.x}, {point.y})
                          </p>
                        </div>
                      </div>

                      {/* Hit mode */}
                      <div className="flex flex-col gap-2">
                        <label className="text-sm text-gray-900">Hit Mode</label>
                        <select
                          value={point.tolerance_mode}
                          onChange={(e) => handleUpdatePoint(index, { tolerance_mode: e.target.value })}
                          className="w-full bg-gray-100 border border-gray-300 rounded px-3 py-2 text-base"
                        >
                          {TOLERANCE_MODES.map((mode) => (
                            <option key={mode.value} value={mode.value}>
                              {mode.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Tolerance */}
                      <div className="flex flex-col gap-2">
                        <label className="text-sm text-gray-900">Tolerance</label>
                        <Input
                          type="number"
                          value={point.tolerance_value}
                          onChange={(e) => handleUpdatePoint(index, { tolerance_value: parseInt(e.target.value) || 0 })}
                          className="w-full"
                        />
                      </div>

                      {/* Linked rotations */}
                      <div className="flex flex-col gap-2">
                        <label className="text-sm text-gray-900">Linked rotations</label>
                        <RotationSelector
                          selectedRotations={point.rotation_paths || []}
                          onChange={(newRotations) => handleUpdatePoint(index, { rotation_paths: newRotations })}
                        />
                      </div>

                      {/* Save/Cancel buttons */}
                      <div className="flex gap-2 pt-2">
                        <Button
                          onClick={() => setExpandedPoint(null)}
                          className="flex-1"
                        >
                          Save
                        </Button>
                        <Button
                          onClick={() => setExpandedPoint(null)}
                          variant="outline"
                          className="flex-1"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
