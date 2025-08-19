import { useEffect, useMemo, useState } from 'react'
import { renameFile, deleteFile, deleteFolder } from '../api.js'

function formatBytes(n){
  if(!Number.isFinite(n)) return '-'
  const u=['B','KB','MB','GB']
  let i=0, v=n
  while(v>=1024 && i<u.length-1){ v/=1024; i++ }
  return `${v.toFixed(i===0?0:1)} ${u[i]}`
}

function basename(rel){ const p=(rel||'').split('/'); return p[p.length-1]||rel }

const withJson = (s) => s && !/\.json$/i.test(s) ? `${s}.json` : s;
function buildTreeFromFlat(files = []) {
  const ROOT = new Map()

  // Pre-scan absolute 'path' fields to learn what to strip
  const pathPartsList = files
    .map(f => String(f.path || '').trim())
    .filter(p => p.startsWith('/'))
    .map(p => p.split('/').filter(Boolean));

  // Prefer cutting after ".../records/"
  const idxOfRecords = Math.max(-1, ...pathPartsList.map(parts => parts.lastIndexOf('records')));
  // Fallback: longest common directory prefix
  const commonPrefix = (() => {
    if (!pathPartsList.length) return [];
    const first = pathPartsList[0];
    let i = 0;
    for (; i < first.length; i++) {
      const seg = first[i];
      if (!pathPartsList.every(parts => parts[i] === seg)) break;
    }
    return first.slice(0, i);
  })();

  const stripBase = (absPath) => {
    if (!absPath) return '';
    const parts = String(absPath).split('/').filter(Boolean);
    if (idxOfRecords >= 0 && idxOfRecords < parts.length - 1) {
      // cut after ".../records"
      return parts.slice(idxOfRecords + 1).join('/');
    }
    if (commonPrefix.length && parts.length > commonPrefix.length) {
      // cut common directory prefix
      return parts.slice(commonPrefix.length).join('/');
    }
    // last resort: just drop leading slash elsewhere
    return parts.join('/');
  };

  const ensureDir = (parts) => {
    let cur = ROOT
    let path = ''
    for (const part of parts) {
      path = path ? `${path}/${part}` : part
      if (!cur.has(part)) {
        cur.set(part, { type:'dir', name: part, rel: path, children: new Map() })
      }
      const node = cur.get(part)
      cur = node.children
    }
    return cur
  }

  for (const raw of files) {
    let relStr = '';
    if (typeof raw === 'string') {
      relStr = raw;
    } else if (raw && typeof raw === 'object') {
      relStr = raw.name || raw.rel || '';
    }

    relStr = String(relStr).replace(/^\/+/, '');

    const relForApi = withJson(relStr);

    const rel = relForApi.split('/').filter(Boolean)
    if (!rel.length) continue

    const fileName = rel.pop()
    const dirMap = ensureDir(rel)
    dirMap.set(`__file__:${rel.concat(fileName).join('/')}`, {
      type:'file',
      name: fileName,
      rel: rel.length ? `${rel.join('/')}/${fileName}` : fileName,
      size: Number(raw.size || 0),
      mtime: Number(raw.mtime || 0),
    })
  }

  // convert Map structure to array nodes
  const toArray = (m) => {
    const out = []
    for (const [key, val] of m) {
      if (key.startsWith('__file__:')) out.push(val)
      else out.push({ ...val, children: toArray(val.children || new Map()) })
    }
    return out
  }
  return toArray(ROOT)
}

