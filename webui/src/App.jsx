import { useEffect, useState } from 'react'
import { getStatus, startRecord, stop, play, saveLast, previewLast, discardLast } from './api.js'
import ModeBadge from './components/ModeBadge.jsx'
import Controls from './components/Controls.jsx'
import PostRecordBanner from './components/PostRecordBanner.jsx'
import FileBrowser from './components/files/FileBrowser.jsx'
import EventsPanel from './components/EventsPanel.jsx'
import './styles.css'

import { Header } from './components/Header.jsx'
import { NavigationTabs } from './components/NavigationTabs.jsx'
import { ActionButtonGroup } from './components/ActionButtonGroup.jsx'
import { StateMessage } from './components/StateMessage.jsx'
import { MacroList } from './components/files/MacroList.jsx'
import { PlaySettingsModal } from './components/PlaySettingsModal.jsx'
import { PostRecordingModal } from './components/PostRecordingModal.jsx'

export default function App(){
  const [activeTab, setActiveTab] = useState('botting')
  const [isRecording, setIsRecording] = useState(false)
  const [isPostRecording, setIsPostRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [recordingStartTime, setRecordingStartTime] = useState(undefined)
  const [playingStartTime, setPlayingStartTime] = useState(undefined)
  const [playingMacroName, setPlayingMacroName] = useState('')
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [isDebugWindowOpen, setIsDebugWindowOpen] = useState(false)
  const [debugLogs, setDebugLogs] = useState([])
  const [isDesktop, setIsDesktop] = useState(false)
  const [playSettings, setPlaySettings] = useState({ speed: 1, jitter_time: 0.2, jitter_hold: 0.045, loop: 15 })
  const [mode, setMode] = useState('...')
  const [selected, setSelected] = useState([]) // kept for Controls
  const [recordingName, setRecordingName] = useState('')

  // Keep mode fresh (and anything else status provides that Controls/Banner need)
  const refresh = () => getStatus().then(st => {
    setMode(st.mode)
    if (st.mode === 'PLAYING') {
      setIsPostRecording(false)
      setIsRecording(false)
      setIsPlaying(true)
      if (!playingStartTime) {
        setPlayingStartTime(Date.now())
      }
    } else if (st.mode === 'POSTRECORD') {
      setIsPlaying(false)
      setIsRecording(false)
      setIsPostRecording(true)
      setPlayingStartTime(undefined)
      setRecordingStartTime(undefined)
    } else if (st.mode === 'RECORDING') {
      setIsPlaying(false)
      setIsPostRecording(false)
      setIsRecording(true)
      if (!recordingStartTime) {
        setRecordingStartTime(Date.now())
      }
    } else {
      // IDLE or other states
      setIsPlaying(false)
      setIsRecording(false)
      setIsPostRecording(false)
      setPlayingStartTime(undefined)
      setRecordingStartTime(undefined)
    }
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

  /**
   * delete event handle
   * @param {folder id} folderId 
   * @param {file id} fileId 
   */
  const handleDelete = (folderId, fileId) => {
    console.log('handle delete folder/files')
  }

  /**
   * rename folder/file or add group/folder
   * @param {folder id for editing} folderId 
   * @param {file id for editing} fileId 
   */
  const handleEdit = (folderId, fileId) => {
    console.log('handle edit folder/file name')
  }

  /**
   * start recording
   */
  const handleRecord = () => {
    startRecord().then(refresh)
  }

  /**
   * handle save recording
   * @param {save name} name 
   */
  const handleSaveRecording = async (name) => {
    if (!name?.trim()) return;
    try {
      await saveLast(name.trim());
      setRecordingName('');
      refresh();
    } catch (e) {
      console.error('Failed to save recording:', e);
    }
  }

  /**
   * handle play once after recording
   */
  const handlePlayOnce = async () => {
    try {
      await previewLast({ speed: playSettings.speed });
      refresh();
    } catch (e) {
      console.error('Failed to play once:', e);
    }
  }

  /**
   * handle discard recording
   */
  const handleDiscardRecording = async () => {
    try {
      await discardLast();
      setRecordingName('');
      refresh();
    } catch (e) {
      console.error('Failed to discard recording:', e);
    }
  }

  /**
   * staring playing
   */
  const handlePlay = () => {
    if (selected) play(selected, playSettings).then(refresh)
  }

  /**
   * stop playing
   */
  const handleStop = () => {
    try {
      stop().then(refresh)
    } catch (e) {
      console.error('Failed to stop: ', e)
    }
  }

  const handlePlaySetting = () => {
      setIsDebugWindowOpen(false)
      setIsSettingsModalOpen(!isSettingsModalOpen)
      console.log('play setting open')
  }

  const handleDebug = () => {
    setIsDebugWindowOpen(!isDebugWindowOpen)
  }

  const handleCloseModal = () => {
    setIsSettingsModalOpen(false)
    setIsDebugWindowOpen(false)
  }


  const canPlay = selected.length > 0 && !isRecording && !isPostRecording && !isPlaying

  return (
    <div className="h-screen flex flex-col relative">
      {/* Global overlay for modals */}
      {(isSettingsModalOpen || isDebugWindowOpen) && (
        <div className='bg-gray-900/25 absolute inset-0 z-20' onClick={handleCloseModal}></div>
      )}

      {/* Main content area - Scrollable (includes header and macro list) */}
      <div className="flex-1 overflow-y-auto">
        <Header 
          isActive={mode} 
          onSettingsClick={handlePlaySetting} 
          onDebugClick={handleDebug} 
          isSettingsActive={isSettingsModalOpen} 
          isDebugActive={isDebugWindowOpen} 
        />
        <MacroList />
      </div>

      {/* Bottom section - Fixed at bottom with proper stacking */}
      <div className='relative z-30 shadow-lg'>
        {/* Debug panel - appears above the main bottom section */}
        {isDebugWindowOpen && (
          <div className="border-t border-gray-200">
            <EventsPanel onMode={setMode} />
          </div>
        )}

        {/* Post-recording modal - appears above action buttons */}
        {isPostRecording && (
          <PostRecordingModal
            isOpen={isPostRecording}
            name={recordingName}
            onNameChange={setRecordingName}
          />
        )}

        {/* Settings modal - appears above action buttons */}
        {isSettingsModalOpen && !isPlaying && (
          <PlaySettingsModal
            isOpen={isSettingsModalOpen}
            onClose={() => setIsSettingsModalOpen(false)}
            settings={playSettings}
            onSettingsChange={setPlaySettings}
          />
        )}

        {/* State message */}
        <StateMessage 
          isPlaying={isPlaying} 
          isRecording={isRecording} 
          startTime={isPlaying ? playingStartTime : recordingStartTime} 
          macroName={playingMacroName} 
        />

        {/* Action buttons */}
        <div className='bg-white border-t border-gray-200'>
          <ActionButtonGroup
            onRecord={handleRecord}
            onPlay={handlePlay}
            isRecording={isRecording}
            isPlaying={isPlaying}
            isPostRecording={isPostRecording}
            canPlay={canPlay}
            onStop={handleStop}
            onSave={handleSaveRecording}
            onPlayOnce={handlePlayOnce}
            onDiscard={handleDiscardRecording}
            recordingName={recordingName}
          />
        </div>

        {/* Navigation tabs */}
        <NavigationTabs activeTab='botting' onTabChange={setActiveTab} />
      </div>
    </div>
  )
}
