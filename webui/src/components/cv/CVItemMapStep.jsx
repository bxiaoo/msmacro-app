import { useState, useEffect } from 'react'
import { ChevronDown, Plus, Trash2, Target } from 'lucide-react'
import { listMapConfigs, listFiles, deleteMapConfig } from '../../api'
import { Button } from '../ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { MapConfigCreateForm } from './MapConfigCreateForm'
import { PathfindingConfig } from './PathfindingConfig'

export function CVItemMapStep({
  mapConfigName,
  onMapConfigChange,
  pathfindingRotations,
  onPathfindingChange,
  pathfindingConfig,
  onPathfindingConfigChange
}) {
  const [mapConfigs, setMapConfigs] = useState([])
  const [availableRotations, setAvailableRotations] = useState([])
  const [expandedSection, setExpandedSection] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)

  useEffect(() => {
    loadMapConfigs()
    loadRotations()
  }, [])

  const loadMapConfigs = () => {
    listMapConfigs().then(data => {
      setMapConfigs(data.configs || [])
    })
  }

  const loadRotations = () => {
    listFiles().then(files => {
      const rotationNames = files.map(f => f.split('/').pop().replace('.json', ''))
      setAvailableRotations(rotationNames)
    })
  }

  const handleMapSelect = (configName) => {
    onMapConfigChange(configName)
    setShowCreateForm(false)
  }

  const handleMapCreated = (configName) => {
    loadMapConfigs()
    onMapConfigChange(configName)
    setShowCreateForm(false)
  }

  const handleDeleteMap = async () => {
    if (!mapConfigName) {
      alert('No map config selected')
      return
    }

    if (confirm(`Are you sure you want to delete map config "${mapConfigName}"?`)) {
      try {
        await deleteMapConfig(mapConfigName)
        onMapConfigChange(null)
        loadMapConfigs()
      } catch (error) {
        alert(`Failed to delete map config: ${error.message}`)
      }
    }
  }

  const handleAddRotation = (distance, rotationPath) => {
    const current = pathfindingRotations[distance] || []
    if (!current.includes(rotationPath)) {
      onPathfindingChange({
        ...pathfindingRotations,
        [distance]: [...current, rotationPath]
      })
    }
  }

  const handleRemoveRotation = (distance, rotationPath) => {
    const current = pathfindingRotations[distance] || []
    onPathfindingChange({
      ...pathfindingRotations,
      [distance]: current.filter(r => r !== rotationPath)
    })
  }

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  return (
    <div className="flex flex-col gap-4 w-full">
      {showCreateForm ? (
        /* Create New Map Form - Replaces entire content */
        <MapConfigCreateForm
          onCreated={handleMapCreated}
          onCancel={() => setShowCreateForm(false)}
        />
      ) : (
        <>
          {/* Map Selection */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-normal text-gray-900">Select map preset</label>

            {/* Map Config Select Dropdown */}
            <Select value={mapConfigName} onValueChange={handleMapSelect}>
              <SelectTrigger>
                <SelectValue placeholder="Select a map config..." />
              </SelectTrigger>
              <SelectContent>
                {mapConfigs.map((config) => (
                  <SelectItem key={config.name} value={config.name}>
                    <div className="flex flex-col">
                      <span className="font-medium">{config.name}</span>
                      <span className="text-xs text-gray-500">
                        Origin: ({config.tl_x}, {config.tl_y}) • Size: {config.width}×{config.height}
                      </span>
                    </div>
                  </SelectItem>
                ))}
                {mapConfigs.length === 0 && (
                  <div className="px-2 py-3 text-sm text-gray-500 text-center">
                    No map configs available
                  </div>
                )}
              </SelectContent>
            </Select>

            {/* Action Buttons */}
            <div className="flex gap-2">
              {/* Create New Map Button */}
              <Button
                variant="default"
                size="lg"
                className="flex-1"
                onClick={() => setShowCreateForm(true)}
              >
                <Target size={16} />
                Create new
              </Button>

              {/* Delete Current Map Button */}
              <Button
                variant="ghost"
                size="lg"
                onClick={handleDeleteMap}
                disabled={!mapConfigName}
                className="border border-gray-300 w-full flex-1"
              >
                <Trash2 size={16} />
                Delete current
              </Button>
            </div>
          </div>

          {/* Pathfinding Configuration */}
          <PathfindingConfig
            config={pathfindingConfig}
            onChange={onPathfindingConfigChange}
          />
        </>
      )}
    </div>
  )
}
