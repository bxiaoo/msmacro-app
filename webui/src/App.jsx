import { useEffect, useState } from 'react'
import { getStatus } from './api.js'
import ModeBadge from './components/ModeBadge.jsx'
import Controls from './components/Controls.jsx'
import PostRecordBanner from './components/PostRecordBanner.jsx'
import FilesTable from './components/FilesTable.jsx'
import EventsPanel from './components/EventsPanel.jsx'
import './styles.css'

export default function App(){
    const [mode,setMode]=useState('...')
    const [files,setFiles]=useState([])
    const [selected,setSelected]=useState(null)

    const refresh = ()=> getStatus().then(st=>{
        setMode(st.mode)
        setFiles(st.files||[])
        // Only auto-select first file if no file is currently selected AND there are files
        if(st.files && st.files.length && !selected){
            setSelected(st.files[0].name)
        }
        // If selected file no longer exists in the list, clear selection
        if(selected && st.files && !st.files.find(f => f.name === selected)) {
            setSelected(null)
        }
    }).catch(()=>{})

    useEffect(()=>{ refresh(); const t=setInterval(refresh, 3000); return ()=>clearInterval(t) },[selected]) // Add selected as dependency

    return (
        <div className="app-container">
            <div className="app-content">
                {/* Header */}
                <div className="header">
                    <h1 className="main-title">
                        MS Macro <ModeBadge mode={mode} />
                    </h1>
                </div>

                {/* Post Record Banner */}
                <PostRecordBanner visible={mode==='POSTRECORD'} onAfter={refresh} />

                {/* Controls */}
                <div className="controls-section">
                    <Controls selected={selected} onAfter={refresh} />
                </div>

                {/* Main Content Grid */}
                <div className="main-grid">
                    {/* Files Table */}
                    <div className="files-section">
                        <FilesTable
                            files={files}
                            selected={selected}
                            setSelected={setSelected}
                            onAfter={refresh}
                        />
                    </div>

                    {/* Events Panel */}
                    <div className="events-section">
                        <EventsPanel onMode={setMode} />
                    </div>
                </div>
            </div>
        </div>
    )
}