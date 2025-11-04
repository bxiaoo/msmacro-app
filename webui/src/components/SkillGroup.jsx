import { Plus } from 'lucide-react'
import { useDroppable } from '@dnd-kit/core'
import { SkillCell } from './SkillCell'
import { DropLine } from './ui/drop-line'

function DelaySeparator({ delay, onDelayClick }) {
  return (
    <div className="content-stretch flex flex-col items-center relative w-full">
      <div className="h-0 relative w-full">
        <div className="absolute bottom-0 left-0 right-0 top-[-1px] border-t border-gray-300" />
      </div>
      <div
        className="absolute bg-gray-200 box-border content-stretch flex gap-[10px] items-center left-1/2 px-[8px] py-[2px] rounded-[99px] top-1/2 translate-x-[-50%] translate-y-[-50%] cursor-pointer hover:bg-gray-300 transition-colors"
        onClick={onDelayClick}
      >
        {delay !== null && delay !== undefined ? (
          <p className="font-['Roboto:Bold',_sans-serif] font-bold leading-[normal] shrink-0 text-[14px] text-gray-700 text-nowrap whitespace-pre" style={{ fontVariationSettings: "'wdth' 100" }}>
            {delay}s
          </p>
        ) : (
          <div className="overflow-clip relative shrink-0 size-[20px]">
            <Plus size={20} className="text-gray-700" />
          </div>
        )}
      </div>
    </div>
  )
}

export function SkillGroup({
  skills,
  groupId,
  onUpdateSkill,
  onEditSkill,
  onDeleteSkill,
  onDelayChange,
  draggingSkillId,
  dragOverId
}) {
  const { setNodeRef } = useDroppable({ id: `on-group:${groupId}` })
  const isOverGroup = dragOverId === `on-group:${groupId}`

  return (
    <div ref={setNodeRef} className={`bg-gray-200 box-border content-stretch flex flex-col isolate items-start relative rounded-[4px] shadow-[0px_1px_2px_0px_rgba(0,0,0,0.05)] w-full ${isOverGroup ? 'ring-2 ring-blue-400 ring-offset-2' : ''}`}>
        {skills.map((skill, index) => {
          const isThisSkillDragging = draggingSkillId === skill.id

          return (
            <div className='w-full' key={skill.id}>
              {/* In-group reorder drop line before each member */}
              <DropLine
                id={`before-in:${skill.id}`}
                isActive={dragOverId === `before-in:${skill.id}`}
                variant="in-group"
              />

              <div
                className={`content-stretch flex flex-col items-stretch relative w-full ${
                  isThisSkillDragging ? 'opacity-30 scale-95' : ''
                } ${
                  dragOverId === skill.id ? 'ring-2 ring-blue-400 ring-offset-2 rounded-[4px] shadow-lg' : ''
                }`}
                style={{ zIndex: skills.length - index }}
              >
                <SkillCell
                  id={skill.id}
                  skillName={skill.name}
                  variant={skill.variant}
                  isOpen={skill.isOpen}
                  isEnabled={skill.isEnabled}
                  isSelected={skill.isSelected}
                  onToggleSelect={() => onUpdateSkill(skill.id, { isSelected: !skill.isSelected })}
                  onToggleExpand={() => onUpdateSkill(skill.id, { isOpen: !skill.isOpen })}
                  onEdit={() => onEditSkill(skill)}
                  onDelete={() => onDeleteSkill(skill.id)}
                  keyReplacement={skill.keyReplacement}
                  onKeyReplacementChange={(value) => onUpdateSkill(skill.id, { keyReplacement: value })}
                  replaceRate={skill.replaceRate}
                  onReplaceRateChange={(value) => onUpdateSkill(skill.id, { replaceRate: value })}
                  frozenRotationDuringCasting={skill.frozenRotationDuringCasting}
                  onFrozenRotationDuringCastingChange={(value) => onUpdateSkill(skill.id, { frozenRotationDuringCasting: value })}
                  isInGroup={true}
                />

                {/* Show delay separator between skills (except after the last one) */}
                {index < skills.length - 1 && (
                  <DelaySeparator
                    delay={skill.delayAfter}
                    onDelayClick={() => {
                      const newDelay = prompt('Enter delay in seconds:', skill.delayAfter || '0')
                      if (newDelay !== null) {
                        const parsedDelay = parseFloat(newDelay)
                        if (!isNaN(parsedDelay) && parsedDelay >= 0) {
                          onDelayChange(skill.id, parsedDelay)
                        }
                      }
                    }}
                  />
                )}
              </div>
            </div>
          )
        })}
    </div>
  )
}
