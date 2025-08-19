import React from 'react';
import GroupRow from './GroupRow.jsx';
import FileRow from './FileRow.jsx';

export default function TreeTable({ tree, selected, toggleFile, deleteFolder, renameFolder, filter }){
  const selSet = new Set(selected||[]);
  const [expandedTop, setExpandedTop] = React.useState(new Set());

  const toggleTop = (rel)=>{
    const s = new Set(expandedTop); if(s.has(rel)) s.delete(rel); else s.add(rel); setExpandedTop(s);
  };

  // Bubble selection updates from child components
  React.useEffect(()=>{
    const handler = (e)=>{
      if(Array.isArray(e.detail)){
        // propagate to top owner via a synthetic event (keeps prop surface small)
        document.dispatchEvent(new CustomEvent('files:selection:set', { detail: e.detail }));
      }
    };
    document.addEventListener('files:selection:update', handler);
    return ()=> document.removeEventListener('files:selection:update', handler);
  },[]);

  const visibleFiles = React.useMemo(()=>{
    if(!filter) return null;
    const q = filter.toLowerCase();
    const dfs = (nodes)=> nodes.flatMap(n => n.type==='file' ? [n] : dfs(n.children||[]));
    return dfs(tree).filter(f => f.rel.toLowerCase().includes(q));
  }, [tree, filter]);

  const allVisibleChecked = React.useMemo(()=>{
    const names = (visibleFiles? visibleFiles : tree.flatMap(n => n.type==='file'? [n] : [])).map(f=>f.rel);
    return names.length>0 && names.every(x => selSet.has(x));
  }, [visibleFiles, tree, selected]);

  const toggleAllVisible = ()=>{
    const names = (visibleFiles? visibleFiles : tree.flatMap(n => n.type==='file'? [n] : [])).map(f=>f.rel);
    const s = new Set(selSet);
    const allIn = names.length>0 && names.every(x => s.has(x));
    if(allIn){ names.forEach(x=>s.delete(x)); } else { names.forEach(x=>s.add(x)); }
    document.dispatchEvent(new CustomEvent('files:selection:set', { detail: Array.from(s) }));
  };

  return (
    <div className="files-table-container">
      <table className="files-table">
        <thead>
          <tr>
            <th className="col-check">
              <input type="checkbox" aria-label="Select all visible" checked={allVisibleChecked} onChange={toggleAllVisible} />
            </th>
            <th>Name</th>
            <th>Size</th>
            <th>Modified</th>
            <th>Actions</th>
          </tr>
        </thead>

        {filter ? (
          <tbody>
            {visibleFiles && visibleFiles.length ? visibleFiles.map((f,i)=> (
              <FileRow key={`ff-${f.rel}-${i}`} file={f} selected={selSet.has(f.rel)} onToggle={toggleFile} onRename={(file)=>renameFolder(null,file)} onDelete={(file)=>deleteFolder(null,null,file)} />
            )) : (
              <tr><td colSpan={5} style={{ padding:'1rem 1.5rem', color:'#6b7280' }}>No matches.</td></tr>
            )}
          </tbody>
        ) : (
          <>
            {/* Root files (none in most setups, but supported) */}
            <tbody>
              {tree.filter(n=>n.type==='file').map((f,i)=> (
                <FileRow key={`rf-${f.rel}-${i}`} file={f} selected={selSet.has(f.rel)} onToggle={toggleFile} onRename={(file)=>renameFolder(null,file)} onDelete={(file)=>deleteFolder(null,null,file)} />
              ))}
            </tbody>

            {/* Top-level folders */}
            {tree.filter(n=>n.type==='dir').map((dir)=> (
              <GroupRow key={`g-${dir.rel}`} dir={dir} selSet={selSet} onToggleFile={toggleFile} onDeleteFolder={deleteFolder} onRenameFolder={renameFolder} expandedTop={expandedTop} toggleTop={toggleTop} />
            ))}
          </>
        )}
      </table>
    </div>
  );
}
