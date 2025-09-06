import {Disc2, Bot, SquareStop, Save, Play, Trash2} from 'lucide-react'
import { Button } from './ui/button'
import { useRef } from 'react'

export function ActionButtonGroup({
    onRecord,
    onPlay,
    isRecording,
    isPlaying,
    isPostRecording,
    canPlay,
    onStop,
    onSave,
    onPlayOnce,
    onDiscard,
    recordingName
}) {
    // Use refs to track last play event times to prevent multiple rapid clicks
    const lastPlayTimeRef = useRef(0)
    const lastPlayOnceTimeRef = useRef(0)

    // Debounced play handler - prevents multiple calls within 1 second
    const handlePlay = () => {
        const now = Date.now()
        const timeSinceLastPlay = now - lastPlayTimeRef.current
        
        if (timeSinceLastPlay >= 1000) {
            lastPlayTimeRef.current = now
            onPlay?.()
        }
    }

    // Debounced play once handler - prevents multiple calls within 1 second
    const handlePlayOnce = () => {
        const now = Date.now()
        const timeSinceLastPlayOnce = now - lastPlayOnceTimeRef.current
        
        if (timeSinceLastPlayOnce >= 1000) {
            lastPlayOnceTimeRef.current = now
            onPlayOnce?.()
        }
    }
    if (isRecording) {
        return (
            <div className='content-stretch p-4 flex flex-col gap-4 items-start justify-start relative shrink-0 w-full'>
                <div className='w-full'>
                <Button className='w-full' onClick={onStop}>
                    <SquareStop />
                    Stop recording
                </Button>
                </div>
            </div>
        )
    }

    if (isPlaying) {
        return (
            <div className='content-stretch p-4 flex flex-col gap-4 items-start justify-start relative shrink-0 w-full'>
                <div className='w-full'>
                <Button className='w-full' onClick={onStop}>
                    <SquareStop />
                    Stop playing
                </Button>
                </div>
            </div>
        )
    }

    if (isPostRecording) {
        return (
            <div className='content-stretch p-4 flex w-full flex-col gap-4 relative shrink-0'>
                <div className='content-stretch flex gap-4'>
                    <div className='w-full'>
                        <Button className='w-full' variant='primary' onClick={() => onSave?.(recordingName)} disabled={!recordingName?.trim()}>
                            <Save size={20} />
                            Save
                        </Button>
                    </div>
                    <div className='w-full'>
                        <Button className='w-full' variant='play' onClick={handlePlayOnce}>
                            <Play />
                            Play Once
                        </Button>
                    </div>
                </div>
                <div className='w-full'>
                    <Button className='w-full' onClick={onDiscard}>
                        <Trash2 />
                        Discard
                    </Button>
                </div>
            </div>
        )
    }

    return (
        <div className='content-stretch p-4 flex w-full flex-row gap-4 relative shrink-0'>
            <div className='w-full'>
                <Button className='w-full' variant='primary' onClick={onRecord}>
                    <Disc2 />
                    Record
                </Button>
            </div>
            <div className='w-full'>
                <Button className='w-full' onClick={handlePlay} disabled={!canPlay}>
                    <Bot />
                    Play
                </Button>
            </div>
        </div>
    )
}