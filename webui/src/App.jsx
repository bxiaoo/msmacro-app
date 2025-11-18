import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { getStatus, startRecord, stop, play, saveLast, previewLast, discardLast, deleteFile, listSkills, saveSkill, updateSkill, deleteSkill as deleteSkillAPI, reorderSkills, EventStream, listCVItems, getCVAutoStatus, startCVAuto, stopCVAuto } from './api.js'
import { useApiAction } from './hooks/useApiAction.js'
import { useSkillsOpenState } from './hooks/useSkillsOpenState.js'
import EventsPanel from './components/EventsPanel.jsx'
import './styles.css'

import { Header } from './components/Header.jsx'
import { NavigationTabs } from './components/NavigationTabs.jsx'
import { ActionButtonGroup } from './components/ActionButtonGroup.jsx'
import { StateMessage } from './components/StateMessage.jsx'
import { MacroList } from './components/rotations/MacroList.jsx'
import { CDSkills } from './components/skills/CDSkills.jsx'
import { CVItemList } from './components/cv/CVItemList.jsx'
import { PlaySettingsModal } from './components/rotations/PlaySettingsModal.jsx'
import { PostRecordingModal } from './components/rotations/PostRecordingModal.jsx'
import { NewSkillModal } from './components/skills/NewSkillModal.jsx'

