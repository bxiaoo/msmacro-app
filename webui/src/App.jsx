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
        if(st.files && st.files.length && !selected){
            setSelected(st.files[0].name)
        }
    }).catch(()=>{})

    useEffect(()=>{ refresh(); const t=setInterval(refresh, 3000); return ()=>clearInterval(t) },[])

    return (
        <div className="min-h-screen bg-gray-100 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        MS Macro <ModeBadge mode={mode} />
                    </h1>
                </div>

                {/* Post Record Banner */}
                <PostRecordBanner visible={mode==='POSTRECORD'} onAfter={refresh} />

                {/* Controls */}
                <div className="mb-6">
                    <Controls selected={selected} onAfter={refresh} />
                </div>

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Files Table - Takes 2/3 width on large screens */}
                    <div className="lg:col-span-2">
                        <FilesTable
                            files={files}
                            selected={selected}
                            setSelected={setSelected}
                            onAfter={refresh}
                        />
                    </div>

                    {/* Events Panel - Takes 1/3 width on large screens */}
                    <div className="lg:col-span-1">
                        <EventsPanel onMode={setMode} />
                    </div>
                </div>
            </div>
        </div>
    )
}