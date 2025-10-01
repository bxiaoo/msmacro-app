import { useState, useEffect } from 'react'
import { Save, X } from 'lucide-react'

function NumberInput({ label, value, onChange, disabled = false }) {
  return (
    <div className="content-stretch flex flex-col gap-[8px] items-start relative shrink-0 w-full">
      <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[14px] w-full ${
        disabled ? 'text-gray-400' : 'text-gray-900'
      }`} style={{ fontVariationSettings: "'wdth' 100" }}>
        {label}
      </p>
      <div className="bg-gray-100 content-stretch flex items-center overflow-clip relative rounded-[2px] shrink-0 w-full">
        <div className="box-border content-stretch flex gap-[10px] items-center overflow-clip p-[12px] relative shrink-0">
          <div className="overflow-clip relative shrink-0 size-[20px]">
            <button
              type="button"
              onClick={() => onChange(Math.max(0, value - 1))}
              disabled={disabled}
              className={`w-full h-full flex items-center justify-center ${disabled ? 'text-gray-400' : 'text-gray-600'}`}
            >
              <span className="text-lg">−</span>
            </button>
          </div>
        </div>
        <div className="flex flex-row items-center self-stretch">
          <div className="bg-gray-300 h-full shrink-0 w-px" />
        </div>
        <div className="basis-0 flex flex-row grow items-center self-stretch shrink-0">
          <div className="basis-0 box-border content-stretch flex gap-[10px] grow h-full items-center justify-center min-h-px min-w-px overflow-clip px-[14px] py-0 relative shrink-0">
            <input
              type="number"
              value={value}
              onChange={(e) => onChange(parseInt(e.target.value) || 0)}
              disabled={disabled}
              className={`font-['Roboto:Medium',_sans-serif] font-medium leading-[normal] text-[16px] bg-transparent border-none outline-none text-center w-full ${
                disabled ? 'text-gray-400' : 'text-gray-900'
              }`}
              style={{ fontVariationSettings: "'wdth' 100" }}
            />
          </div>
        </div>
        <div className="flex flex-row items-center self-stretch">
          <div className="bg-gray-300 h-full shrink-0 w-px" />
        </div>
        <div className="box-border content-stretch flex gap-[10px] items-center overflow-clip p-[12px] relative shrink-0">
          <div className="overflow-clip relative shrink-0 size-[20px]">
            <button
              type="button"
              onClick={() => onChange(value + 1)}
              disabled={disabled}
              className={`w-full h-full flex items-center justify-center ${disabled ? 'text-gray-400' : 'text-gray-600'}`}
            >
              <span className="text-lg">+</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function KeyInput({ label, placeholder = "Keystroke", value, onChange, disabled = false }) {
  return (
    <div className="content-stretch flex flex-col gap-[8px] items-start relative shrink-0 w-full">
      <p className={`font-['Roboto:Regular',_sans-serif] font-normal leading-[normal] relative shrink-0 text-[14px] w-full ${
        disabled ? 'text-gray-400' : 'text-gray-900'
      }`} style={{ fontVariationSettings: "'wdth' 100" }}>
        {label}
      </p>
      <div className="bg-gray-100 box-border content-stretch flex gap-[10px] h-[44px] items-center overflow-clip px-[8px] py-0 relative rounded-[4px] shrink-0 w-full">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className={`basis-0 font-['Roboto:Regular',_sans-serif] font-normal grow leading-[normal] min-h-px min-w-px relative shrink-0 text-[16px] bg-transparent border-none outline-none ${
            disabled ? 'text-gray-600' : 'text-gray-600'
          }`}
          style={{ fontVariationSettings: "'wdth' 100" }}
        />
      </div>
    </div>
  )
}

export function NewSkillModal({ isOpen, onClose, onSave, editingSkill = null }) {
  const [skillKey, setSkillKey] = useState('')
  const [cooldown, setCooldown] = useState(120)

  // Pre-populate form when editing
  useEffect(() => {
    if (editingSkill) {
      setSkillKey(editingSkill.name || '')
      setCooldown(editingSkill.cooldown || 120)
    } else {
      setSkillKey('')
      setCooldown(120)
    }
  }, [editingSkill, isOpen])

  const handleSave = () => {
    if (!skillKey.trim()) return

    onSave({
      skillKey: skillKey.trim(),
      cooldown,
      isEditing: !!editingSkill,
      skillId: editingSkill?.id
    })

    // Reset form
    setSkillKey('')
    setCooldown(120)
  }

  const handleDiscard = () => {
    setSkillKey('')
    setCooldown(120)
    onClose()
  }

  const canSave = skillKey.trim().length > 0

  if (!isOpen) return null

  return (
    <>
      {/* Overlay */}
      <div className="absolute bg-[rgba(0,0,0,0.25)] inset-0 z-40" onClick={handleDiscard} />

      {/* Modal */}
      <div className="absolute bottom-0 content-stretch flex flex-col items-start left-0 right-0 z-50">
        <div className="bg-white box-border content-stretch flex flex-col gap-[16px] items-start p-[16px] relative rounded-tl-[8px] rounded-tr-[8px] shrink-0 w-full">
          <p className="font-['Roboto:Bold',_sans-serif] font-bold leading-[normal] relative shrink-0 text-[18px] text-gray-900 w-full" style={{ fontVariationSettings: "'wdth' 100" }}>
            {editingSkill ? 'Edit CD skill' : 'New CD skill'}
          </p>

          <div className="content-stretch flex flex-col gap-[14px] items-start relative shrink-0 w-full">
            <KeyInput
              label="Skill key"
              value={skillKey}
              onChange={setSkillKey}
              placeholder="Keystroke"
            />

            <NumberInput
              label="Cold down (second)"
              value={cooldown}
              onChange={setCooldown}
            />
          </div>
        </div>

        {/* Action buttons - replaces the main record/play buttons */}
        <div className="bg-white box-border content-stretch flex flex-col gap-[20px] items-start pb-[24px] pt-[16px] px-[16px] relative shrink-0 w-full">
          <div className="content-stretch flex flex-col gap-[16px] items-start relative shrink-0 w-full">
            <div className="content-stretch flex gap-[16px] items-center relative shrink-0 w-full">
              <button
                onClick={handleSave}
                disabled={!canSave}
                className={`basis-0 box-border content-stretch flex gap-[8px] grow h-[64px] items-center justify-center min-h-px min-w-px px-[32px] py-0 relative rounded-[4px] shrink-0 ${
                  canSave ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              >
                <div className="overflow-clip relative shrink-0 size-[20px]">
                  <Save size={20} className={canSave ? 'text-white' : 'text-gray-400'} />
                </div>
                <p className={`font-['Roboto:Medium',_sans-serif] font-medium leading-[normal] relative shrink-0 text-[16px] text-nowrap whitespace-pre ${
                  canSave ? 'text-white' : 'text-gray-400'
                }`} style={{ fontVariationSettings: "'wdth' 100" }}>
                  Save
                </p>
              </button>

              <button
                onClick={handleDiscard}
                className="basis-0 bg-gray-900 box-border content-stretch flex gap-[8px] grow h-[64px] items-center justify-center min-h-px min-w-px px-[32px] py-0 relative rounded-[4px] shrink-0"
              >
                <div className="overflow-clip relative shrink-0 size-[20px]">
                  <X size={20} className="text-white" />
                </div>
                <p className="font-['Roboto:Medium',_sans-serif] font-medium leading-[normal] relative shrink-0 text-[16px] text-nowrap text-white whitespace-pre" style={{ fontVariationSettings: "'wdth' 100" }}>
                  Discard
                </p>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}