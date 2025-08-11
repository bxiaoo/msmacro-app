import { stopRecord } from '../api.js'
import { useState } from 'react'

export default function PostRecordBanner({ visible, onAfter }){
    const [name,setName]=useState("")
    if(!visible) return null

    return (
        <div className="postrecord-banner">
            <div className="postrecord-content">
                <div className="postrecord-icon">⚠️</div>
                <div className="postrecord-body">
                    <h3 className="postrecord-title">Choose what to do with your recording</h3>
                    <div className="postrecord-actions">
                        <input
                            type="text"
                            placeholder="File name (optional)"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className="postrecord-input"
                        />
                        <button
                            onClick={() => stopRecord('save', name.trim() || null).then(() => { setName(""); onAfter(); })}
                            className="btn btn-save"
                        >
                            💾 Save
                        </button>
                        <button
                            onClick={() => stopRecord('play_now').then(onAfter)}
                            className="btn btn-play-once"
                        >
                            ▶️ Play Once
                        </button>
                        <button
                            className="btn btn-discard"
                            onClick={() => stopRecord('discard').then(onAfter)}
                        >
                            🗑️ Discard
                        </button>
                    </div>
                    <p className="postrecord-hint">
                        Use <code className="hotkey">LCTL+S/P/D</code> keyboard shortcuts
                    </p>
                </div>
            </div>
        </div>
    )
}