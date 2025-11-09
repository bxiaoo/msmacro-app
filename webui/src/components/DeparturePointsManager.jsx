import { useState, useEffect } from 'react'
import { MapPin, Plus, Trash2, GripVertical, Target } from 'lucide-react'
import {
  addDeparturePoint,
  removeDeparturePoint,
  updateDeparturePoint,
  getDeparturePointsStatus,
  getObjectDetectionStatus
} from '../api'
import { Button } from './ui/button'
import { Input } from './ui/input'

const TOLERANCE_MODES = [
  { value: 'both', label: 'Both X & Y ±', description: 'Player must be within tolerance in both directions' },
  { value: 'y_axis', label: 'Y-axis ±', description: 'Only check Y coordinate (horizontal line)' },
  { value: 'x_axis', label: 'X-axis ±', description: 'Only check X coordinate (vertical line)' },
  { value: 'y_greater', label: 'Y >', description: 'Y must be greater than saved value' },
  { value: 'y_less', label: 'Y <', description: 'Y must be less than saved value' },
  { value: 'x_greater', label: 'X >', description: 'X must be greater than saved value' },
  { value: 'x_less', label: 'X <', description: 'X must be less than saved value' },
]

export function DeparturePointsManager({ activeMapConfig }) {
  const [points, setPoints] = useState([])
  const [playerPosition, setPlayerPosition] = useState(null)
  const [playerDetected, setPlayerDetected] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load departure points and status
  const loadStatus = async () => {
    if (!activeMapConfig) return

    try {
      const statusData = await getDeparturePointsStatus()
      setPoints(statusData.points || [])
      setPlayerPosition(statusData.player_position)
      setPlayerDetected(statusData.player_detected || false)
      setError(null)
    } catch (err) {
      console.error('Failed to load departure points status:', err)
      setError(err.message)
    }
  }

  useEffect(() => {
    if (!activeMapConfig) {
      setPoints([])
      setPlayerPosition(null)
      setPlayerDetected(false)
      return
    }

    // Initial load
    loadStatus()

    // Poll status every 500ms for real-time updates
    const interval = setInterval(loadStatus, 500)

    return () => clearInterval(interval)
  }, [activeMapConfig])

  const handleCaptureCurrentPosition = async () => {
    if (!activeMapConfig || !playerDetected || !playerPosition) {
      alert('No player position detected. Please ensure object detection is running.')
      return
    }

    setLoading(true)
    try {
      const pointName = `Point ${points.length + 1}`
      await addDeparturePoint(
        activeMapConfig.name,
        playerPosition.x,
        playerPosition.y,
        pointName,
        'both',
        5
      )
      await loadStatus()
    } catch (err) {
      alert(`Failed to add departure point: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleRemovePoint = async (pointId) => {
    if (!activeMapConfig) return

    setLoading(true)
    try {
      await removeDeparturePoint(activeMapConfig.name, pointId)
      await loadStatus()
    } catch (err) {
      alert(`Failed to remove departure point: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdatePoint = async (pointId, updates) => {
    if (!activeMapConfig) return

    try {
      await updateDeparturePoint(activeMapConfig.name, pointId, updates)
      await loadStatus()
    } catch (err) {
      alert(`Failed to update departure point: ${err.message}`)
    }
  }

  if (!activeMapConfig) {
    return (
      <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
        <MapPin size={48} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm font-medium">No Active Map Configuration</p>
        <p className="text-xs mt-1">Create and activate a map configuration to add departure points</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with capture button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-md font-semibold text-gray-900">Departure Points</h3>
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
            {points.length} point{points.length !== 1 ? 's' : ''}
          </span>
        </div>
        <Button
          onClick={handleCaptureCurrentPosition}
          disabled={!playerDetected || loading}
          className="flex items-center gap-2"
          size="sm"
        >
          <Target size={16} />
          Capture Current Position
        </Button>
      </div>

      {/* Current player position indicator */}
      <div className={`p-3 rounded-lg text-sm border ${
        playerDetected
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-gray-50 border-gray-200 text-gray-600'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              playerDetected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
            }`} />
            <span className="font-medium">
              {playerDetected ? 'Player Detected' : 'Player Not Detected'}
            </span>
          </div>
          {playerDetected && playerPosition && (
            <span className="font-mono text-xs">
              ({playerPosition.x}, {playerPosition.y})
            </span>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          Failed to load departure points: {error}
        </div>
      )}

      {/* Points list */}
      {points.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500 border-2 border-dashed border-gray-300">
          <MapPin size={36} className="mx-auto mb-2 text-gray-300" />
          <p className="text-sm font-medium">No Departure Points</p>
          <p className="text-xs mt-1">
            Click "Capture Current Position" when the player is at a desired waypoint
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {points.map((point, index) => (
            <DeparturePointItem
              key={point.id}
              point={point}
              index={index}
              onRemove={() => handleRemovePoint(point.id)}
              onUpdate={(updates) => handleUpdatePoint(point.id, updates)}
              loading={loading}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function DeparturePointItem({ point, index, onRemove, onUpdate, loading }) {
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(point.name)
  const [editToleranceMode, setEditToleranceMode] = useState(point.tolerance_mode)
  const [editToleranceValue, setEditToleranceValue] = useState(point.tolerance_value)

  const handleSave = () => {
    onUpdate({
      name: editName,
      tolerance_mode: editToleranceMode,
      tolerance_value: parseInt(editToleranceValue, 10)
    })
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditName(point.name)
    setEditToleranceMode(point.tolerance_mode)
    setEditToleranceValue(point.tolerance_value)
    setIsEditing(false)
  }

  const toleranceMode = TOLERANCE_MODES.find(m => m.value === point.tolerance_mode)

  return (
    <div className={`p-4 rounded-lg border-2 transition-all ${
      point.hit_departure
        ? 'bg-green-50 border-green-400 shadow-md'
        : 'bg-white border-gray-200'
    }`}>
      <div className="flex items-start gap-3">
        {/* Order badge */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
          point.hit_departure
            ? 'bg-green-500 text-white'
            : 'bg-gray-100 text-gray-600'
        }`}>
          {index + 1}
        </div>

        {/* Content */}
        <div className="flex-1 space-y-2">
          {isEditing ? (
            <>
              {/* Edit mode */}
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="Point name"
                className="text-sm"
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-gray-600 block mb-1">Tolerance Mode</label>
                  <select
                    value={editToleranceMode}
                    onChange={(e) => setEditToleranceMode(e.target.value)}
                    className="w-full text-sm border border-gray-300 rounded px-2 py-1"
                  >
                    {TOLERANCE_MODES.map(mode => (
                      <option key={mode.value} value={mode.value}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {TOLERANCE_MODES.find(m => m.value === editToleranceMode)?.description}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-gray-600 block mb-1">Tolerance (px)</label>
                  <Input
                    type="number"
                    value={editToleranceValue}
                    onChange={(e) => setEditToleranceValue(e.target.value)}
                    min="1"
                    max="50"
                    className="text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleSave} size="sm" className="flex-1">
                  Save
                </Button>
                <Button onClick={handleCancel} size="sm" variant="outline" className="flex-1">
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              {/* View mode */}
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{point.name}</span>
                {point.hit_departure && (
                  <span className="text-xs bg-green-500 text-white px-2 py-1 rounded-full font-semibold animate-pulse">
                    HIT!
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                <div>
                  <span className="text-gray-500">Position:</span>{' '}
                  <span className="font-mono">({point.x}, {point.y})</span>
                </div>
                <div>
                  <span className="text-gray-500">Mode:</span>{' '}
                  <span>{toleranceMode?.label}</span>
                </div>
                <div>
                  <span className="text-gray-500">Tolerance:</span>{' '}
                  <span>{point.tolerance_value}px</span>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={() => setIsEditing(true)}
                  size="sm"
                  variant="outline"
                  className="flex-1 text-xs"
                  disabled={loading}
                >
                  Edit
                </Button>
                <Button
                  onClick={onRemove}
                  size="sm"
                  variant="outline"
                  className="flex items-center gap-1 text-xs text-red-600 hover:bg-red-50"
                  disabled={loading}
                >
                  <Trash2 size={14} />
                  Remove
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
