import { useState } from 'react'
import { Input } from '../ui/input'
import { Checkbox } from '../ui/checkbox'

export function PathfindingConfig({ config, onChange }) {
  const handleClassChange = (classType) => {
    onChange({
      ...config,
      class_type: classType
    })
  }

  const handleFieldChange = (field, value) => {
    onChange({
      ...config,
      [field]: value
    })
  }

  const handleCheckboxChange = (checked) => {
    onChange({
      ...config,
      double_jump_up_allowed: checked,
      // Clear Y axis jump skill when enabling double jump
      y_axis_jump_skill: checked ? '' : config.y_axis_jump_skill
    })
  }

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Header */}
      <h3 className="font-bold text-base text-gray-900">Pathfinding</h3>

      {/* Class Tabs */}
      <div className="bg-gray-100 p-1 rounded-lg flex gap-1">
        <button
          onClick={() => handleClassChange('other')}
          className={`flex-1 px-3 py-2.5 text-sm font-semibold rounded-md transition-all ${
            config.class_type === 'other'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-900 hover:bg-gray-50'
          }`}
        >
          Other class
        </button>
        <button
          onClick={() => handleClassChange('magician')}
          className={`flex-1 px-3 py-2.5 text-sm font-semibold rounded-md transition-all ${
            config.class_type === 'magician'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-900 hover:bg-gray-50'
          }`}
        >
          Magician class
        </button>
      </div>

      {/* Configuration Inputs */}
      <div className="flex flex-col gap-2">
        {/* Rope lift key (both classes) */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-normal text-gray-900">
            Rope lift key
          </label>
          <Input
            type="text"
            value={config.rope_lift_key || ''}
            onChange={(e) => handleFieldChange('rope_lift_key', e.target.value)}
            placeholder="Keystroke"
            className="bg-gray-100 h-11"
          />
        </div>

        {/* Other class specific fields */}
        {config.class_type === 'other' && (
          <>
            {/* Diagonal movement key */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-normal text-gray-900">
                Diagonal movement key
              </label>
              <Input
                type="text"
                value={config.diagonal_movement_key || ''}
                onChange={(e) => handleFieldChange('diagonal_movement_key', e.target.value)}
                placeholder="Keystroke"
                className="bg-gray-100 h-11"
              />
            </div>

            {/* Double jump UP allowed checkbox */}
            <div className="flex items-center gap-1">
              <Checkbox
                checked={config.double_jump_up_allowed ?? true}
                onCheckedChange={handleCheckboxChange}
              />
              <label className="text-sm font-normal text-gray-900">
                Double jump UP allowed
              </label>
            </div>

            {/* Y axis jump skill (disabled when double jump enabled) */}
            <div className="flex flex-col gap-1.5">
              <label className={`text-sm font-normal ${
                config.double_jump_up_allowed ?? true ? 'text-gray-400' : 'text-gray-900'
              }`}>
                Y axis jump skill
              </label>
              <Input
                type="text"
                value={config.y_axis_jump_skill || ''}
                onChange={(e) => handleFieldChange('y_axis_jump_skill', e.target.value)}
                placeholder="Keystroke"
                className="bg-gray-100 h-11"
                disabled={config.double_jump_up_allowed ?? true}
              />
            </div>
          </>
        )}

        {/* Magician class specific fields */}
        {config.class_type === 'magician' && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-normal text-gray-900">
              Teleport skill
            </label>
            <Input
              type="text"
              value={config.teleport_skill || ''}
              onChange={(e) => handleFieldChange('teleport_skill', e.target.value)}
              placeholder="Keystroke"
              className="bg-gray-100 h-11"
            />
          </div>
        )}
      </div>
    </div>
  )
}
