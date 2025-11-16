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
  const [saving, setSaving] = useState(false)

  // Update preview when coordinates change
  useEffect(() => {
    const url = `/api/cv/frame-lossless?tl_x=${tlX}&tl_y=${tlY}&width=${width}&height=${height}&t=${Date.now()}`
    setPreviewUrl(url)
  }, [tlX, tlY, width, height])

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Please enter a name for the map configuration')
      return
    }

    setSaving(true)
    try {
      await createMapConfig(name.trim(), tlX, tlY, width, height)
      onCreated(name.trim())
    } catch (error) {
      alert(`Failed to create map config: ${error.message}`)
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
      <div className="border-2 border-gray-300 rounded overflow-hidden bg-gray-50">
        {previewUrl && (
          <img
            key={previewUrl}
            src={previewUrl}
            alt="Map preview"
            className="w-full h-auto"
            onError={() => console.error('Failed to load preview')}
          />
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
