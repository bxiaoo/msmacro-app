import { useState, useEffect } from 'react'
import { Target, Pencil, Trash2, ChevronDown } from 'lucide-react'
import { getDeparturePointsStatus, listFiles } from '../../api'
import { Button } from '../ui/button'
import { Input } from '../ui/input'

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
  mapConfigName,
  departurePoints,
  onDeparturePointsChange
}) {
  const [playerPosition, setPlayerPosition] = useState(null)
  const [playerDetected, setPlayerDetected] = useState(false)
  const [livePreviewUrl, setLivePreviewUrl] = useState(null)
  const [expandedPoint, setExpandedPoint] = useState(null)
  const [availableRotations, setAvailableRotations] = useState([])

  useEffect(() => {
    // Poll player position and update preview
    const interval = setInterval(async () => {
      try {
        const status = await getDeparturePointsStatus()
        setPlayerPosition(status.player_position)
        setPlayerDetected(status.player_detected || false)

        // Update live preview URL with cache busting
        if (mapConfigName) {
          setLivePreviewUrl(`/api/cv/frame-lossless?t=${Date.now()}`)
        }
      } catch (error) {
        console.error('Failed to get departure points status:', error)
      }
    }, 500)

    return () => clearInterval(interval)
  }, [mapConfigName])

  useEffect(() => {
    // Load available rotations
    listFiles().then(files => {
      setAvailableRotations(files)
    }).catch(error => {
      console.error('Failed to load rotations:', error)
    })
  }, [])

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

  const handleAddRotation = (pointIndex, rotationPath) => {
    const point = departurePoints[pointIndex]
    if (!point.rotation_paths.includes(rotationPath)) {
      handleUpdatePoint(pointIndex, {
        rotation_paths: [...point.rotation_paths, rotationPath]
      })
    }
  }

  const handleRemoveRotation = (pointIndex, rotationPath) => {
    const point = departurePoints[pointIndex]
    handleUpdatePoint(pointIndex, {
      rotation_paths: point.rotation_paths.filter(r => r !== rotationPath)
    })
  }

  return (
    <div className="flex flex-col gap-4 w-full">
      {/* Live Map Preview */}
      <div className="flex flex-col gap-2">
        <h3 className="font-semibold text-base text-gray-900">Live Map Preview</h3>
        <div className="bg-gray-100 rounded p-4 border border-gray-200">
          {livePreviewUrl ? (
            <img
              key={livePreviewUrl}
              src={livePreviewUrl}
              alt="Live minimap"
              className="w-full h-auto rounded"
              onError={() => console.error('Failed to load preview')}
            />
          ) : (
            <div className="flex items-center justify-center py-16 text-gray-400">
              <p className="text-sm">No preview available</p>
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

                        {/* Selected rotations */}
                        <div className="space-y-1">
                          {point.rotation_paths.map((rotation) => (
                            <div key={rotation} className="bg-gray-200 rounded overflow-hidden">
                              <div className="flex items-center p-1.5">
                                <div className="px-2.5 py-2">
                                  <div className="w-5 h-5 bg-gray-900 rounded flex items-center justify-center">
                                    <ChevronDown size={14} className="text-white" />
                                  </div>
                                </div>
                                <div className="flex-1 px-2">
                                  <p className="font-bold text-base text-gray-900">{rotation.replace('.json', '')}</p>
                                </div>
                                <button
                                  onClick={() => handleRemoveRotation(index, rotation)}
                                  className="p-2.5 hover:bg-gray-300 rounded-sm transition-colors"
                                  title="Remove"
                                >
                                  <Trash2 size={14} className="text-gray-900" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Add rotation */}
                        <select
                          onChange={(e) => {
                            if (e.target.value) {
                              handleAddRotation(index, e.target.value)
                              e.target.value = ''
                            }
                          }}
                          className="w-full bg-gray-100 border border-gray-300 rounded px-2 py-1.5 text-sm"
                        >
                          <option value="">Add rotation...</option>
                          {availableRotations.map((rot) => (
                            <option key={rot} value={rot}>{rot}</option>
                          ))}
                        </select>
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
