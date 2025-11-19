import { useState, useMemo } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  closestCenter
} from '@dnd-kit/core'
import { Plus } from 'lucide-react'
import { SkillCell } from './SkillCell'
import { SkillGroup } from './SkillGroup'
import { DropLine } from '../ui/drop-line'
import { AddButton } from '../ui/add-button'



export function CDSkills({ skills, onOpenNewSkillModal, onEditSkill, onUpdateSkill, onDeleteSkill, onReorderSkills }) {
  const [activeId, setActiveId] = useState(null)
  const [overId, setOverId] = useState(null)

  // Configure sensors - only activate on drag handle (Menu icon)
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5, // Small movement threshold since we have explicit handle
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 200, // Short delay for touch
        tolerance: 5,
      },
    })
  )

  // Build mixed blocks (groups and singles) ordered by `order`
  const blocks = useMemo(() => {
    const sorted = [...skills].sort((a, b) => (a.order || 0) - (b.order || 0))
    const seen = new Set()
    const out = []
    for (const s of sorted) {
      if (s.groupId) {
        if (seen.has(s.groupId)) continue
        const members = sorted.filter(x => x.groupId === s.groupId)
        out.push({ type: 'group', groupId: s.groupId, skillIds: members.map(m => m.id) })
        seen.add(s.groupId)
      } else {
        out.push({ type: 'single', skillIds: [s.id] })
      }
    }
    return out
  }, [skills])

  // No SortableContext: using core Draggable/Droppable per cell

  const handleDragStart = (event) => {
    setActiveId(event.active.id)
  }

  const handleDragOver = (event) => {
    const { over } = event
    setOverId(over ? over.id : null)
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    const draggedId = active?.id
    const dropId = over?.id
    setActiveId(null)
    setOverId(null)

    if (!draggedId || !dropId) return
    if (draggedId === dropId) return

    // Clone current block structure
    const bs = blocks.map(b => ({ ...b, skillIds: [...b.skillIds] }))

    const findLoc = (id) => {
      for (let i = 0; i < bs.length; i++) {
        const j = bs[i].skillIds.findIndex(sid => String(sid) === String(id))
        if (j !== -1) return { i, j }
      }
      return null
    }

    const removeFromBlocks = (id) => {
      const loc = findLoc(id)
      if (!loc) return
      const b = bs[loc.i]
      b.skillIds.splice(loc.j, 1)
      if (b.type === 'group' && b.skillIds.length === 1) {
        const last = b.skillIds[0]
        bs.splice(loc.i, 1, { type: 'single', skillIds: [last] })
      } else if (b.type === 'single' && b.skillIds.length === 0) {
        bs.splice(loc.i, 1)
      }
    }

    const insertSingleBefore = (id, beforeSkillId) => {
      // Find the block containing beforeSkillId
      const idx = bs.findIndex(b =>
        b.skillIds.some(sid => String(sid) === String(beforeSkillId))
      )
      const block = { type: 'single', skillIds: [id] }
      if (idx === -1) bs.push(block)
      else bs.splice(idx, 0, block)
    }

    const insertIntoGroupBefore = (id, targetMemberId) => {
      for (const b of bs) {
        if (b.type === 'group') {
          const idx = b.skillIds.findIndex(sid => String(sid) === String(targetMemberId))
          if (idx !== -1) {
            b.skillIds.splice(idx, 0, id)
            return true
          }
        }
      }
      return false
    }

    const insertIntoGroupEnd = (id, groupId) => {
      const b = bs.find(x => x.type === 'group' && String(x.groupId) === String(groupId))
      if (b) b.skillIds.push(id)
      else insertSingleBefore(id, groupId) // fallback
    }

    const createGroupFromTwo = (aId, bId, atIdx) => {
      const gid = `group-${Date.now()}`
      bs.splice(atIdx, 1, { type: 'group', groupId: gid, skillIds: [aId, bId] })
    }

    // Remove dragged from its origin first
    removeFromBlocks(draggedId)

    // Interpret drop target
    if (typeof dropId === 'string' && dropId.startsWith('before:')) {
      const key = dropId.slice('before:'.length)
      insertSingleBefore(draggedId, key)
    } else if (typeof dropId === 'string' && dropId.startsWith('before-in:')) {
      const memberId = dropId.slice('before-in:'.length)
      if (!insertIntoGroupBefore(draggedId, memberId)) insertSingleBefore(draggedId, memberId)
    } else if (dropId === 'after-list') {
      bs.push({ type: 'single', skillIds: [draggedId] })
    } else if (typeof dropId === 'string' && dropId.startsWith('on-group:')) {
      const gid = dropId.slice('on-group:'.length)
      insertIntoGroupEnd(draggedId, gid)
    } else {
      // Dropped on skill cell id
      const target = skills.find(s => String(s.id) === String(dropId))
      if (target && String(target.id) !== String(draggedId)) {
        if (target.groupId) {
          // Target is in a group, add after it in the same group
          const b = bs.find(x => x.type === 'group' && String(x.groupId) === String(target.groupId))
          if (b) {
            const idx = b.skillIds.findIndex(sid => String(sid) === String(target.id))
            b.skillIds.splice(idx + 1, 0, draggedId)
          } else {
            insertSingleBefore(draggedId, target.id)
          }
        } else {
          // Target is a single skill, create group
          const atIdx = bs.findIndex(x => x.type === 'single' && String(x.skillIds[0]) === String(target.id))
          if (atIdx !== -1) {
            createGroupFromTwo(target.id, draggedId, atIdx)
          } else {
            insertSingleBefore(draggedId, target.id)
          }
        }
      }
    }

    // Produce updated skills
    const id2orig = new Map(skills.map(s => [s.id, s]))
    const updated = []
    let order = 0
    for (const b of bs) {
      if (b.type === 'single') {
        const id = b.skillIds[0]
        const orig = id2orig.get(id)
        if (orig) updated.push({ ...orig, order: order++, groupId: null, delayAfter: 0 })
      } else {
        for (const id of b.skillIds) {
          const orig = id2orig.get(id)
          if (orig) updated.push({ ...orig, order: order++, groupId: b.groupId, delayAfter: orig.delayAfter ?? 0 })
        }
      }
    }

    if (onReorderSkills) await onReorderSkills(updated)
  }

  const handleDelayChange = async (skillId, delay) => {
    await onUpdateSkill(skillId, { delayAfter: delay })
  }

  const addNewSkill = () => {
    onOpenNewSkillModal()
  }

  const items = blocks
  const activeSkill = activeId ? skills.find(s => s.id === activeId) : null

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="bg-gray-100 min-h-full relative">
        <div className="px-4 py-4">
            <div className="flex flex-col gap-3 w-full">
              {items.length === 0 ? (
                <AddButton onClick={addNewSkill} />
              ) : (
                <>
                  {items.map((item) => {
                    if (item.type === 'group') {
                      const groupFirstId = item.skillIds[0]

                      return (
                        <div key={item.groupId}>
                          {activeId && (
                            <DropLine id={`before:${groupFirstId}`} isActive={overId === `before:${groupFirstId}`} />
                          )}

                          <SkillGroup
                            skills={item.skillIds.map(id => skills.find(s => s.id === id)).filter(Boolean)}
                            groupId={item.groupId}
                            onUpdateSkill={onUpdateSkill}
                            onEditSkill={onEditSkill}
                            onDeleteSkill={onDeleteSkill}
                            onDelayChange={handleDelayChange}
                            draggingSkillId={activeId}
                            dragOverId={overId}
                          />
                        </div>
                      )
                    } else {
                      const skillId = item.skillIds[0]
                      const skill = skills.find(s => s.id === skillId)
                      if (!skill) return null
                      const isDragging = activeId === skill.id
                      const isHoveredForGrouping = !isDragging && activeId && overId === skill.id

                      return (
                        <div key={skill.id}>
                          {activeId && (
                            <DropLine id={`before:${skill.id}`} isActive={overId === `before:${skill.id}`} />
                          )}

                          <div className={`transition-all duration-150 ${isHoveredForGrouping ? 'ring-2 ring-green-500 ring-offset-2 rounded-[4px] shadow-lg' : ''}`}>
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
                              isDragging={isDragging}
                              isInGroup={false}
                            />
                          </div>
                        </div>
                      )
                    }
                  })}

                  <AddButton onClick={addNewSkill} />
                  {activeId && <DropLine id={'after-list'} isActive={overId === 'after-list'} />}
                </>
              )}
            </div>
        </div>
      </div>

      <DragOverlay dropAnimation={null}>
        {activeSkill ? (
          <div style={{ width: 'calc(100vw - 2rem)', maxWidth: '600px' }}>
            <div className="w-full">
              <SkillCell
                id={undefined}
                skillName={activeSkill.name}
                variant={activeSkill.variant}
                isOpen={false}
                isEnabled={activeSkill.isEnabled}
                isSelected={activeSkill.isSelected}
                onToggleSelect={() => {}}
                onToggleExpand={() => {}}
                onEdit={() => {}}
                onDelete={() => {}}
                keyReplacement={activeSkill.keyReplacement}
                replaceRate={activeSkill.replaceRate}
                frozenRotationDuringCasting={activeSkill.frozenRotationDuringCasting}
                isDragging={true}
                isInGroup={false}
              />
            </div>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
