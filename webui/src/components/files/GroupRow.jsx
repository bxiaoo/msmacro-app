import React from 'react';
import FolderRow from './FolderRow.jsx';
import FileRow from './FileRow.jsx';

export default function GroupRow({ dir, selSet, onToggleFile, onDeleteFolder, onRenameFolder, expandedTop, toggleTop }){
  const open = expandedTop.has(dir.rel);
  const files = (dir.children||[]).filter(c=>c.type==='file');
  const subdirs = (dir.children||[]).filter(c=>c.type==='dir');
  const selectedCount = files.reduce((n,f)=> n + (selSet.has(f.rel)?1:0), 0);
  const allSelected = files.length>0 && selectedCount===files.length;

  const selectAllHere = ()=>{
    const names = files.map(f=>f.rel);
    const s = new Set(selSet);
    const allIn = names.length>0 && names.every(x => s.has(x));
    if(allIn){ names.forEach(x => s.delete(x)); } else { names.forEach(x => s.add(x)); }
    document.dispatchEvent(new CustomEvent('files:selection:update', { detail: Array.from(s) }));
  };

  return (
    <tbody>
      <tr className="group-row">
        <td className="col-check" onClick={(e)=>{ e.stopPropagation(); selectAllHere(); }}>
          <input type="checkbox" checked={allSelected} ref={el=>{ if(el) el.indeterminate = (selectedCount>0 && !allSelected); }} readOnly aria-label={`Select group ${dir.name}`} />
        </td>
        <td className="col-name" colSpan={2}>
          <div className="group-name" onClick={()=>toggleTop(dir.rel)}>
            <span className={`group-caret ${open? 'open':''}`}>▸</span>
            <span className="group-icon">📁</span>
            <span className="group-label">{dir.name}</span>
            <span className="group-meta">({files.length} files{ subdirs.length? `, ${subdirs.length} folders`: ''})</span>
          </div>
        </td>
        <td className="col-mtime">—</td>
        <td className="col-actions">
          <div className="file-actions">
            <button type="button" className="btn-link" onClick={(e)=>{ e.stopPropagation(); onRenameFolder(dir); }}>Rename Folder</button>
            <button type="button" className="btn-link danger" title="Delete folder and all contents" onClick={(e)=>{ e.stopPropagation(); onDeleteFolder(dir, true); }}>Delete Folder</button>
            <button type="button" className="btn-link" title="Delete folder if empty" onClick={(e)=>{ e.stopPropagation(); onDeleteFolder(dir, false); }}>Delete Empty</button>
          </div>
        </td>
      </tr>

      {open && (
        <>
          {files.map((f,i)=> (
            <FileRow key={`f-${f.rel}-${i}`} file={f} selected={selSet.has(f.rel)} onToggle={onToggleFile} onRename={(file)=>onRenameFolder(null,file)} onDelete={(file)=>onDeleteFolder(null,null,file)} />
          ))}
          {subdirs.map((d,i)=> (
            <FolderRow key={`d-${d.rel}-${i}`} node={d} depth={1} selSet={selSet} onToggleFile={onToggleFile} onDeleteFolder={onDeleteFolder} onRenameFolder={onRenameFolder} expanded={expandedTop /* reuse set for simplicity */} toggleExpanded={toggleTop} />
          ))}
        </>
      )}
    </tbody>
  );
}
