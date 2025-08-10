import { useState } from 'react'
import { renameFile, deleteFile } from '../api.js'

export default function FilesTable({ files, selected, setSelected, onAfter }){
    const [filter,setFilter]=useState("")
    const rows = (files||[]).filter(f=>f.name.toLowerCase().includes(filter.toLowerCase()))
    return (
        <article>
            <header className="grid">
                <strong>Recordings</strong>
                <input placeholder="filter…" value={filter} onChange={e=>setFilter(e.target.value)}/>
            </header>
            <table role="grid" className="table-fixed">
                <thead><tr><th>Name</th><th>Size</th><th>Modified</th><th>Actions</th></tr></thead>
                <tbody>
                {rows.map(f=>{
                    const dt=new Date(f.mtime*1000).toLocaleString()
                    const sel = selected===f.name
                    return <tr key={f.name} style={{background: sel ? '#f0f7ff' : undefined}}>
                        <td><a href="#" onClick={e=>{e.preventDefault(); setSelected(f.name)}} style={{fontWeight: sel ? 600 : 400}}>{f.name}</a></td>
                        <td>{f.size} B</td><td>{dt}</td>
                        <td>
                            <button onClick={async ()=>{
                                const nn = prompt("New name (no path, .json optional):", f.name)
                                if(!nn) return
                                await renameFile(f.name, nn); onAfter()
                            }}>Rename</button>
                            <button className="secondary" onClick={async ()=>{
                                if(!confirm(`Delete ${f.name}?`)) return
                                await deleteFile(f.name); if(selected===f.name) setSelected(null); onAfter()
                            }}>Delete</button>
                        </td>
                    </tr>
                })}
                </tbody>
            </table>
        </article>
    )
}
