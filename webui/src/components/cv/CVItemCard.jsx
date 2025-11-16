import { useState, useEffect } from 'react'
import { Pencil, Trash2, Menu } from 'lucide-react'
import { Checkbox } from '../ui/checkbox'
import { getDeparturePointsStatus } from '../../api'

export function CVItemCard({ item, isActive, onActivate, onEdit, onDelete, showDeparturePoints }) {
  const [playerPosition, setPlayerPosition] = useState(null)
  const [livePreviewUrl, setLivePreviewUrl] = useState(null)

  // Poll player position when active
  useEffect(() => {
    if (!isActive || !showDeparturePoints) return

    const interval = setInterval(async () => {
      try {
        const status = await getDeparturePointsStatus()
        setPlayerPosition(status.player_position)
        setLivePreviewUrl(`/api/cv/frame-lossless?t=${Date.now()}`)
      } catch (error) {
        console.error('Failed to get status:', error)
      }
    }, 500)

    return () => clearInterval(interval)
  }, [isActive, showDeparturePoints])

  const handleActivateToggle = () => {
    onActivate(item.name)
  }

  const handleEdit = () => {
    onEdit(item)
  }

  const handleDelete = () => {
    if (confirm(`Delete CV Item "${item.name}"?`)) {
      onDelete(item.name)
    }
  }

  const departurePoints = item.departure_points || []

  return (
    <div className="bg-gray-200 rounded overflow-hidden">
      {/* Header */}
      <div className="flex items-center p-1.5">
        {/* Checkbox */}
        <div className="px-2.5 py-2">
          <Checkbox
            checked={isActive}
            onChange={handleActivateToggle}
          />
        </div>

        {/* CV Item Name */}
        <div className="flex-1 flex items-center gap-1">
          <p className="font-bold text-base text-gray-900">
            {item.name}
          </p>
        </div>

        {/* Edit Button */}
        <button
          onClick={handleEdit}
          className="p-2.5 hover:bg-gray-300 rounded-sm transition-colors"
          title="Edit"
        >
          <Pencil size={20} className="text-gray-900" />
        </button>

        {/* Delete Button */}
        <button
          onClick={handleDelete}
          className="p-2.5 hover:bg-gray-300 rounded-sm transition-colors"
          title="Delete"
          disabled={isActive}
        >
          <Trash2 size={20} className={isActive ? 'text-gray-400' : 'text-gray-900'} />
        </button>

        {/* Drag Handle */}
        <div className="px-2.5 py-0 pr-0">
          <Menu size={14} className="text-gray-600" />
        </div>
      </div>

      {/* Expanded View: Departure Points (when active and enabled) */}
      {isActive && showDeparturePoints && departurePoints.length > 0 && (
        <div className="bg-white border-t-2 border-gray-300 p-3 space-y-3">
          {/* Player Position Badge */}
          {playerPosition && (
            <div className="bg-emerald-200 border border-emerald-300 rounded px-3 py-2 text-sm">
              <span className="font-semibold text-emerald-900">
                Player current position ({playerPosition.x}, {playerPosition.y})
              </span>
            </div>
          )}

          {/* Departure Points List */}
          <div className="space-y-2">
            {departurePoints.map((point, index) => (
              <div
                key={point.id || index}
                className="bg-white border-2 border-gray-300 rounded p-2.5 flex items-center gap-2"
              >
                <div className="bg-gray-100 rounded-full w-6 h-6 flex items-center justify-center font-bold text-sm text-gray-900 shrink-0">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <p className="font-bold text-sm text-gray-900">
                    {point.name || `Point ${index + 1}`} <span className="font-normal text-xs text-gray-600">({point.x}, {point.y})</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    Mode {point.tolerance_mode || 'both'} &nbsp; Tolerance {point.tolerance_value || 3}px
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Live Map Preview */}
          {livePreviewUrl && (
            <div className="border-2 border-gray-300 rounded overflow-hidden">
              <img
                key={livePreviewUrl}
                src={livePreviewUrl}
                alt="Live minimap"
                className="w-full h-auto"
                onError={() => console.error('Failed to load preview')}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
