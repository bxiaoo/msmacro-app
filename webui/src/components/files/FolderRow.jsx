import React from 'react';
import FileRow from './FileRow.jsx';

export default function FolderRow({ node, depth, selSet, onToggleFile, onDeleteFolder, onRenameFolder, expanded, toggleExpanded }){
  const isOpen = expanded.has(node.rel);
  const files = (node.children||[]).filter(c=>c.type==='file');
  const subdirs = (node.children||[]).filter(c=>c.type==='dir');
  const selectedCount = files.reduce((n,f)=> n + (selSet.has(f.rel)?1:0), 0);
  const allSelected = files.length>0 && selectedCount===files.length;

  const selectAllHere = ()=>{
    const names = files.map(f=>f.rel);
    const s = new Set(selSet);
    const allIn = names.length>0 && names.every(x => s.has(x));
    if(allIn){ names.forEach(x => s.delete(x)); } else { names.forEach(x => s.add(x)); }
    // Use a custom event to bubble up selection change (keeps component lean)
    document.dispatchEvent(new CustomEvent('files:selection:update', { detail: Array.from(s) }));
  };

  return (
    <>
      <tr className="folder-row">
        <td className="col-check" onClick={(e)=>{ e.stopPropagation(); selectAllHere(); }}>
          <input type="checkbox" checked={allSelected} ref={el=>{ if(el) el.indeterminate = (selectedCount>0 && !allSelected); }} readOnly aria-label={`Select folder ${node.name}`} />
        </td>
        <td className="col-name" colSpan={2}>
          <div className="folder-name" style={{ paddingLeft: `${depth*16}px` }} onClick={()=>toggleExpanded(node.rel)}>
            <span className={`folder-caret ${isOpen? 'open':''}`}>▸</span>
            <span className="folder-icon">📁</span>
            <span className="folder-label">{node.name}</span>
            <span className="folder-meta">({files.length} files{ subdirs.length? `, ${subdirs.length} folders`: ''})</span>
          </div>
        </td>
        <td className="col-mtime">—</td>
        <td className="col-actions">
          <div className="file-actions">
            <button type="button" className="btn-link" onClick={(e)=>{ e.stopPropagation(); onRenameFolder(node); }}>Rename Folder</button>
            <button type="button" className="btn-link danger" title="Delete folder and all contents" onClick={(e)=>{ e.stopPropagation(); onDeleteFolder(node, true); }}>Delete Folder</button>
            <button type="button" className="btn-link" title="Delete folder if empty" onClick={(e)=>{ e.stopPropagation(); onDeleteFolder(node, false); }}>Delete Empty</button>
          </div>
        </td>
      </tr>
      {isOpen && (
        <>
          {files.map((f,i)=>(
            <FileRow key={`f-${f.rel}-${i}`} file={f} selected={selSet.has(f.rel)} onToggle={onToggleFile} onRename={(file)=>onRenameFolder(null,file)} onDelete={(file)=>onDeleteFolder(null,null,file)} />
          ))}
          {subdirs.map((d,i)=>(
            <FolderRow key={`d-${d.rel}-${i}`} node={d} depth={depth+1} selSet={selSet} onToggleFile={onToggleFile} onDeleteFolder={onDeleteFolder} onRenameFolder={onRenameFolder} expanded={expanded} toggleExpanded={toggleExpanded} />
          ))}
        </>
      )}
    </>
  );
}