export default function App(){
  const { executeAction, isPending } = useApiAction()
  const { getAllOpenStates, setOpenState, removeOpenState, cleanupOpenStates } = useSkillsOpenState()
  const [activeTab, setActiveTab] = useState('rotations')
  const [isRecording, setIsRecording] = useState(false)
  const [isPostRecording, setIsPostRecording] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playingMacroName, setPlayingMacroName] = useState('')

  // CV-AUTO states
  const [activeCVItem, setActiveCVItem] = useState(null)
  const [isCVAutoPlaying, setIsCVAutoPlaying] = useState(false)

  // Use refs for start times to avoid timer resets
  const recordingStartTimeRef = useRef(undefined)
  const playingStartTimeRef = useRef(undefined)
  const [recordingStartTime, setRecordingStartTime] = useState(undefined)
  const [playingStartTime, setPlayingStartTime] = useState(undefined)
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [isDebugWindowOpen, setIsDebugWindowOpen] = useState(false)
  const [debugLogs, setDebugLogs] = useState([])
  const [isDesktop, setIsDesktop] = useState(false)
  const [playSettings, setPlaySettings] = useState({ 
    speed: 1, 
    jitter_time: 0.3,
    jitter_hold: 0.3,
    loop: 15,
    ignore_keys: ['s', '', ''], // Up to 3 keys that can be ignored
    ignore_tolerance: 0.15 // How often keys should be ignored (0-1, where 0.1 = 10%)
  })
  const [mode, setMode] = useState('...')
  const [selected, setSelected] = useState([]) // kept for Controls
  const [recordingName, setRecordingName] = useState('')
  const [isNewSkillModalOpen, setIsNewSkillModalOpen] = useState(false)
  const [editingSkill, setEditingSkill] = useState(null)
  const [cdSkills, setCdSkills] = useState([])
  const [skillsLoaded, setSkillsLoaded] = useState(false)

  // Keep mode fresh (and anything else status provides that Controls/Banner need)
  const refresh = useCallback(() => getStatus().then(st => {
    const newMode = st.mode
    setMode(prevMode => {
      if (prevMode === newMode) return prevMode // Prevent unnecessary re-renders
      return newMode
    })

    if (newMode === 'PLAYING') {
      setIsPostRecording(false)
      setIsRecording(false)
      setIsPlaying(true)
      // Use ref to check if startTime already set (prevents reset)
      if (!playingStartTimeRef.current) {
        const now = Date.now()
        playingStartTimeRef.current = now
        setPlayingStartTime(now)
      }
      // Update playing file name from backend
      if (st.current_playing_file) {
        const fileName = st.current_playing_file.split('/').pop().replace('.json', '');
        setPlayingMacroName(fileName);
      }
    } else if (newMode === 'POSTRECORD') {
      setIsPlaying(false)
      setIsRecording(false)
      setIsPostRecording(true)
      playingStartTimeRef.current = undefined
      recordingStartTimeRef.current = undefined
      setPlayingStartTime(undefined)
      setRecordingStartTime(undefined)
    } else if (newMode === 'RECORDING') {
      setIsPlaying(false)
      setIsPostRecording(false)
      setIsRecording(true)
      // Use ref to check if startTime already set (prevents reset)
      if (!recordingStartTimeRef.current) {
        const now = Date.now()
        recordingStartTimeRef.current = now
        setRecordingStartTime(now)
      }
    } else {
      // IDLE or other states
      setIsPlaying(false)
      setIsRecording(false)
      setIsPostRecording(false)
      playingStartTimeRef.current = undefined
      recordingStartTimeRef.current = undefined
      setPlayingStartTime(undefined)
      setRecordingStartTime(undefined)
      setPlayingMacroName('')
    }
  }).catch(() => {}), []) // No dependencies - stable callback

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2000)
    return () => clearInterval(t)
  }, [refresh])

  // Poll CV status (active item and CV-AUTO playing state)
  useEffect(() => {
    const refreshCVStatus = async () => {
      try {
        // Get active CV item
        const response = await listCVItems()
        setActiveCVItem(response.active_item || null)

        // Get CV-AUTO playing status
        const cvAutoStatus = await getCVAutoStatus()
        setIsCVAutoPlaying(cvAutoStatus.is_running || false)
      } catch (err) {
        // Silently fail - CV might not be initialized
      }
    }

    refreshCVStatus()
    const interval = setInterval(refreshCVStatus, 2000)
    return () => clearInterval(interval)
  }, [])

  // Connect SSE EventStream for real-time updates
  useEffect(() => {
    const eventStream = new EventStream(
      // onMode callback
      (newMode) => {
        setMode(newMode)
      },
      // onFiles callback
      (files) => {
        // Dispatch event to trigger MacroList refresh
        document.dispatchEvent(new CustomEvent('files:refresh'))
      }
    )

    return () => eventStream.close()
  }, [])

  // Bridge selection coming from FileBrowser → Controls
  useEffect(() => {
    const onSel = (e) => { if (Array.isArray(e.detail)) setSelected(e.detail) }
    document.addEventListener('files:selection:set', onSel)
    return () => document.removeEventListener('files:selection:set', onSel)
  }, [])

  // Load skills from backend
  const loadSkills = useCallback(async () => {
    try {
      const skills = await listSkills()

      // Merge backend data with localStorage open states
      const openStates = getAllOpenStates()
      const mergedSkills = (skills || []).map(skill => ({
        ...skill,
        isOpen: openStates[skill.id] || false
      }))

      // Cleanup localStorage for any deleted skills
      cleanupOpenStates(mergedSkills.map(s => s.id))

      setCdSkills(mergedSkills)
      setSkillsLoaded(true)
    } catch (error) {
      console.error('Failed to load skills:', error)
      setSkillsLoaded(true)
    }
  }, [getAllOpenStates, cleanupOpenStates])

  useEffect(() => {
    loadSkills()
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
  const handleRecord = useCallback(() => {
    executeAction('record', () => startRecord(), refresh)
  }, [executeAction, refresh])

  /**
   * handle save recording
   * @param {save name} name 
   */
  const handleSaveRecording = useCallback((name) => {
    if (!name?.trim()) return;
    executeAction('save',
      () => saveLast(name.trim()),
      () => {
        setRecordingName('');
        refresh();
        // Trigger MacroList refresh
        document.dispatchEvent(new CustomEvent('files:refresh'));
      }
    )
  }, [executeAction, refresh])

  /**
   * handle play once after recording
   */
  const handlePlayOnce = useCallback(() => {
    executeAction('playOnce', 
      () => previewLast({ speed: playSettings.speed }), 
      refresh
    )
  }, [executeAction, playSettings.speed, refresh])

  /**
   * handle discard recording
   */
  const handleDiscardRecording = useCallback(() => {
    executeAction('discard',
      () => discardLast(),
      () => {
        setRecordingName('');
        refresh();
        // Trigger MacroList refresh
        document.dispatchEvent(new CustomEvent('files:refresh'));
      }
    )
  }, [executeAction, refresh])

  /**
   * staring playing
   */
  const handlePlay = useCallback(() => {
    // Check if CV item is active → start CV-AUTO
    if (activeCVItem) {
      executeAction('play',
        () => startCVAuto({
          loop: playSettings.loop,
          speed: playSettings.speed,
          jitter_time: playSettings.jitter_time,
          jitter_hold: playSettings.jitter_hold,
          jump_key: "SPACE"
        }),
        refresh
      );
    }
    // Otherwise play selected rotations normally
    else if (selected && selected.length > 0) {
      // Get selected skills for injection during playback
      const selectedSkills = cdSkills.filter(skill => skill.isSelected)

      executeAction('play',
        () => play(selected, {
          ...playSettings,
          active_skills: selectedSkills
        }),
        refresh
      );
    }
  }, [executeAction, activeCVItem, selected, playSettings, refresh, cdSkills])

  /**
   * stop playing
   */
  const handleStop = useCallback(() => {
    // If CV-AUTO is running, stop it
    if (isCVAutoPlaying) {
      executeAction('stop', () => stopCVAuto(), refresh)
    } else {
      // Otherwise stop regular playback
      executeAction('stop', () => stop(), refresh)
    }
  }, [executeAction, isCVAutoPlaying, refresh])

  const handlePlaySetting = useCallback(() => {
      setIsDebugWindowOpen(false)
      setIsSettingsModalOpen(!isSettingsModalOpen)
      console.log('play setting open')
  }, [isSettingsModalOpen])

  const handleDebug = useCallback(() => {
    setIsDebugWindowOpen(!isDebugWindowOpen)
  }, [isDebugWindowOpen])

  const handleCloseModal = useCallback(() => {
    setIsSettingsModalOpen(false)
    setIsDebugWindowOpen(false)
    // Note: We don't close isPostRecording or isNewSkillModalOpen on overlay click
    // Those require explicit close button clicks
  }, [])

  /**
   * handle delete selected files
   */
  const handleDeleteSelected = useCallback(async () => {
    if (!selected.length) return
    if (!confirm(`Delete ${selected.length} file(s)?`)) return

    executeAction('deleteSelected', async () => {
      for (const rel of selected) {
        await deleteFile(rel)
      }
      setSelected([])
    }, () => {
      refresh();
      // Trigger MacroList refresh
      document.dispatchEvent(new CustomEvent('files:refresh'));
    })
  }, [selected, executeAction, refresh])

  /**
   * handle new skill modal actions
   */
  const handleOpenNewSkillModal = useCallback(() => {
    setIsNewSkillModalOpen(true)
  }, [])

  const handleCloseNewSkillModal = useCallback(() => {
    setIsNewSkillModalOpen(false)
    setEditingSkill(null)
  }, [])

  const handleEditSkill = useCallback((skill) => {
    setEditingSkill(skill)
    setIsNewSkillModalOpen(true)
  }, [])

  const handleSaveNewSkill = useCallback(async ({ name, skillKey, cooldown, skillDelay, castPosition, isEditing, skillId }) => {
    try {
      if (isEditing && skillId) {
        // Update existing skill
        const existingSkill = cdSkills.find(skill => skill.id === skillId)
        if (existingSkill) {
          const updatedSkill = {
            ...existingSkill,
            name: name,
            keystroke: skillKey,
            cooldown: cooldown,
            skillDelay: skillDelay !== undefined ? skillDelay : 0.3,
            castPosition: castPosition !== undefined ? castPosition : 0.3
          }
          await updateSkill(skillId, updatedSkill)
          setCdSkills(prev => prev.map(skill =>
            skill.id === skillId ? updatedSkill : skill
          ))
        }
      } else {
        // Create new skill
        const maxOrder = cdSkills.length > 0 ? Math.max(...cdSkills.map(s => s.order || 0)) : -1
        const newSkill = {
          name: name,
          keystroke: skillKey,
          variant: "cd skill",
          isOpen: false,
          isEnabled: true,
          isSelected: false,
          keyReplacement: false,
          replaceRate: 0.7,
          frozenRotationDuringCasting: false,
          cooldown: cooldown,
          skillDelay: skillDelay !== undefined ? skillDelay : 0.3,
          castPosition: castPosition !== undefined ? castPosition : 0.3,
          order: maxOrder + 1,
          groupId: null,
          delayAfter: 0
        }
        const savedSkill = await saveSkill(newSkill)
        setCdSkills(prev => [...prev, savedSkill])
      }
    } catch (error) {
      console.error('Failed to save skill:', error)
    }

    setIsNewSkillModalOpen(false)
    setEditingSkill(null)
  }, [cdSkills])

  /**
   * handle skill management functions
   */
  const updateSkillLocal = useCallback(async (id, updates) => {
    try {
      const existingSkill = cdSkills.find(skill => skill.id === id)
      if (existingSkill) {
        const updatedSkill = { ...existingSkill, ...updates }

        // If isOpen is being updated, persist to localStorage
        if ('isOpen' in updates) {
          setOpenState(id, updates.isOpen)
        }

        await updateSkill(id, updatedSkill)
        setCdSkills(prev => prev.map(skill =>
          skill.id === id ? updatedSkill : skill
        ))
      }
    } catch (error) {
      console.error('Failed to update skill:', error)
    }
  }, [cdSkills, setOpenState])

  const deleteSkill = useCallback(async (id) => {
    if (confirm('Delete this skill?')) {
      try {
        await deleteSkillAPI(id)
        // Remove from localStorage as well
        removeOpenState(id)
        setCdSkills(prev => prev.filter(skill => skill.id !== id))
      } catch (error) {
        console.error('Failed to delete skill:', error)
      }
    }
  }, [removeOpenState])

  const handleReorderSkills = useCallback(async (reorderedSkills) => {
    try {
      await reorderSkills(reorderedSkills)
      setCdSkills(reorderedSkills)
    } catch (error) {
      console.error('Failed to reorder skills:', error)
    }
  }, [])

  const canPlay = useMemo(() =>
    (selected.length > 0 || activeCVItem) && !isRecording && !isPostRecording && !isPlaying && !isPending('play'),
    [selected.length, activeCVItem, isRecording, isPostRecording, isPlaying, isPending]
  )

  // Calculate selected counts for tab badges
  const selectedRotationsCount = useMemo(() => selected.length, [selected.length])
  const selectedSkillsCount = useMemo(() =>
    cdSkills.filter(skill => skill.isSelected).length,
    [cdSkills]
  )

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Global overlay for modals - dark background when any modal is open */}
      {(isSettingsModalOpen || isDebugWindowOpen || isPostRecording || isNewSkillModalOpen) && (
        <div className='bg-gray-900/50 fixed inset-0 z-10' onClick={handleCloseModal}></div>
      )}

      {/* Main content area - Scrollable (includes header, tabs, and macro list) */}
      <div className="flex-1 flex flex-col gap-2 overflow-y-auto min-h-0">
        <Header
          isActive={mode}
          onSettingsClick={handlePlaySetting}
          onDebugClick={handleDebug}
          onDeleteSelected={handleDeleteSelected}
          hasSelectedFiles={selected.length > 0}
          isSettingsActive={isSettingsModalOpen}
          isDebugActive={isDebugWindowOpen}
        />

        {/* Navigation tabs */}
        <NavigationTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          rotationsCount={selectedRotationsCount}
          skillsCount={selectedSkillsCount}
        />

        {/* Tab Content */}
        {activeTab === 'rotations' && <MacroList onSelectedChange={setSelected} />}
        {activeTab === 'cd-skills' && (
          <CDSkills
            skills={cdSkills}
            onOpenNewSkillModal={handleOpenNewSkillModal}
            onEditSkill={handleEditSkill}
            onUpdateSkill={updateSkillLocal}
            onDeleteSkill={deleteSkill}
            onReorderSkills={handleReorderSkills}
          />
        )}
        {activeTab === 'cv-items' && <CVItemList />}
      </div>

      {/* Bottom section - Sticky at bottom, always visible */}
      <div className='sticky bottom-0 z-30 shadow-lg'>
        {/* Debug panel - modal that appears above bottom section */}
        {isDebugWindowOpen && (
          <div className="border-t border-gray-200 z-50 relative bg-white">
            <EventsPanel onMode={setMode} />
          </div>
        )}

        {/* Post-recording modal - only show if isPostRecording is true */}
        {isPostRecording && (
            <div className="z-50 relative">
              <PostRecordingModal
                isOpen={isPostRecording}
                name={recordingName}
                onNameChange={setRecordingName}
              />
            </div>
        )}

        {/* Settings modal - only show if isSettingsModalOpen is true and not playing */}
        {isSettingsModalOpen && !isPlaying && (
            <div className="z-50 relative">
              <PlaySettingsModal
                isOpen={isSettingsModalOpen}
                onClose={() => setIsSettingsModalOpen(false)}
                settings={playSettings}
                onSettingsChange={setPlaySettings}
              />
            </div>
        )}

        {/* New skill modal - only show if isNewSkillModalOpen is true */}
        {isNewSkillModalOpen && (
          <div className="z-50 relative">
            <NewSkillModal
              isOpen={isNewSkillModalOpen}
              onClose={handleCloseNewSkillModal}
              onSave={handleSaveNewSkill}
              editingSkill={editingSkill}
            />
          </div>
        )}

        {/* State message */}
        <StateMessage
          isPlaying={isPlaying}
          isRecording={isRecording}
          isCVActivated={!!activeCVItem}
          isCVPlaying={isCVAutoPlaying}
          startTime={isPlaying ? playingStartTime : recordingStartTime}
          macroName={playingMacroName}
          cvItemName={activeCVItem}
        />

        {/* Action buttons */}
        {!isNewSkillModalOpen && <div className='bg-white border-t border-gray-200'>
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
            isPending={isPending}
          />
        </div>}
      </div>
    </div>
  )
}
