import { useDroppable } from '@dnd-kit/core'

/**
 * DropLine - Unified drop zone indicator for drag-and-drop reordering
 *
 * @param {string} id - The droppable ID (can include prefixes like 'before:', 'before-in:', etc.)
 * @param {boolean} isActive - Whether this drop line is currently being hovered over
 * @param {string} variant - Visual variant: 'default' for list gaps, 'in-group' for within groups
 */
export function DropLine({ id, isActive, variant = 'default' }) {
  const { setNodeRef } = useDroppable({ id })

  // Variant-specific styling
  const heightClass = variant === 'in-group'
    ? 'h-0' // In-group lines don't expand, they overlay
    : isActive ? 'h-[12px]' : 'h-0' // List lines expand when active

  const lineHeight = variant === 'in-group' ? 'h-[2px]' : 'h-[3px]'
  const lineColor = isActive ? 'bg-blue-500' : 'bg-transparent'

  return (
    <div
      ref={setNodeRef}
      className={`relative shrink-0 w-full flex items-center justify-center transition-all duration-150 ease-out ${heightClass}`}
    >
      <div
        aria-hidden="true"
        className={`w-full ${lineHeight} rounded-full transition-all duration-150 mx-3 ${lineColor}`}
      />
    </div>
  )
}
