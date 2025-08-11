import { useState } from 'react'
import { renameFile, deleteFile } from '../api.js'

export default function FilesTable({ files, selected, setSelected, onAfter }){
    const [filter,setFilter]=useState("")
    const rows = (files||[]).filter(f=>f.name.toLowerCase().includes(filter.toLowerCase()))

    return (
        <div className="card files-card">
            <div className="files-header">
                <h3 className="files-title">Recordings</h3>
                <div className="search-container">
                    <input
                        type="text"
                        placeholder="Search recordings..."
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        className="search-input"
                    />
                    <div className="search-icon">🔍</div>
                </div>
            </div>

            <div className="files-table-container">
                <table className="files-table">
                    <thead>
                    <tr>
                        <th>Name</th>
                        <th>Size</th>
                        <th>Modified</th>
                        <th>Actions</th>
                    </tr>
                    </thead>
                    <tbody>
                    {rows.map(file => {
                        const dt = new Date(file.mtime * 1000).toLocaleString();
                        const isSelected = selected === file.name;

                        return (
                            <tr
                                key={file.name}
                                className={isSelected ? 'selected' : ''}
                                onClick={() => setSelected(file.name)}
                            >
                                <td>
                                    <div className={`file-name ${isSelected ? 'selected' : ''}`}>
                                        {isSelected && <span className="file-selected-indicator">▶</span>}
                                        {file.name}
                                    </div>
                                </td>
                                <td>
                                    <div className="file-info">{file.size} B</div>
                                </td>
                                <td>
                                    <div className="file-info">{dt}</div>
                                </td>
                                <td>
                                    <div className="file-actions">
                                        <button
                                            onClick={async (e) => {
                                                e.stopPropagation();
                                                const newName = prompt("New name (no path, .json optional):", file.name);
                                                if (!newName) return;
                                                await renameFile(file.name, newName);
                                                onAfter();
                                            }}
                                            className="btn-link"
                                        >
                                            Rename
                                        </button>
                                        <button
                                            onClick={async (e) => {
                                                e.stopPropagation();
                                                if (!confirm(`Delete ${file.name}?`)) return;
                                                await deleteFile(file.name);
                                                if (selected === file.name) setSelected(null);
                                                onAfter();
                                            }}
                                            className="btn-link danger"
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}