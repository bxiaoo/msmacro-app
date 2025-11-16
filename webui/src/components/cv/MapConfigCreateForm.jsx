import { useState, useEffect } from 'react'
import { Plus, Minus, Save, Square } from 'lucide-react'
import { createMapConfig } from '../../api'
import { Button } from '../ui/button'
import { Input } from '../ui/input'

export function MapConfigCreateForm({ onCreated, onCancel }) {
  const [name, setName] = useState('')
  const [tlX, setTlX] = useState(66)
  const [tlY, setTlY] = useState(34)
  const [width, setWidth] = useState(150)
  const [height, setHeight] = useState(45)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState(false)
  const [saving, setSaving] = useState(false)

  // Update preview when coordinates change
  useEffect(() => {
    const url = `/api/cv/frame-lossless?tl_x=${tlX}&tl_y=${tlY}&width=${width}&height=${height}&t=${Date.now()}`
    console.log('[MapConfigCreateForm] Preview URL updated:', url)
    console.log('[MapConfigCreateForm] Coordinates:', { tlX, tlY, width, height })
    setPreviewUrl(url)
    setPreviewError(false) // Reset error when coordinates change
  }, [tlX, tlY, width, height])

  const handleSave = async () => {
    // Validate name
    if (!name.trim()) {
      alert('Please enter a name for the map configuration')
      return
    }

    // Validate coordinates
    if (tlX < 0 || tlY < 0 || width <= 0 || height <= 0) {
      alert('Invalid coordinates. All values must be positive, and width/height must be greater than 0.')
      console.error('[MapConfigCreateForm] Invalid coordinates:', { tlX, tlY, width, height })
      return
    }

    if (tlX + width > 1280 || tlY + height > 720) {
      alert(`Coordinates out of bounds. Region (${tlX + width}, ${tlY + height}) exceeds maximum dimensions (1280, 720).`)
      console.error('[MapConfigCreateForm] Coordinates out of bounds:', { tlX, tlY, width, height, max: [1280, 720] })
      return
    }

    setSaving(true)
    try {
      console.log('[MapConfigCreateForm] Creating map config with params:', {
        name: name.trim(),
        tlX,
        tlY,
        width,
        height
      })

      await createMapConfig(name.trim(), tlX, tlY, width, height)

      console.log('[MapConfigCreateForm] Map config created successfully:', name.trim())
      onCreated(name.trim())
    } catch (error) {
      console.error('[MapConfigCreateForm] Failed to create map config:', error)

      // Extract detailed error information
      const errorMessage = error.body?.error || error.message || 'Unknown error'
      const statusCode = error.status || 'N/A'

      let userMessage = `Failed to create map config (HTTP ${statusCode}): ${errorMessage}`

      // Add specific guidance based on error type
      if (statusCode === 400) {
        userMessage += '\n\nValidation failed. The map config name might already exist or contain invalid characters.'
      } else if (statusCode === 500) {
        userMessage += '\n\nServer error occurred. Check the backend logs for details.'
      } else if (statusCode === 'N/A') {
        userMessage += '\n\nNetwork error. Please check your connection and ensure the backend is running.'
      }

      alert(userMessage)
    } finally {
      setSaving(false)
    }
  }

  const adjustValue = (setter, current, delta) => {
    setter(Math.max(0, current + delta))
  }

  return (
    <div className="bg-white border-2 border-gray-300 rounded p-4 space-y-4">
      <h4 className="font-bold text-base text-gray-900">Create new map</h4>

      {/* Live Preview */}
      <div className="border-2 border-gray-300 rounded overflow-hidden bg-gray-50 min-h-[100px] flex flex-col">
        {previewUrl && (
          <>
            <img
              key={previewUrl}
              src={previewUrl}
              alt="Map preview"
              className="w-full h-auto"
              onError={(e) => {
                console.error('[MapConfigCreateForm] Failed to load preview')
                console.error('[MapConfigCreateForm] Preview URL:', previewUrl)
                console.error('[MapConfigCreateForm] Coordinates:', { tlX, tlY, width, height })
                console.error('[MapConfigCreateForm] Error:', e)
                setPreviewError(true)
              }}
              onLoad={() => {
                console.log('[MapConfigCreateForm] Preview loaded successfully')
                setPreviewError(false)
              }}
            />
            {previewError && (
              <div className="bg-red-50 border-t border-red-200 p-3 text-center">
                <p className="text-red-600 text-sm font-medium">⚠️ Failed to load preview</p>
                <p className="text-red-500 text-xs mt-1">
                  Check if CV frame capture is running. The daemon must be active to show live previews.
                </p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Name Input */}
      <div className="flex flex-col gap-2">
        <label className="text-sm text-gray-900">Map Name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter map name"
          className="w-full"
          autoComplete="off"
          data-form-type="other"
        />
      </div>

      {/* Origin Adjustment */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-900">x origin</label>
          <div className="bg-gray-100 rounded flex items-center overflow-hidden">
            <button
              onClick={() => adjustValue(setTlX, tlX, -10)}
              className="p-3 hover:bg-gray-200 border-r border-gray-300"
            >
              <Minus size={20} />
            </button>
            <div className="flex-1 flex items-center justify-center py-3">
              <span className="font-medium text-base text-gray-900">{tlX}</span>
            </div>
            <button
              onClick={() => adjustValue(setTlX, tlX, 10)}
              className="p-3 hover:bg-gray-200 border-l border-gray-300"
            >
              <Plus size={20} />
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-900">y origin</label>
          <div className="bg-gray-100 rounded flex items-center overflow-hidden">
            <button
              onClick={() => adjustValue(setTlY, tlY, -10)}
              className="p-3 hover:bg-gray-200 border-r border-gray-300"
            >
              <Minus size={20} />
            </button>
            <div className="flex-1 flex items-center justify-center py-3">
              <span className="font-medium text-base text-gray-900">{tlY}</span>
            </div>
            <button
              onClick={() => adjustValue(setTlY, tlY, 10)}
              className="p-3 hover:bg-gray-200 border-l border-gray-300"
            >
              <Plus size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Axis Adjustment */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-900">x axis</label>
          <div className="bg-gray-100 rounded flex items-center overflow-hidden">
            <button
              onClick={() => adjustValue(setWidth, width, -10)}
              className="p-3 hover:bg-gray-200 border-r border-gray-300"
            >
              <Minus size={20} />
            </button>
            <div className="flex-1 flex items-center justify-center py-3">
              <span className="font-medium text-base text-gray-900">{width}</span>
            </div>
            <button
              onClick={() => adjustValue(setWidth, width, 10)}
              className="p-3 hover:bg-gray-200 border-l border-gray-300"
            >
              <Plus size={20} />
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm text-gray-900">y axis</label>
          <div className="bg-gray-100 rounded flex items-center overflow-hidden">
            <button
              onClick={() => adjustValue(setHeight, height, -10)}
              className="p-3 hover:bg-gray-200 border-r border-gray-300"
            >
              <Minus size={20} />
            </button>
            <div className="flex-1 flex items-center justify-center py-3">
              <span className="font-medium text-base text-gray-900">{height}</span>
            </div>
            <button
              onClick={() => adjustValue(setHeight, height, 10)}
              className="p-3 hover:bg-gray-200 border-l border-gray-300"
            >
              <Plus size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4 pt-2">
        <Button
          onClick={handleSave}
          disabled={saving || !name.trim()}
          className="flex-1 bg-blue-700 text-white h-11 flex items-center justify-center gap-2"
        >
          <Save size={20} />
          Save
        </Button>
        <Button
          onClick={onCancel}
          disabled={saving}
          className="flex-1 bg-white text-gray-900 border border-gray-300 h-11 flex items-center justify-center gap-2"
        >
          <Square size={20} />
          Discard
        </Button>
      </div>
    </div>
  )
}
