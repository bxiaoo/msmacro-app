import {Disc2, Bot, SquareStop, Save, Play, Trash2} from 'lucide-react'
import { Button } from './ui/button'

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
    recordingName,
    isPending
}) {
    // With the new useApiAction hook, we no longer need manual debouncing
    // The hook handles preventing duplicate calls automatically
    if (isRecording) {
        return (
            <div className='content-stretch p-4 flex flex-col gap-4 items-start justify-start relative shrink-0 w-full'>
                <div className='w-full'>
                <Button className='w-full' onClick={onStop} disabled={isPending('stop')}>
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
                <Button className='w-full' onClick={onStop} disabled={isPending('stop')}>
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
                        <Button 
                            className='w-full' 
                            variant='primary' 
                            onClick={() => onSave?.(recordingName)} 
                            disabled={!recordingName?.trim() || isPending('save')}
                        >
                            <Save size={20} />
                            Save
                        </Button>
                    </div>
                    <div className='w-full'>
                        <Button 
                            className='w-full' 
                            variant='play' 
                            onClick={onPlayOnce}
                            disabled={isPending('playOnce')}
                        >
                            <Play />
                            Play Once
                        </Button>
                    </div>
                </div>
                <div className='w-full'>
                    <Button 
                        className='w-full' 
                        onClick={onDiscard}
                        disabled={isPending('discard')}
                    >
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
                <Button 
                    className='w-full' 
                    variant='primary' 
                    onClick={onRecord}
                    disabled={isPending('record') || isRecording || isPlaying || isPostRecording}
                >
                    <Disc2 />
                    Record
                </Button>
            </div>
            <div className='w-full'>
                <Button 
                    className='w-full' 
                    onClick={onPlay} 
                    disabled={!canPlay || isPending('play')}
                >
                    <Bot />
                    Play
                </Button>
            </div>
        </div>
    )
}