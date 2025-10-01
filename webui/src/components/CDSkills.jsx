import { Plus } from 'lucide-react'
import { SkillCell } from './SkillCell'

function AddSkillButton({ onClick }) {
  return (
    <div
      className="relative rounded-[4px] shrink-0 w-full cursor-pointer"
      onClick={onClick}
    >
      <div className="box-border content-stretch flex items-center justify-center overflow-clip px-0 py-[18px] relative w-full">
        <div className="overflow-clip relative shrink-0 size-[20px]">
          <Plus size={20} className="text-gray-600" />
        </div>
      </div>
      <div aria-hidden="true" className="absolute border-2 border-dashed border-gray-300 inset-0 pointer-events-none rounded-[4px]" />
    </div>
  )
}

export function CDSkills({ skills, onOpenNewSkillModal, onEditSkill, onUpdateSkill, onDeleteSkill }) {
  const addNewSkill = () => {
    onOpenNewSkillModal()
  }

  return (
    <div className="bg-gray-100 min-h-full relative">
      <div className="px-4 py-4">
        <div className="flex flex-col gap-3 w-full">
          {skills.length === 0 ? (
            // Empty state - only show the large add button
            <AddSkillButton onClick={addNewSkill} />
          ) : (
            // Skills list with add button at the end
            <>
              {skills.map((skill) => (
                <SkillCell
                  key={skill.id}
                  skillName={skill.name}
                  variant={skill.variant}
                  isOpen={skill.isOpen}
                  isEnabled={skill.isEnabled}
                  isSelected={skill.isSelected}
                  onToggleSelect={() => onUpdateSkill(skill.id, { isSelected: !skill.isSelected })}
                  onToggleExpand={() => onUpdateSkill(skill.id, { isOpen: !skill.isOpen })}
                  onEdit={() => onEditSkill(skill)}
                  onDelete={() => onDeleteSkill(skill.id)}
                  // CD Skill props
                  afterKeyConstraints={skill.afterKeyConstraints}
                  onAfterKeyConstraintsChange={(value) => onUpdateSkill(skill.id, { afterKeyConstraints: value })}
                  key1={skill.key1}
                  key2={skill.key2}
                  key3={skill.key3}
                  onKey1Change={(value) => onUpdateSkill(skill.id, { key1: value })}
                  onKey2Change={(value) => onUpdateSkill(skill.id, { key2: value })}
                  onKey3Change={(value) => onUpdateSkill(skill.id, { key3: value })}
                  afterKeysSeconds={skill.afterKeysSeconds}
                  onAfterKeysSecondsChange={(value) => onUpdateSkill(skill.id, { afterKeysSeconds: value })}
                  frozenRotationDuringCasting={skill.frozenRotationDuringCasting}
                  onFrozenRotationDuringCastingChange={(value) => onUpdateSkill(skill.id, { frozenRotationDuringCasting: value })}
                />
              ))}

              <AddSkillButton onClick={addNewSkill} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}