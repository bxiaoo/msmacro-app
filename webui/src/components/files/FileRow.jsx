import React from 'react';
import { formatBytes, formatMTime } from '../../utils/format.js';

export default function FileRow({ file, selected, onToggle, onRename, onDelete }){
  return (
    <tr className={selected? 'selected': ''} onClick={(e)=>{
      if(e.target.closest && e.target.closest('.file-actions')) return;
      onToggle(file.rel);
    }}>
      <td className="col-check" onClick={(e)=>e.stopPropagation()}>
        <input type="checkbox" checked={selected} onChange={()=>onToggle(file.rel)} aria-label={`Select ${file.name}`} />
      </td>
      <td className="col-name">
        <div className={`file-name ${selected? 'selected':''}`}>
          <span className="file-icon">📄</span>
          <span className="file-label">{file.name}</span>
        </div>
      </td>
      <td className="col-size"><div className="file-info">{formatBytes(file.size)}</div></td>
      <td className="col-mtime"><div className="file-info">{formatMTime(file.mtime)}</div></td>
      <td className="col-actions">
        <div className="file-actions">
          <button type="button" className="btn-link" onClick={(e)=>{ e.stopPropagation(); onRename(file); }}>Rename</button>
          <button type="button" className="btn-link danger" onClick={(e)=>{ e.stopPropagation(); onDelete(file); }}>Delete</button>
        </div>
      </td>
    </tr>
  );
}
