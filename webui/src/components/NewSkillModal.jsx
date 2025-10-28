import { useState, useEffect } from 'react'
import { Save, X } from 'lucide-react'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { NumberInput } from './ui/number-input'

export function NewSkillModal({ isOpen, onClose, onSave, editingSkill = null }) {
  const [name, setName] = useState('')
  const [skillKey, setSkillKey] = useState('')
  const [cooldown, setCooldown] = useState(120)
  const [skillDelay, setSkillDelay] = useState(0.3)
  const [castPosition, setCastPosition] = useState(0.3)

  // Pre-populate form when editing
  useEffect(() => {
    if (editingSkill) {
      setName(editingSkill.name || '')
      setSkillKey(editingSkill.keystroke || editingSkill.name || '')
      setCooldown(editingSkill.cooldown || 120)
      setSkillDelay(editingSkill.skillDelay || 0.3)
      setCastPosition(editingSkill.castPosition || 0.3)
    } else {
      setName('')
      setSkillKey('')
      setCooldown(120)
      setSkillDelay(0.3)
      setCastPosition(0.3)
    }
  }, [editingSkill, isOpen])

  const handleSave = () => {
    if (!skillKey.trim() || !name.trim()) return

    onSave({
      name: name.trim(),
      skillKey: skillKey.trim(),
      cooldown,
      skillDelay,
      castPosition,
      isEditing: !!editingSkill,
      skillId: editingSkill?.id
    })

    // Reset form
    setName('')
    setSkillKey('')
    setCooldown(120)
    setSkillDelay(0.3)
    setCastPosition(0.3)
  }

  const handleDiscard = () => {
    setName('')
    setSkillKey('')
    setCooldown(120)
    setSkillDelay(0.3)
    setCastPosition(0.3)
    onClose()
  }

  const canSave = skillKey.trim().length > 0 && name.trim().length > 0

  if (!isOpen) return null

  return (
    <>
      {/* Modal */}
      <div className="absolute bottom-0 content-stretch flex flex-col items-start left-0 right-0 z-50">
        <div className="bg-white box-border content-stretch flex flex-col gap-[16px] items-start p-[16px] relative rounded-tl-[8px] rounded-tr-[8px] shrink-0 w-full">
          <p className="font-['Roboto:Bold',_sans-serif] font-bold leading-[normal] relative shrink-0 text-[18px] text-gray-900 w-full" style={{ fontVariationSettings: "'wdth' 100" }}>
            {editingSkill ? 'Edit skill' : 'New skill'}
          </p>

          <div className="content-stretch flex flex-col gap-[14px] items-start relative shrink-0 w-full">
            <div className="flex flex-col gap-1.5 w-full">
              <label className="text-sm font-medium text-gray-900">
                Name
              </label>
              <Input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Skill name"
              />
            </div>

            <div className="flex flex-col gap-1.5 w-full">
              <label className="text-sm font-medium text-gray-900">
                Skill key
              </label>
              <Input
                type="text"
                value={skillKey}
                onChange={(e) => setSkillKey(e.target.value)}
                placeholder="Keystroke"
              />
            </div>

            <NumberInput
              label="Cool down (second)"
              value={cooldown}
              onChange={setCooldown}
              min={0}
            />

            <NumberInput
              label="Skill delay (second)"
              value={skillDelay}
              onChange={setSkillDelay}
              min={0}
              step={0.1}
            />

            <NumberInput
              label="Cast position (second)"
              value={castPosition}
              onChange={setCastPosition}
              min={0}
              step={0.1}
            />
          </div>
        </div>

        {/* Action buttons - replaces the main record/play buttons */}
        <div className="bg-white box-border content-stretch flex flex-col gap-[20px] items-start pb-[16px] pt-[16px] px-[16px] relative shrink-0 w-full">
          <div className="content-stretch flex flex-col gap-[16px] items-start relative shrink-0 w-full">
            <div className="content-stretch flex gap-[16px] items-center relative shrink-0 w-full">
              <div className='w-full'>
              <Button
                onClick={handleSave}
                disabled={!canSave}
                variant="primary"
                className="w-full"
              >
                <Save size={20} />
                Save
              </Button>
              </div>

              <div className='w-full'>
              <Button
                onClick={handleDiscard}
                variant="default"
                className="w-full"
              >
                <X size={20} />
                Discard
              </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
