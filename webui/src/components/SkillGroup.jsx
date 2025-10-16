import { Plus } from 'lucide-react'
import { SkillCell } from './SkillCell'

function InGroupDropZone({ isVisible, onDrop }) {
  if (!isVisible) return null

  return (
    <div className="relative shrink-0 w-full h-[8px] flex items-center transition-all duration-200 ease-out px-3">
      <div
        aria-hidden="true"
        className="w-full h-[2px] bg-blue-500 rounded-full transition-all duration-200"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      />
    </div>
  )
}

function DelaySeparator({ delay, onDelayChange, onDelayClick }) {
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
  dragOverId,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  onLongPressStart,
  onLongPressEnd
}) {
  return (
    <div className="bg-gray-200 box-border content-stretch flex flex-col isolate items-start relative rounded-[4px] shadow-[0px_1px_2px_0px_rgba(0,0,0,0.05)] w-full transition-all duration-300 ease-out">
      {skills.map((skill, index) => {
        const isThisSkillDragging = draggingSkillId === skill.id
        const isDraggedFromSameGroup = draggingSkillId && skills.some(s => s.id === draggingSkillId)
        const showDropZoneBefore = isDraggedFromSameGroup && dragOverId === skill.id && draggingSkillId !== skill.id

        return (
          <div className='w-full' key={skill.id}>
            {/* Drop zone before skill (for in-group reordering) */}
            {showDropZoneBefore && (
              <InGroupDropZone
                isVisible={true}
                onDrop={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onDrop(skill.id, false)
                }}
              />
            )}

            <div
              data-skill-id={skill.id}
              className={`content-stretch flex flex-col items-stretch relative w-full transition-all duration-300 ease-out ${
                isThisSkillDragging ? 'opacity-30 scale-95' : ''
              }`}
              style={{ zIndex: skills.length - index }}
              onDragOver={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onDragOver(skill.id, e)
              }}
              onDrop={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onDrop(skill.id, false)
              }}
            >
              <SkillCell
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
                dragHandleProps={{
                  draggable: true,
                  onDragStart: (e) => onDragStart(skill.id, e),
                  onDragEnd: onDragEnd,
                  onTouchStart: (e) => {
                    e.preventDefault()
                    onLongPressStart(skill.id, e)
                  },
                  onTouchEnd: (e) => {
                    e.preventDefault()
                    onLongPressEnd()
                  }
                }}
                isInGroup={true}
              />

              {/* Show delay separator between skills (except after the last one) */}
              {index < skills.length - 1 && (
                <DelaySeparator
                  delay={skill.delay_after}
                  onDelayClick={() => {
                    const newDelay = prompt('Enter delay in seconds:', skill.delay_after || '0')
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
