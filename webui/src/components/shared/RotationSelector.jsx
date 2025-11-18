import { useState, useEffect, useMemo } from 'react'
import { getStatus } from '../../api'
import { buildTree, flattenFiles } from '../../hooks/useFileTree'
import { MacroItem } from '../rotations/MacroItem'

/**
 * Reusable rotation selector component with checkbox-based multi-selection
 * @param {string[]} selectedRotations - Array of selected rotation file names
 * @param {function} onChange - Callback when selection changes: (newSelection: string[]) => void
 * @param {boolean} showActions - Whether to show edit/delete actions (default: false)
 */
export function RotationSelector({
  selectedRotations = [],
  onChange,
  showActions = false
}) {
  const [tree, setTree] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedFolders, setExpandedFolders] = useState(new Set())

  // Load available rotations on mount
  useEffect(() => {
    const loadRotations = async () => {
      try {
        setLoading(true)
        setError(null)
        // Use getStatus() API like the Rotations tab does
        const st = await getStatus()
        const items = Array.isArray(st?.tree) ? st.tree : []

        // Build tree structure (keep hierarchy, don't flatten)
        const builtTree = buildTree(items)
        setTree(builtTree)
      } catch (err) {
        console.error('[RotationSelector] Failed to load rotations:', err)
        setError(err.message || 'Failed to load rotations')
        setTree([])
      } finally {
        setLoading(false)
      }
    }

    loadRotations()
  }, [])

  // Flatten tree to get all files (for folder logic calculations)
  const allFiles = useMemo(() => flattenFiles(tree), [tree])

  // Toggle folder expand/collapse
  const toggleFolder = (folderRel) => {
    const s = new Set(expandedFolders)
    if (s.has(folderRel)) s.delete(folderRel)
    else s.add(folderRel)
    setExpandedFolders(s)
  }

  // Calculate folder checkbox state (tri-state: empty/indeterminate/checked)
  const getFolderCheckboxState = (folderRel) => {
    // Get only files directly in this folder (not in subfolders)
    const folderFiles = allFiles.filter(f => {
      const filePath = f.rel
      const folderPath = folderRel + '/'
      return filePath.startsWith(folderPath) &&
             !filePath.substring(folderPath.length).includes('/')
    })

    if (folderFiles.length === 0) {
      return { checked: false, indeterminate: false }
    }

    const selectedCount = folderFiles.filter(f =>
      selectedRotations.includes(f.rel)
    ).length

    if (selectedCount === 0) return { checked: false, indeterminate: false }
    if (selectedCount === folderFiles.length) return { checked: true, indeterminate: false }
    return { checked: false, indeterminate: true }
  }

  // Toggle folder selection (select/deselect all files in folder)
  const toggleFolderFiles = (folderRel) => {
    // Get only files directly in this folder (not in subfolders)
    const folderFiles = allFiles.filter(f => {
      const filePath = f.rel
      const folderPath = folderRel + '/'
      return filePath.startsWith(folderPath) &&
             !filePath.substring(folderPath.length).includes('/')
    })

    const folderFileRels = folderFiles.map(f => f.rel)
    const allSelected = folderFileRels.length > 0 &&
                        folderFileRels.every(rel => selectedRotations.includes(rel))

    if (allSelected) {
      // Deselect all files in folder
      onChange(selectedRotations.filter(r => !folderFileRels.includes(r)))
    } else {
      // Select all files in folder
      onChange([...new Set([...selectedRotations, ...folderFileRels])])
    }
  }

  const handleToggle = (rotationPath) => {
    const currentSelection = Array.isArray(selectedRotations) ? selectedRotations : []

    if (currentSelection.includes(rotationPath)) {
      // Remove from selection
      onChange(currentSelection.filter(r => r !== rotationPath))
    } else {
      // Add to selection
      onChange([...currentSelection, rotationPath])
    }
  }

  if (loading) {
    return (
      <div className="bg-gray-50 rounded p-4 text-center text-gray-500 text-sm">
        Loading rotations...
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4 text-center">
        <p className="text-red-800 font-semibold text-sm">Failed to load rotations</p>
        <p className="text-red-600 text-xs mt-1">{error}</p>
      </div>
    )
  }

  if (tree.length === 0) {
    return (
      <div className="bg-gray-50 rounded p-4 text-center text-gray-500 text-sm">
        No rotations available
      </div>
    )
  }

  const safeSelectedRotations = Array.isArray(selectedRotations) ? selectedRotations : []

  return (
    <div className="bg-gray-100 min-h-full">
      <div className="px-4 py-4">
        <div className="flex flex-col gap-3 w-full">
          {/* Root-level files (not in any folder) */}
          {tree
            .filter(node => node.type === 'file')
            .map(file => (
              <MacroItem
                key={file.rel}
                name={file.name}
                type="file"
                checked={safeSelectedRotations.includes(file.rel)}
                onCheckChange={() => handleToggle(file.rel)}
              />
            ))}

          {/* Folders */}
          {tree
            .filter(node => node.type === 'dir')
            .map(dir => {
              const folderState = getFolderCheckboxState(dir.rel)
              const isExpanded = expandedFolders.has(dir.rel)

              return (
                <div
                  key={dir.rel}
                  className="bg-gray-200 rounded-[4px] shadow-sm"
                >
                  {/* Folder header */}
                  <MacroItem
                    name={dir.name}
                    type="folder"
                    checked={folderState.checked}
                    indeterminate={folderState.indeterminate}
                    isExpanded={isExpanded}
                    onCheckChange={() => toggleFolderFiles(dir.rel)}
                    onToggleExpand={() => toggleFolder(dir.rel)}
                  />

                  {/* Folder contents (when expanded) */}
                  {isExpanded && (
                    <>
                      {(dir.children || [])
                        .filter(child => child.type === 'file')
                        .map(file => (
                          <MacroItem
                            key={file.rel}
                            name={file.name}
                            type="file"
                            checked={safeSelectedRotations.includes(file.rel)}
                            onCheckChange={() => handleToggle(file.rel)}
                          />
                        ))}
                    </>
                  )}
                </div>
              )
            })}
        </div>
      </div>
    </div>
  )
}
