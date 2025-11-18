import { useState, useEffect } from 'react'
import { getStatus } from '../../api'
import { buildTree, flattenFiles } from '../../hooks/useFileTree'
import { Checkbox } from '../ui/checkbox'

/**
 * Reusable rotation selector component with checkbox-based multi-selection
 * @param {string[]} selectedRotations - Array of selected rotation file names
 * @param {function} onChange - Callback when selection changes: (newSelection: string[]) => void
 * @param {boolean} showActions - Whether to show edit/delete actions (default: false)
 */
export function RotationSelector({
  selectedRotations = [],
  onChange,
  showActions = false
}) {
  const [availableRotations, setAvailableRotations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Load available rotations on mount
  useEffect(() => {
    const loadRotations = async () => {
      try {
        setLoading(true)
        setError(null)
        // Use getStatus() API like the Rotations tab does
        const st = await getStatus()
        const items = Array.isArray(st?.tree) ? st.tree : []

        // Build tree and flatten files exactly like MacroList does
        const tree = buildTree(items)
        const allFiles = flattenFiles(tree)
        const files = allFiles.map(f => f.rel)

        setAvailableRotations(files)
      } catch (err) {
        console.error('[RotationSelector] Failed to load rotations:', err)
        setError(err.message || 'Failed to load rotations')
        setAvailableRotations([])
      } finally {
        setLoading(false)
      }
    }

    loadRotations()
  }, [])

  const handleToggle = (rotationPath) => {
    const currentSelection = Array.isArray(selectedRotations) ? selectedRotations : []

    if (currentSelection.includes(rotationPath)) {
      // Remove from selection
      onChange(currentSelection.filter(r => r !== rotationPath))
    } else {
      // Add to selection
      onChange([...currentSelection, rotationPath])
    }
  }

  if (loading) {
    return (
      <div className="bg-gray-50 rounded p-4 text-center text-gray-500 text-sm">
        Loading rotations...
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4 text-center">
        <p className="text-red-800 font-semibold text-sm">Failed to load rotations</p>
        <p className="text-red-600 text-xs mt-1">{error}</p>
      </div>
    )
  }

  if (availableRotations.length === 0) {
    return (
      <div className="bg-gray-50 rounded p-4 text-center text-gray-500 text-sm">
        No rotations available
      </div>
    )
  }

  const safeSelectedRotations = Array.isArray(selectedRotations) ? selectedRotations : []

  return (
    <div className="space-y-1">
      {availableRotations.map((rotation) => {
        const isChecked = safeSelectedRotations.includes(rotation)
        const displayName = rotation.replace('.json', '')

        return (
          <div
            key={rotation}
            className="flex items-center gap-2 p-2 rounded hover:bg-gray-50 transition-colors"
          >
            <Checkbox
              checked={isChecked}
              onChange={() => handleToggle(rotation)}
            />
            <label
              className="flex-1 text-base text-gray-900 cursor-pointer select-none"
              onClick={() => handleToggle(rotation)}
            >
              {displayName}
            </label>
          </div>
        )
      })}
    </div>
  )
}
