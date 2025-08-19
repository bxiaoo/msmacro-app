import { useEffect, useState } from 'react'
import { getStatus } from './api.js'
import ModeBadge from './components/ModeBadge.jsx'
import Controls from './components/Controls.jsx'
import PostRecordBanner from './components/PostRecordBanner.jsx'
import FileBrowser from './components/files/FileBrowser.jsx'
import EventsPanel from './components/EventsPanel.jsx'
import './styles.css'

export default function App(){
  const [mode, setMode] = useState('...')
  const [selected, setSelected] = useState([]) // kept for Controls

  // Keep mode fresh (and anything else status provides that Controls/Banner need)
  const refresh = () => getStatus().then(st => {
    setMode(st.mode)
  }).catch(() => {})

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2000)
    return () => clearInterval(t)
  }, [])

  // Bridge selection coming from FileBrowser → Controls
  useEffect(() => {
    const onSel = (e) => { if (Array.isArray(e.detail)) setSelected(e.detail) }
    document.addEventListener('files:selection:set', onSel)
    return () => document.removeEventListener('files:selection:set', onSel)
  }, [])

  return (
    <div className="app-container">
      <div className="app-content">
        <div className="header">
          <h1 className="main-title">
            MS Macro <ModeBadge mode={mode} />
          </h1>
        </div>

        <PostRecordBanner visible={mode === 'POSTRECORD'} onAfter={refresh} />

        <div className="controls-section">
          <Controls selected={selected} onAfter={refresh} />
        </div>

        <div className="main-grid">
          <div className="files-section">
            {/* New modular browser with folder accordions & actions */}
            <FileBrowser />
          </div>
          <div className="events-section">
            <EventsPanel onMode={setMode} />
          </div>
        </div>
      </div>
    </div>
  )
}
