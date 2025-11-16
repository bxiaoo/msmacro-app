import { useState, useEffect } from 'react'
import { ChevronRight, Square } from 'lucide-react'
import { createCVItem, updateCVItem } from '../../api'
import { CVItemMapStep } from './CVItemMapStep'
import { CVItemDepartureStep } from './CVItemDepartureStep'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'

export function CVItemDrawer({ isOpen, onClose, onSave, editingItem }) {
  const [currentStep, setCurrentStep] = useState(1)
  const [itemName, setItemName] = useState('')
  const [showNameDialog, setShowNameDialog] = useState(false)
  const [mapConfigName, setMapConfigName] = useState(null)
  const [pathfindingRotations, setPathfindingRotations] = useState({
    near: [],
    medium: [],
    far: [],
    very_far: []
  })
  const [pathfindingConfig, setPathfindingConfig] = useState({
    class_type: 'other',
    rope_lift_key: '',
    diagonal_movement_key: '',
    double_jump_up_allowed: true,
    y_axis_jump_skill: '',
    teleport_skill: ''
  })
  const [departurePoints, setDeparturePoints] = useState([])

  // Load editing item data when drawer opens
  useEffect(() => {
    if (editingItem) {
      setItemName(editingItem.name)
      setMapConfigName(editingItem.map_config_name)
      setPathfindingRotations(editingItem.pathfinding_rotations || {
        near: [],
        medium: [],
        far: [],
        very_far: []
      })
      setPathfindingConfig(editingItem.pathfinding_config || {
        class_type: 'other',
        rope_lift_key: '',
        diagonal_movement_key: '',
        double_jump_up_allowed: true,
        y_axis_jump_skill: '',
        teleport_skill: ''
      })
      setDeparturePoints(editingItem.departure_points || [])
    } else {
      // Reset for new item
      setItemName('')
      setMapConfigName(null)
      setPathfindingRotations({ near: [], medium: [], far: [], very_far: [] })
      setPathfindingConfig({
        class_type: 'other',
        rope_lift_key: '',
        diagonal_movement_key: '',
        double_jump_up_allowed: true,
        y_axis_jump_skill: '',
        teleport_skill: ''
      })
      setDeparturePoints([])
    }
    setCurrentStep(1)
  }, [editingItem, isOpen])

  const handleContinue = () => {
    setCurrentStep(2)
  }

  const handleBack = () => {
    setCurrentStep(1)
  }

  const handleSaveClick = () => {
    // Validate before opening dialog
    if (!mapConfigName) {
      alert('Please select a map configuration')
      return
    }

    if (departurePoints.length === 0) {
      alert('Please add at least one departure point')
      return
    }

    // Check that at least one point has rotations
    const hasRotations = departurePoints.some(p => p.rotation_paths && p.rotation_paths.length > 0)
    if (!hasRotations) {
      alert('At least one departure point must have linked rotations')
      return
    }

    // Pre-fill name if editing
    if (editingItem) {
      setItemName(editingItem.name)
    }

    // Open naming dialog
    setShowNameDialog(true)
  }

  const handleConfirmSave = async () => {
    // Validate name
    if (!itemName.trim()) {
      alert('Please enter a valid CV Item name')
      return
    }

    const item = {
      name: itemName.trim(),
      map_config_name: mapConfigName,
      pathfinding_rotations,
      pathfinding_config: pathfindingConfig,
      departure_points: departurePoints,
      description: '',
      tags: []
    }

    try {
      if (editingItem) {
        await updateCVItem(editingItem.name, item)
      } else {
        await createCVItem(item)
      }
      setShowNameDialog(false)
      onSave()
    } catch (error) {
      alert(`Failed to save CV Item: ${error.message}`)
    }
  }

  const handleDiscard = () => {
    if (confirm('Discard changes?')) {
      onClose()
    }
  }

  if (!isOpen) return null

  const canContinue = mapConfigName

  return (
    <>
      {/* Dark overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-lg shadow-lg z-50 max-h-[90vh] overflow-y-auto">
        <div className="p-4 px-4 py-8 flex flex-col gap-4">
          {/* Header */}
          <div className="flex flex-col gap-2">
            <h2 className="font-bold text-lg text-gray-900">
              {editingItem ? 'Edit CV Item' : 'New cv rotation set'}
            </h2>

            {/* Progress indicator */}
            <div className="flex items-center gap-1">
              <div className={`px-4 py-2 rounded ${currentStep === 1 ? 'bg-blue-100' : 'bg-gray-100'}`}>
                <p className={`text-sm font-medium ${currentStep === 1 ? 'text-blue-600' : 'text-gray-400'}`}>
                  Select map
                </p>
              </div>
              <ChevronRight size={20} className="text-gray-400" />
              <div className={`px-4 py-2 rounded ${currentStep === 2 ? 'bg-blue-100' : 'bg-gray-100'}`}>
                <p className={`text-sm font-medium ${currentStep === 2 ? 'text-blue-600' : 'text-gray-400'}`}>
                  Craft rotation
                </p>
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-gray-200 h-1 rounded-full">
              <div
                className="bg-blue-600 h-1 rounded-full transition-all"
                style={{ width: `${(currentStep / 2) * 100}%` }}
              />
            </div>
          </div>

          {/* Step content */}
          <div className="flex-1 overflow-y-auto">
            {currentStep === 1 && (
              <CVItemMapStep
                mapConfigName={mapConfigName}
                onMapConfigChange={setMapConfigName}
                pathfindingRotations={pathfindingRotations}
                onPathfindingChange={setPathfindingRotations}
                pathfindingConfig={pathfindingConfig}
                onPathfindingConfigChange={setPathfindingConfig}
              />
            )}

            {currentStep === 2 && (
              <CVItemDepartureStep
                mapConfigName={mapConfigName}
                departurePoints={departurePoints}
                onDeparturePointsChange={setDeparturePoints}
              />
            )}
          </div>

          {/* Action buttons */}
          <div className="flex flex-col gap-4 pt-4 border-t border-gray-200">
            {currentStep === 1 && (
              <div className="flex gap-4">
                <Button
                  onClick={handleContinue}
                  disabled={!canContinue}
                  className="flex-1 bg-blue-700 text-white h-16 flex items-center justify-center gap-2"
                >
                  <ChevronRight size={20} />
                  Continue
                </Button>
                <Button
                  onClick={handleDiscard}
                  className="flex-1"
                >
                  <Square size={20} />
                  Discard
                </Button>
              </div>
            )}

            {currentStep === 2 && (
              <div className="flex gap-4">
                <Button
                  onClick={handleSaveClick}
                  disabled={departurePoints.length === 0}
                  className="flex-1 bg-blue-700 text-white h-16"
                >
                  Save
                </Button>
                <Button
                  onClick={handleDiscard}
                  className="flex-1 bg-white text-gray-900 border border-gray-300 h-16 flex items-center justify-center gap-2"
                >
                  <Square size={20} />
                  Discard
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Naming Dialog */}
      <Dialog open={showNameDialog} onOpenChange={setShowNameDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit CV Item Name' : 'Name Your CV Item'}</DialogTitle>
            <DialogDescription>
              {editingItem
                ? 'You can change the name of this CV item if needed.'
                : 'Enter a unique name to identify this CV rotation set.'
              }
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <Input
              placeholder="Enter CV Item name..."
              value={itemName}
              onChange={(e) => setItemName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && itemName.trim()) {
                  handleConfirmSave()
                }
              }}
              className="w-full"
              autoFocus
            />
          </div>

          <DialogFooter>
            <Button
              onClick={() => setShowNameDialog(false)}
              variant="ghost"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmSave}
              disabled={!itemName.trim()}
              variant="primary"
            >
              {editingItem ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