function normalizeTree(items, base=''){
  if(!Array.isArray(items)) return []
  const norm=[]
  for(const raw of items){
    const rtype = raw.type || raw.kind
    const name  = raw.name || ''
    const rel   = (raw.rel || (base ? `${base}/${name}` : name)).replace(/^\/+/, '')
    if((rtype === 'dir' || rtype === 'folder' || Array.isArray(raw.children))){
      const kids = normalizeTree(raw.children || [], rel)
      norm.push({ type:'dir', name: name || basename(rel), rel, children:kids })
    }else{
      norm.push({
        type:'file',
        name: name || basename(rel),
        rel,
        size: Number(raw.size || 0),
        mtime: Number(raw.mtime || 0),
      })
    }
  }
  norm.sort((a,b)=>{
    if(a.type !== b.type) return a.type==='dir' ? -1 : 1
    if(a.type==='dir') return (a.name||'').localeCompare(b.name||'')
    return (b.mtime - a.mtime) || (a.name||'').localeCompare(b.name||'')
  })
  return norm
}
function flattenFiles(nodes){
  const out=[]
  for(const n of nodes){
    if(n.type==='file') out.push(n)
    else if(n.type==='dir') out.push(...flattenFiles(n.children||[]))
  }
  return out
}
function buildGroups(normTree){
  const rootFiles = normTree.filter(n=>n.type==='file')
  const folderGroups = normTree.filter(n=>n.type==='dir')
  return { rootFiles, folderGroups }
}
function collectVisibleFiles(normTree, expandedGroups, expandedFolders, filter){
  if(filter){
    const q = filter.toLowerCase()
    return flattenFiles(normTree).filter(f => f.rel.toLowerCase().includes(q))
  }
  const vis=[]
  for (const n of normTree) if(n.type==='file') vis.push(n)
  for (const dir of normTree){
    if(dir.type!=='dir' || !expandedGroups.has(dir.rel)) continue
    for(const c of dir.children||[]){
      if(c.type==='file') vis.push(c)
    }
    const walk=(node)=>{
      for(const ch of node.children||[]){
        if(ch.type==='file') vis.push(ch)
        else if(ch.type==='dir' && expandedFolders.has(ch.rel)){
          walk(ch)
        }
      }
    }
    for(const c of dir.children||[]){
      if(c.type==='dir' && expandedFolders.has(c.rel)) walk(c)
    }
  }
  return vis
}

