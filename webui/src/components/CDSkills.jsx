import { useState, useCallback } from 'react'
import { Plus } from 'lucide-react'
import { SkillCell } from './SkillCell'
import { SkillGroup } from './SkillGroup'

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

function DropZone({ isVisible, onDrop, willGroup = false }) {
  if (!isVisible || willGroup) return null

  return (
    <div className="relative shrink-0 w-full h-[8px] flex items-center transition-all duration-200 ease-out">
      <div
        aria-hidden="true"
        className="w-full h-[2px] bg-blue-500 rounded-full transition-all duration-200"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      />
    </div>
  )
}

export function CDSkills({ skills, onOpenNewSkillModal, onEditSkill, onUpdateSkill, onDeleteSkill, onReorderSkills }) {
  const [dragState, setDragState] = useState({
    draggingId: null,
    dragOverId: null,
    longPressTimer: null,
    touchStart: null,
    dragPosition: null, // { x, y } for floating preview
    shouldGroup: false, // Whether current position would create a group
    showTopBoundary: false, // Show top boundary drop zone
    showBottomBoundary: false // Show bottom boundary drop zone
  })

  // Group skills by group_id
  const groupedSkills = useCallback(() => {
    const groups = {}
    const ungrouped = []

    // Sort skills by order
    const sortedSkills = [...skills].sort((a, b) => (a.order || 0) - (b.order || 0))

    sortedSkills.forEach(skill => {
      if (skill.group_id) {
        if (!groups[skill.group_id]) {
          groups[skill.group_id] = []
        }
        groups[skill.group_id].push(skill)
      } else {
        ungrouped.push(skill)
      }
    })

    // Create mixed array of groups and individual skills
    const result = []
    let processedSkills = new Set()

    sortedSkills.forEach(skill => {
      if (processedSkills.has(skill.id)) return

      if (skill.group_id && groups[skill.group_id]) {
        result.push({
          type: 'group',
          groupId: skill.group_id,
          skills: groups[skill.group_id]
        })
        groups[skill.group_id].forEach(s => processedSkills.add(s.id))
      } else {
        result.push({
          type: 'single',
          skill: skill
        })
        processedSkills.add(skill.id)
      }
    })

    return result
  }, [skills])

  const handleLongPressStart = (skillId, e) => {
    const touch = e.touches?.[0] || e
    const timer = setTimeout(() => {
      setDragState(prev => ({
        ...prev,
        draggingId: skillId,
        touchStart: { x: touch.clientX, y: touch.clientY },
        dragPosition: { x: touch.clientX, y: touch.clientY }
      }))
    }, 300) // 300ms long press

    setDragState(prev => ({
      ...prev,
      longPressTimer: timer
    }))
  }

  const handleLongPressEnd = () => {
    if (dragState.longPressTimer) {
      clearTimeout(dragState.longPressTimer)
    }
    setDragState(prev => ({
      ...prev,
      longPressTimer: null
    }))
  }

  const handleTouchMove = (e) => {
    if (!dragState.draggingId) return

    const touch = e.touches[0]
    setDragState(prev => ({
      ...prev,
      dragPosition: { x: touch.clientX, y: touch.clientY }
    }))

    updateDragTarget(touch.clientX, touch.clientY)
  }

  const handleMouseMove = (e) => {
    if (!dragState.draggingId) return

    setDragState(prev => ({
      ...prev,
      dragPosition: { x: e.clientX, y: e.clientY }
    }))

    updateDragTarget(e.clientX, e.clientY)
  }

  const updateDragTarget = (clientX, clientY) => {
    const draggedSkill = skills.find(s => s.id === dragState.draggingId)
    if (!draggedSkill) return

    // Get the skill list container bounds for boundary detection
    const skillListContainer = document.querySelector('.flex.flex-col.gap-3')
    const containerRect = skillListContainer?.getBoundingClientRect()

    // Large detection area for boundaries (80px from top/bottom of container)
    const boundaryDetectionSize = 80
    let showTopBoundary = false
    let showBottomBoundary = false

    if (containerRect) {
      const distanceFromTop = clientY - containerRect.top
      const distanceFromBottom = containerRect.bottom - clientY

      showTopBoundary = distanceFromTop < boundaryDetectionSize && distanceFromTop > 0
      showBottomBoundary = distanceFromBottom < boundaryDetectionSize && distanceFromBottom > 0
    }

    const element = document.elementFromPoint(clientX, clientY)
    const skillElement = element?.closest('[data-skill-id]')

    if (skillElement && !showTopBoundary && !showBottomBoundary) {
      const targetId = skillElement.getAttribute('data-skill-id')
      if (targetId === dragState.draggingId) return

      const targetSkill = skills.find(s => s.id === targetId)
      const rect = skillElement.getBoundingClientRect()
      const relativeY = clientY - rect.top

      // Check if dragged skill is from a group
      const isDraggedFromGroup = draggedSkill.group_id !== null
      const isTargetInSameGroup = isDraggedFromGroup && targetSkill?.group_id === draggedSkill.group_id

      // Determine behavior based on context
      let shouldGroup = false

      if (isTargetInSameGroup) {
        // Within same group: always reorder (never group)
        shouldGroup = false
      } else {
        // Different group or no group: check vertical position for grouping
        const isInGroupZone = relativeY > 20 && relativeY < rect.height - 20
        shouldGroup = isInGroupZone
      }

      setDragState(prev => ({
        ...prev,
        dragOverId: targetId,
        shouldGroup: shouldGroup,
        showTopBoundary: false,
        showBottomBoundary: false
      }))
    } else {
      setDragState(prev => ({
        ...prev,
        dragOverId: showTopBoundary || showBottomBoundary ? null : prev.dragOverId,
        shouldGroup: false,
        showTopBoundary: showTopBoundary,
        showBottomBoundary: showBottomBoundary
      }))
    }
  }

  const handleDragStart = (skillId, e) => {
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/html', e.currentTarget)
      // Hide default drag ghost
      const img = new Image()
      img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
      e.dataTransfer.setDragImage(img, 0, 0)
    }
    setDragState(prev => ({
      ...prev,
      draggingId: skillId,
      dragPosition: { x: e.clientX, y: e.clientY }
    }))
  }

  const handleDragOver = (targetId, e) => {
    e.preventDefault()
    if (dragState.draggingId === targetId) return

    // Update position for floating preview
    setDragState(prev => ({
      ...prev,
      dragOverId: targetId,
      dragPosition: { x: e.clientX, y: e.clientY }
    }))
  }

  const handleDragEnd = () => {
    setDragState({
      draggingId: null,
      dragOverId: null,
      longPressTimer: null,
      touchStart: null,
      dragPosition: null,
      shouldGroup: false,
      showTopBoundary: false,
      showBottomBoundary: false
    })
  }

  const handleTouchEnd = () => {
    if (dragState.draggingId) {
      if (dragState.showTopBoundary) {
        handleDropAtBoundary('top')
      } else if (dragState.showBottomBoundary) {
        handleDropAtBoundary('bottom')
      } else if (dragState.dragOverId) {
        handleDrop(dragState.dragOverId, dragState.shouldGroup)
      } else {
        handleDragEnd()
      }
    } else {
      handleDragEnd()
    }
  }

  const handleDrop = async (targetId, shouldGroup = false) => {
    if (!dragState.draggingId || dragState.draggingId === targetId) {
      handleDragEnd()
      return
    }

    const draggedSkill = skills.find(s => s.id === dragState.draggingId)
    const targetSkill = skills.find(s => s.id === targetId)

    if (!draggedSkill) {
      handleDragEnd()
      return
    }

    let updatedSkills = [...skills]

    // Check if reordering within the same group
    const isSameGroup = draggedSkill.group_id && draggedSkill.group_id === targetSkill?.group_id

    if (isSameGroup && targetSkill) {
      // In-group reordering: just swap orders within the group
      const draggedOrder = draggedSkill.order || 0
      const targetOrder = targetSkill.order || 0

      updatedSkills = updatedSkills.map(skill => {
        if (skill.id === draggedSkill.id) {
          return {
            ...skill,
            order: targetOrder
          }
        }

        // Shift other skills in the same group
        if (skill.group_id === draggedSkill.group_id && skill.id !== draggedSkill.id) {
          if (draggedOrder < targetOrder) {
            if (skill.order > draggedOrder && skill.order <= targetOrder) {
              return {
                ...skill,
                order: skill.order - 1
              }
            }
          } else {
            if (skill.order >= targetOrder && skill.order < draggedOrder) {
              return {
                ...skill,
                order: skill.order + 1
              }
            }
          }
        }

        return skill
      })
    } else if (shouldGroup && targetSkill) {
      // Group logic: create/extend group
      const newGroupId = targetSkill.group_id || `group-${Date.now()}`

      // If dragging from one group to another, remove from old group
      const wasInGroup = draggedSkill.group_id !== null

      // Update both skills to be in the same group
      updatedSkills = updatedSkills.map(skill => {
        if (skill.id === draggedSkill.id) {
          return {
            ...skill,
            group_id: newGroupId,
            order: targetSkill.order + 1,
            delay_after: skill.delay_after || 0
          }
        }
        if (skill.id === targetSkill.id && !skill.group_id) {
          return {
            ...skill,
            group_id: newGroupId,
            delay_after: skill.delay_after || 0
          }
        }
        // Shift orders for skills after the target
        if (skill.order > targetSkill.order) {
          return {
            ...skill,
            order: skill.order + 1
          }
        }
        return skill
      })

      // If the dragged skill was the last one in its old group, ungroup remaining skill
      if (wasInGroup && draggedSkill.group_id !== newGroupId) {
        const oldGroupId = draggedSkill.group_id
        const remainingInOldGroup = updatedSkills.filter(s => s.group_id === oldGroupId)

        if (remainingInOldGroup.length === 1) {
          // Ungroup the last remaining skill
          updatedSkills = updatedSkills.map(skill => {
            if (skill.group_id === oldGroupId) {
              return {
                ...skill,
                group_id: null,
                delay_after: 0
              }
            }
            return skill
          })
        }
      }
    } else if (targetSkill) {
      // Reorder logic: change order and potentially ungroup
      const draggedOrder = draggedSkill.order || 0
      const targetOrder = targetSkill.order || 0
      const wasInGroup = draggedSkill.group_id !== null
      const oldGroupId = draggedSkill.group_id

      updatedSkills = updatedSkills.map(skill => {
        if (skill.id === draggedSkill.id) {
          return {
            ...skill,
            order: targetOrder,
            group_id: null,  // Ungroup when reordering outside group
            delay_after: 0
          }
        }

        // Shift other skills' orders
        if (draggedOrder < targetOrder) {
          if (skill.order > draggedOrder && skill.order <= targetOrder && skill.id !== draggedSkill.id) {
            return {
              ...skill,
              order: skill.order - 1
            }
          }
        } else {
          if (skill.order >= targetOrder && skill.order < draggedOrder && skill.id !== draggedSkill.id) {
            return {
              ...skill,
              order: skill.order + 1
            }
          }
        }

        return skill
      })

      // If the dragged skill was in a group, check if we need to ungroup remaining skill
      if (wasInGroup && oldGroupId) {
        const remainingInGroup = updatedSkills.filter(s => s.group_id === oldGroupId)

        if (remainingInGroup.length === 1) {
          // Ungroup the last remaining skill
          updatedSkills = updatedSkills.map(skill => {
            if (skill.group_id === oldGroupId) {
              return {
                ...skill,
                group_id: null,
                delay_after: 0
              }
            }
            return skill
          })
        }
      }
    }

    // Call backend to persist reordering
    if (onReorderSkills) {
      await onReorderSkills(updatedSkills)
    }

    handleDragEnd()
  }

  const handleDropAtBoundary = async (position) => {
    if (!dragState.draggingId) {
      handleDragEnd()
      return
    }

    const draggedSkill = skills.find(s => s.id === dragState.draggingId)
    if (!draggedSkill) {
      handleDragEnd()
      return
    }

    const wasInGroup = draggedSkill.group_id !== null
    const oldGroupId = draggedSkill.group_id

    let updatedSkills = [...skills]

    // Calculate new order based on position
    let newOrder
    if (position === 'top') {
      newOrder = -1 // Will be first after shifting
    } else {
      // 'bottom'
      const maxOrder = Math.max(...skills.map(s => s.order || 0))
      newOrder = maxOrder + 1
    }

    updatedSkills = updatedSkills.map(skill => {
      if (skill.id === draggedSkill.id) {
        return {
          ...skill,
          order: newOrder,
          group_id: null, // Ungroup when dropping at boundary
          delay_after: 0
        }
      }

      // Shift orders if needed
      if (position === 'top') {
        return {
          ...skill,
          order: skill.order + 1
        }
      }

      return skill
    })

    // If the dragged skill was in a group, check if we need to ungroup remaining skill
    if (wasInGroup && oldGroupId) {
      const remainingInGroup = updatedSkills.filter(s => s.group_id === oldGroupId)

      if (remainingInGroup.length === 1) {
        // Ungroup the last remaining skill
        updatedSkills = updatedSkills.map(skill => {
          if (skill.group_id === oldGroupId) {
            return {
              ...skill,
              group_id: null,
              delay_after: 0
            }
          }
          return skill
        })
      }
    }

    // Call backend to persist reordering
    if (onReorderSkills) {
      await onReorderSkills(updatedSkills)
    }

    handleDragEnd()
  }

  const handleDelayChange = async (skillId, delay) => {
    await onUpdateSkill(skillId, { delay_after: delay })
  }

  const addNewSkill = () => {
    onOpenNewSkillModal()
  }

  const items = groupedSkills()
  const draggedSkill = dragState.draggingId ? skills.find(s => s.id === dragState.draggingId) : null

  return (
    <div
      className="bg-gray-100 min-h-full relative"
      onMouseMove={handleMouseMove}
      onTouchMove={handleTouchMove}
      onMouseUp={handleDragEnd}
      onTouchEnd={handleTouchEnd}
    >
      <div className="px-4 py-4">
        <div className="flex flex-col gap-3 w-full">
          {items.length === 0 ? (
            // Empty state - only show the large add button
            <AddSkillButton onClick={addNewSkill} />
          ) : (
            // Skills list with add button at the end
            <>
              {/* Top drop zone - only show when cursor is near top */}
              {dragState.showTopBoundary && (
                <DropZone
                  isVisible={true}
                  willGroup={false}
                  onDrop={(e) => {
                    e.preventDefault()
                    handleDropAtBoundary('top')
                  }}
                />
              )}

              {items.map((item) => {
                if (item.type === 'group') {
                  const firstSkillId = item.skills[0]?.id
                  const draggedSkill = dragState.draggingId ? skills.find(s => s.id === dragState.draggingId) : null
                  const isDraggedFromThisGroup = draggedSkill && item.skills.some(s => s.id === dragState.draggingId)
                  const showDropZoneBeforeGroup = dragState.draggingId && dragState.dragOverId === firstSkillId && !isDraggedFromThisGroup

                  return (
                    <div key={item.groupId} className="transition-all duration-300 ease-out">
                      {showDropZoneBeforeGroup && (
                        <DropZone
                          isVisible={true}
                          willGroup={dragState.shouldGroup}
                          onDrop={(e) => {
                            e.preventDefault()
                            handleDrop(firstSkillId, false)
                          }}
                        />
                      )}

                      <div
                        data-skill-id={firstSkillId}
                        className={`transition-all duration-300 ease-out ${
                          dragState.dragOverId === firstSkillId && dragState.shouldGroup
                            ? 'ring-2 ring-blue-400 ring-offset-2 rounded-[4px] shadow-lg'
                            : ''
                        }`}
                        onDragOver={(e) => handleDragOver(firstSkillId, e)}
                        onDrop={(e) => {
                          e.preventDefault()
                          handleDrop(firstSkillId, dragState.shouldGroup)
                        }}
                      >
                        <SkillGroup
                          skills={item.skills}
                          groupId={item.groupId}
                          onUpdateSkill={onUpdateSkill}
                          onEditSkill={onEditSkill}
                          onDeleteSkill={onDeleteSkill}
                          onDelayChange={handleDelayChange}
                          draggingSkillId={dragState.draggingId}
                          dragOverId={dragState.dragOverId}
                          onDragStart={handleDragStart}
                          onDragEnd={handleDragEnd}
                          onDragOver={handleDragOver}
                          onDrop={handleDrop}
                          onLongPressStart={handleLongPressStart}
                          onLongPressEnd={handleLongPressEnd}
                        />
                      </div>
                    </div>
                  )
                } else {
                  const skill = item.skill
                  const isDragging = dragState.draggingId === skill.id

                  return (
                    <div key={skill.id} className="transition-all duration-300 ease-out">
                      {dragState.draggingId && dragState.dragOverId === skill.id && (
                        <DropZone
                          isVisible={true}
                          willGroup={dragState.shouldGroup}
                          onDrop={(e) => {
                            e.preventDefault()
                            handleDrop(skill.id, false)
                          }}
                        />
                      )}

                      <div
                        data-skill-id={skill.id}
                        className={`transition-all duration-300 ease-out ${
                          isDragging ? 'opacity-30 scale-95' : ''
                        } ${
                          dragState.dragOverId === skill.id && dragState.shouldGroup
                            ? 'ring-2 ring-blue-400 ring-offset-2 rounded-[4px] shadow-lg'
                            : ''
                        }`}
                        onDragOver={(e) => handleDragOver(skill.id, e)}
                        onDrop={(e) => {
                          e.preventDefault()
                          handleDrop(skill.id, dragState.shouldGroup)
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
                          isDragging={false}
                          dragHandleProps={{
                            draggable: true,
                            onDragStart: (e) => handleDragStart(skill.id, e),
                            onDragEnd: handleDragEnd,
                            onTouchStart: (e) => {
                              e.preventDefault()
                              handleLongPressStart(skill.id, e)
                            },
                            onTouchEnd: (e) => {
                              e.preventDefault()
                              handleLongPressEnd()
                            }
                          }}
                        />
                      </div>
                    </div>
                  )
                }
              })}

              {/* Bottom drop zone - only show when cursor is near bottom */}
              {dragState.showBottomBoundary && (
                <DropZone
                  isVisible={true}
                  willGroup={false}
                  onDrop={(e) => {
                    e.preventDefault()
                    handleDropAtBoundary('bottom')
                  }}
                />
              )}

              <AddSkillButton onClick={addNewSkill} />
            </>
          )}
        </div>
      </div>

      {/* Floating drag preview that follows cursor/finger */}
      {draggedSkill && dragState.dragPosition && (
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: dragState.dragPosition.x - 180, // Center horizontally (approximate)
            top: dragState.dragPosition.y - 28, // Center vertically (approximate)
            width: '361px'
          }}
        >
          <SkillCell
            skillName={draggedSkill.name}
            variant={draggedSkill.variant}
            isOpen={false}
            isEnabled={draggedSkill.isEnabled}
            isSelected={draggedSkill.isSelected}
            onToggleSelect={() => {}}
            onToggleExpand={() => {}}
            onEdit={() => {}}
            onDelete={() => {}}
            keyReplacement={draggedSkill.keyReplacement}
            replaceRate={draggedSkill.replaceRate}
            frozenRotationDuringCasting={draggedSkill.frozenRotationDuringCasting}
            isDragging={true}
            dragHandleProps={{}}
            isInGroup={false}
          />
        </div>
      )}
    </div>
  )
}
