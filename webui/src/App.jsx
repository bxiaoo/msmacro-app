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
        <>
            <h1>MS Macro <ModeBadge mode={mode}/></h1>

            <PostRecordBanner visible={mode==='POSTRECORD'} onAfter={refresh} />
            <Controls selected={selected} onAfter={refresh} />

            <div className="grid">
                <FilesTable files={files} selected={selected} setSelected={setSelected} onAfter={refresh}/>
                <EventsPanel onMode={setMode}/>
            </div>
        </>
    )
}
