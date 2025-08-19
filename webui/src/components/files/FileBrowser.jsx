
import React from 'react'
import { getStatus, renameFile, deleteFile, deleteFolder } from '../../api.js'
import { buildTree, flattenFiles } from '../../hooks/useFileTree.js'
import { dirname, basename, ensureJson, joinPath } from '../../utils/paths.js'
import TreeTable from './TreeTable.jsx'

export default function FileBrowser(){
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [tree, setTree] = React.useState([])
  const [filter, setFilter] = React.useState('')
  const [selected, setSelected] = React.useState([])

  const refresh = React.useCallback(async ()=>{
    setLoading(true); setError('')
    try{
      const st = await getStatus()
      const items = Array.isArray(st?.tree) ? st.tree : []
      const t = buildTree(items)
      setTree(t)
      // prune selection to only existing files after refresh
      const all = new Set(flattenFiles(t).map(f=>f.rel))
      setSelected(prev => prev.filter(r => all.has(r)))
    }catch(e){
      setError(String(e?.message || e))
    }finally{
      setLoading(false)
    }
  },[])

  React.useEffect(()=>{ refresh() }, [refresh])

  // 🔄 Emit selection to parent listeners (App → Controls) on every change
  React.useEffect(()=>{
    document.dispatchEvent(new CustomEvent('files:selection:set', { detail: selected }))
  }, [selected])

  const toggleFile = (rel)=>{
    const s = new Set(selected)
    if(s.has(rel)) s.delete(rel); else s.add(rel)
    const next = Array.from(s)
    setSelected(next) // useEffect above emits the event
  }

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

  const deleteSelected = async ()=>{
    if(!selected.length) return
    if(!confirm(`Delete ${selected.length} file(s)?`)) return
    for(const rel of selected){ await deleteFile(rel) }
    setSelected([])
    await refresh()
  }

  return (
    <div className="card files-card">
      <div className="files-header">
        <h3 className="files-title">Recordings</h3>
        <div style={{ display:'flex', gap:'.5rem', alignItems:'center' }}>
          <div className="search-container">
            <input className="search-input" placeholder="Search..." value={filter} onChange={(e)=> setFilter(e.target.value)} />
            <div className="search-icon">🔍</div>
          </div>
          <button type="button" className="btn btn-play" onClick={refresh} disabled={loading}>Refresh</button>
          <button type="button" className="btn btn-stop" onClick={deleteSelected} disabled={!selected.length}>Delete Selected</button>
        </div>
      </div>

      <TreeTable
        tree={tree}
        selected={selected}
        toggleFile={toggleFile}
        deleteFolder={doDeleteFolder}
        renameFolder={doRenameFolder}
        filter={filter}
      />
    </div>
  )
}