export default function FilesTable({ files, tree=[], selected=[], setSelected, onAfter }){
  const [filter,setFilter]=useState("")
  const [expandedGroups,setExpandedGroups]=useState(()=> new Set()) // top-level folders
  const [expandedFolders,setExpandedFolders]=useState(()=> new Set()) // nested

  const sourceTree = useMemo(() => {
    if (Array.isArray(tree) && tree.length) return tree
    if (Array.isArray(files) && files.length) return buildTreeFromFlat(files)
    return []
  }, [tree, files])

  const normTree = useMemo(()=> normalizeTree(sourceTree), [sourceTree])
  const { rootFiles, folderGroups } = useMemo(()=> buildGroups(normTree), [normTree])

  const allFiles     = useMemo(()=> flattenFiles(normTree), [normTree])
  const allFileNames = useMemo(()=> new Set(allFiles.map(f=>f.rel)), [allFiles])

  useEffect(()=>{
    if(!Array.isArray(selected)) return
    const pruned = selected.filter(n => allFileNames.has(n))
    if(pruned.length !== selected.length) setSelected(pruned)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFileNames])

  const visible = useMemo(
    ()=> collectVisibleFiles(normTree, expandedGroups, expandedFolders, filter),
    [normTree, expandedGroups, expandedFolders, filter]
  )

  const selSet = useMemo(()=> new Set(selected||[]), [selected])

  const toggleFile = (rel)=>{
    const s = new Set(selSet)
    if(s.has(rel)) s.delete(rel); else s.add(rel)
    setSelected(Array.from(s))
  }

  const toggleAllVisible = ()=>{
    const names = visible.map(f=>f.rel)
    const s = new Set(selSet)
    const allIn = names.length>0 && names.every(x => s.has(x))
    if(allIn){ names.forEach(x => s.delete(x)) } else { names.forEach(x => s.add(x)) }
    setSelected(Array.from(s))
  }

  const toggleGroup = (rel)=>{
    const s = new Set(expandedGroups)
    if(s.has(rel)) s.delete(rel); else s.add(rel)
    setExpandedGroups(s)
  }

  const toggleFolder = (rel)=>{
    const s = new Set(expandedFolders)
    if(s.has(rel)) s.delete(rel); else s.add(rel)
    setExpandedFolders(s)
  }

  const selectDesc = (nodes)=>{
    const desc = flattenFiles(nodes).map(f=>f.rel)
    const s = new Set(selSet)
    const allIn = desc.length>0 && desc.every(x => s.has(x))
    if(allIn){ desc.forEach(x => s.delete(x)) } else { desc.forEach(x => s.add(x)) }
    setSelected(Array.from(s))
  }

  // -------- actions --------

  const handleDeleteFolder = async (folderRel, recursive, affectedRels=[])=>{
    if(recursive){
      const ok = confirm("Delete this folder and ALL its contents?")
      if(!ok) return
    }
    await deleteFolder(folderRel, recursive)
    if(affectedRels.length){
      const s = new Set(selSet)
      affectedRels.forEach(r => s.delete(r))
      setSelected(Array.from(s))
    }
    onAfter?.()
  }

  // -------- row renderers --------

  const renderFileRow = (file, idx)=>{
    const dt = file.mtime ? new Date(file.mtime * 1000).toLocaleString() : "-"
    const isSelected = selSet.has(file.rel)
    return (
      <tr
        key={`f-${file.rel}-${idx}`}
        className={isSelected ? 'selected' : ''}
        onClick={(e)=>{
          if(e.target.closest && e.target.closest('.file-actions')) return
          toggleFile(file.rel)
        }}
      >
        <td className="col-check" onClick={e=>e.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={()=>toggleFile(file.rel)}
            aria-label={`Select ${file.name}`}
          />
        </td>
        <td className="col-name">
          <div className={`file-name ${isSelected ? 'selected' : ''}`}>
            <span className="file-icon">📄</span>
            <span className="file-label">{file.name}</span>
          </div>
        </td>
        <td className="col-size">
          <div className="file-info">{formatBytes(file.size)}</div>
        </td>
        <td className="col-mtime">
          <div className="file-info">{dt}</div>
        </td>
        <td className="col-actions">
          <div className="file-actions">
            <button
              type="button"
              onClick={async (e)=>{
                e.stopPropagation()
                const suggest = file.rel
                const input = prompt("new name (subfolders allowed):", suggest)
                if(!input) return
                const hasSlash = input.includes('/')
                const parent = file.rel.includes('/') ? file.rel.slice(0, file.rel.lastIndexOf("/")) : ''
                const base = hasSlash ? input : (parent ? `${parent}/${input}` : input)
                const finalNew = /\.json$/i.test(base) ? base : `${base}.json`
                await renameFile(file.rel, finalNew)
                onAfter?.()
              }}
              className="btn-link"
            >
              Rename
            </button>
            <button
              type="button"
              onClick={async (e)=>{
                e.stopPropagation()
                if(!confirm(`Delete ${file.name}?`)) return
                await deleteFile(file.rel)
                const s = new Set(selSet); s.delete(file.rel)
                setSelected(Array.from(s))
                onAfter?.()
              }}
              className="btn-link danger"
            >
              Delete
            </button>
          </div>
        </td>
      </tr>
    )
  }

  const renderFolderRow = (node, depth, idx)=>{
    const isOpen = expandedFolders.has(node.rel)
    const descFiles = flattenFiles([node])
    const fileRels = descFiles.map(f=>f.rel)
    const selectedCount = descFiles.filter(f => selSet.has(f.rel)).length
    const allSelected = selectedCount>0 && selectedCount===descFiles.length

    return (
      <>
        <tr key={`d-${node.rel}-${idx}`} className="folder-row">
          <td className="col-check" onClick={(e)=>{ e.stopPropagation(); selectDesc([node]) }}>
            <input
              type="checkbox"
              checked={allSelected}
              ref={el => { if(el) el.indeterminate = (selectedCount>0 && !allSelected) }}
              onChange={()=>selectDesc([node])}
              aria-label={`Select folder ${node.name}`}
            />
          </td>
          <td className="col-name" colSpan={2}>
            <div
              className="folder-name"
              style={{ paddingLeft: `${depth * 16}px` }}
              onClick={()=>toggleFolder(node.rel)}
              title={node.name}
            >
              <span className={`folder-caret ${isOpen ? 'open' : ''}`}>▸</span>
              <span className="folder-icon">📁</span>
              <span className="folder-label">{node.name}</span>
              <span className="folder-meta">({descFiles.length} items)</span>
            </div>
          </td>
          <td className="col-mtime">—</td>
          <td className="col-actions">
            <div className="file-actions">
              <button
                type="button"
                onClick={(e)=>{
                  e.stopPropagation()
                  handleDeleteFolder(node.rel, true, fileRels) // recursive
                }}
                className="btn-link danger"
                title="Delete folder and all contents"
              >
                Delete Folder
              </button>
              <button
                type="button"
                onClick={(e)=>{
                  e.stopPropagation()
                  handleDeleteFolder(node.rel, false, fileRels) // empty-only (will error if not empty)
                }}
                className="btn-link"
                title="Delete folder if empty"
              >
                Delete Empty
              </button>
            </div>
          </td>
        </tr>
        {isOpen && (node.children||[]).map((c, i) => (
          c.type==='file'
            ? renderFileRow(c, i)
            : renderFolderRow(c, depth+1, i)
        ))}
      </>
    )
  }

  const renderGroup = (dir)=>{
    const open = expandedGroups.has(dir.rel)
    const descFiles = flattenFiles([dir])
    const fileRels = descFiles.map(f=>f.rel)
    const selectedCount = descFiles.filter(f=>selSet.has(f.rel)).length
    const allSelected = selectedCount>0 && selectedCount===descFiles.length

    return (
      <tbody key={`g-${dir.rel}`}>
        <tr className="group-row">
          <td className="col-check" onClick={(e)=>{ e.stopPropagation(); selectDesc([dir]) }}>
            <input
              type="checkbox"
              checked={allSelected}
              ref={el => { if(el) el.indeterminate = (selectedCount>0 && !allSelected) }}
              onChange={()=>selectDesc([dir])}
              aria-label={`Select group ${dir.name}`}
            />
          </td>
          <td className="col-name" colSpan={2}>
            <div
              className="group-name"
              onClick={()=>toggleGroup(dir.rel)}
              title={dir.name}
            >
              <span className={`group-caret ${open ? 'open' : ''}`}>▸</span>
              <span className="group-icon">📁</span>
              <span className="group-label">{dir.name}</span>
              <span className="group-meta">({descFiles.length} items)</span>
            </div>
          </td>
          <td className="col-mtime">—</td>
          <td className="col-actions">
            <div className="file-actions">
              <button
                type="button"
                onClick={(e)=>{ e.stopPropagation(); handleDeleteFolder(dir.rel, true, fileRels) }}
                className="btn-link danger"
                title="Delete folder and all contents"
              >
                Delete Folder
              </button>
              <button
                type="button"
                onClick={(e)=>{ e.stopPropagation(); handleDeleteFolder(dir.rel, false, fileRels) }}
                className="btn-link"
                title="Delete folder if empty"
              >
                Delete Empty
              </button>
            </div>
          </td>
        </tr>

        {open && (
          <>
            {(dir.children||[]).filter(c=>c.type==='file').map((f,i)=> renderFileRow(f,i))}
            {(dir.children||[]).filter(c=>c.type==='dir').map((d,i)=> renderFolderRow(d, 1, i))}
          </>
        )}
      </tbody>
    )
  }

  const filteredFlatRows = filter
    ? visible.filter(n=>n.type==='file').map((f,i)=> renderFileRow(f,i))
    : null

  const allVisibleChecked = (() => {
    const names = visible.map(f=>f.rel)
    return names.length>0 && names.every(x => selSet.has(x))
  })()

  return (
    <div className="card files-card">
      <div className="files-header">
        <h3 className="files-title">Recordings</h3>
        <div className="search-container">
          <input
            type="text"
            placeholder="Search (shows flat matches)..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      <div className="files-table-container">
        <table className="files-table">
          <thead>
            <tr>
              <th className="col-check">
                <input
                  type="checkbox"
                  aria-label="Select all visible"
                  checked={allVisibleChecked}
                  onChange={toggleAllVisible}
                />
              </th>
              <th>Name</th>
              <th>Size</th>
              <th>Modified</th>
              <th>Actions</th>
            </tr>
          </thead>

          {filter ? (
            <tbody>
              {filteredFlatRows && filteredFlatRows.length ? filteredFlatRows : (
                <tr><td colSpan={5} style={{padding:'1rem 1.5rem', color:'#6b7280'}}>No matches.</td></tr>
              )}
            </tbody>
          ) : (
            <>
              <tbody>
                {rootFiles.length
                  ? rootFiles.map((f,i)=> renderFileRow(f,i))
                  : <tr><td colSpan={5} style={{padding:'0.75rem 1.5rem', color:'#6b7280'}}>No files in root.</td></tr>
                }
              </tbody>

              {folderGroups.length
                ? folderGroups.map(dir => renderGroup(dir))
                : <tbody><tr><td colSpan={5} style={{padding:'0.75rem 1.5rem', color:'#6b7280'}}>No subfolders.</td></tr></tbody>
              }
            </>
          )}
        </table>
      </div>
    </div>
  )
}
