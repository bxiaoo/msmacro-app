import * as React from 'react'
import { getStatus, renameFile, deleteFile, deleteFolder } from '../../api.js'
import { buildTree, flattenFiles } from '../../hooks/useFileTree.js'
import { dirname, basename, ensureJson, joinPath } from '../../utils/paths.js'
import { MacroItem } from "./MacroItem";

export function MacroList({ onSelectedChange }){
  const [tree, setTree] = React.useState([])
  const [selected, setSelected] = React.useState([])

  const refresh = React.useCallback(async ()=>{
    try{
      const st = await getStatus()
      const items = Array.isArray(st?.tree) ? st.tree : []
      const t = buildTree(items)
      setTree(prevTree => {
        // Only update if tree actually changed
        if (JSON.stringify(prevTree) === JSON.stringify(t)) return prevTree
        return t
      })
      // prune selection to only existing files after refresh
      const all = new Set(flattenFiles(t).map(f=>f.rel))
      setSelected(prev => prev.filter(r => all.has(r)))
    }catch(e){
      console.error('Failed to refresh file tree:', e)
    }
  },[])

  React.useEffect(()=>{ refresh() }, [refresh])

  // Listen for file refresh events from App (after CRUD operations)
  React.useEffect(() => {
    const onRefresh = () => refresh()
    document.addEventListener('files:refresh', onRefresh)
    return () => document.removeEventListener('files:refresh', onRefresh)
  }, [refresh])

  // 🔄 Emit selection to parent listeners (App → Controls) on every change
  React.useEffect(()=>{
    document.dispatchEvent(new CustomEvent('files:selection:set', { detail: selected }))
    onSelectedChange?.(selected)
  }, [selected, onSelectedChange])

  // Memoize flattened files for performance
  const allFiles = React.useMemo(() => flattenFiles(tree), [tree])

  const toggleFile = (rel)=>{
    const s = new Set(selected)
    if(s.has(rel)) s.delete(rel); else s.add(rel)
    const next = Array.from(s)
    setSelected(next) // useEffect above emits the event
  }

  // Handle folder selection - selects all files directly in folder (not subfolders)
  const toggleFolderFiles = React.useCallback((folderRel)=>{
    // Get only files directly in this folder (not in subfolders)
    const folderFiles = allFiles.filter(f => {
      const filePath = f.rel
      const folderPath = folderRel + '/'
      return filePath.startsWith(folderPath) && !filePath.substring(folderPath.length).includes('/')
    })
    
    const s = new Set(selected)
    const folderFileRels = folderFiles.map(f => f.rel)
    const allFolderFilesSelected = folderFileRels.length > 0 && folderFileRels.every(rel => s.has(rel))
    
    if (allFolderFilesSelected) {
      // Unselect all files in this folder
      folderFileRels.forEach(rel => s.delete(rel))
    } else {
      // Select all files in this folder
      folderFileRels.forEach(rel => s.add(rel))
    }
    
    setSelected(Array.from(s))
  }, [allFiles, selected])
  
  // Calculate folder checkbox state
  const getFolderCheckboxState = React.useCallback((folderRel) => {
    // Get only files directly in this folder (not in subfolders)
    const folderFiles = allFiles.filter(f => {
      const filePath = f.rel
      const folderPath = folderRel + '/'
      return filePath.startsWith(folderPath) && !filePath.substring(folderPath.length).includes('/')
    })
    
    if (folderFiles.length === 0) return { checked: false, indeterminate: false }
    
    const folderFileRels = folderFiles.map(f => f.rel)
    const selectedCount = folderFileRels.filter(rel => selected.includes(rel)).length
    
    if (selectedCount === 0) return { checked: false, indeterminate: false }
    if (selectedCount === folderFileRels.length) return { checked: true, indeterminate: false }
    return { checked: false, indeterminate: true }
  }, [allFiles, selected])

  // ----- Actions (unchanged) -----
  const doRenameFile = async (file)=>{
    const suggest = file.rel
    const input = prompt('New name (subfolders allowed):', suggest)
    if(!input) return
    let base = input
    if(!/\.json$/i.test(base)) base = `${base}.json`
    if(!base.includes('/')){
      const parent = dirname(file.rel)
      base = parent? joinPath(parent, base) : base
    }
    await renameFile(file.rel, base)
    setSelected(prev => prev.filter(x => x !== file.rel))
    await refresh()
  }

  const doRenameFolder = async (folderNodeOrNull, fileIfAny)=>{
    if(fileIfAny){ return doRenameFile(fileIfAny) }
    const node = folderNodeOrNull; if(!node) return
    const oldPrefix = node.rel
    const input = prompt('Rename folder to:', node.name)
    if(!input) return
    const parent = dirname(oldPrefix)
    const newPrefix = parent? joinPath(parent, input) : input
    const collect = (n)=> n.flatMap(x => x.type==='file'? [x] : collect(x.children||[]))
    const subtreeFiles = collect([node])
    for(const f of subtreeFiles){
      const relNew = f.rel.replace(new RegExp(`^${oldPrefix}/`), `${newPrefix}/`)
      await renameFile(f.rel, ensureJson(relNew))
    }
    await refresh()
  }

  const doDeleteFile = async (file)=>{
    if(!confirm(`Delete ${basename(file.rel)}?`)) return
    await deleteFile(file.rel)
    setSelected(prev => prev.filter(x => x !== file.rel))
    await refresh()
  }

  const doDeleteFolder = async (folderNodeOrNull, recursive, fileIfAny)=>{
    if(fileIfAny){ return doDeleteFile(fileIfAny) }
    const node = folderNodeOrNull; if(!node) return
    if(recursive){
      const ok = confirm(`Delete folder \"${node.rel}\" and ALL its contents?`)
      if(!ok) return
    }
    await deleteFolder(node.rel, !!recursive)
    setSelected(prev => prev.filter(x => !x.startsWith(`${node.rel}/`)))
    await refresh()
  }

  const selSet = new Set(selected||[]);
  const [expandedTop, setExpandedTop] = React.useState(new Set())

  const toggleTop = (rel)=>{
    const s = new Set(expandedTop); if(s.has(rel)) s.delete(rel); else s.add(rel); setExpandedTop(s);
  };


  return (
    <div className="bg-gray-100 min-h-full">
      <div className="px-4 py-4">
        {/* Content area */}
        <div className="flex flex-col gap-3 w-full">
          {/* Root files (none in most setups, but supported) */}
          {tree.filter(n=>n.type==='file').map((file,i)=> (
            <div key={`rf-${file.rel}-${i}`} className="w-full">
              <div className="content-stretch flex flex-col items-start justify-start overflow-clip relative rounded-[4px] shrink-0 w-full">
                <MacroItem
                  name={file.name}
                  type="file"
                  checked={selSet.has(file.rel)}
                  onCheckChange={() => toggleFile(file.rel)}
                  onEdit={() => doRenameFile(file)}
                  onDelete={() => doDeleteFile(file)}
                />
              </div>
            </div>
          ))}

          {/* Top-level folders */}
          {tree.filter(n=>n.type==='dir').map((dir)=> (
            <div key={`g-${dir.rel}`} className="w-full">
              <div className="content-stretch flex flex-col items-start justify-start overflow-clip relative rounded-[4px] shrink-0 w-full">
                <div className="bg-gray-200 box-border content-stretch flex flex-col items-start justify-start overflow-clip relative rounded-[4px] shadow-[0px_1px_2px_0px_rgba(0,0,0,0.05)] shrink-0 w-full">
                  {(() => {
                    const folderState = getFolderCheckboxState(dir.rel)
                    return (
                      <MacroItem
                        name={dir.name}
                        type="folder"
                        checked={folderState.checked}
                        indeterminate={folderState.indeterminate}
                        isExpanded={expandedTop.has(dir.rel)}
                        onCheckChange={() => toggleFolderFiles(dir.rel)}
                        onToggleExpand={() => toggleTop(dir.rel)}
                        onEdit={() => doRenameFolder(dir)}
                        onDelete={() => doDeleteFolder(dir, true)}
                      />
                    )
                  })()}

                  {expandedTop.has(dir.rel) && (
                    <>
                      {(dir.children||[]).filter(c=>c.type==='file').map((file,i)=> (
                        <MacroItem
                          key={`f-${file.rel}-${i}`}
                          name={file.name}
                          type="file"
                          checked={selSet.has(file.rel)}
                          onCheckChange={() => toggleFile(file.rel)}
                          onEdit={() => doRenameFile(file)}
                          onDelete={() => doDeleteFile(file)}
                        />
                      ))}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}