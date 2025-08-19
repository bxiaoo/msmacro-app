import { startRecord, stop, play } from '../api.js'
import { useState } from 'react'

export default function Controls({ selected, onAfter }){
    const [speed,setSpeed]=useState(1.00)
    const [jt,setJt]=useState(0.00)
    const [jh,setJh]=useState(0.00)
    const [loop,setLoop]=useState(1)

    return (
        <div className="card controls-card">
            <h3 className="controls-title">Controls</h3>

            {/* Action Buttons */}
            <div className="controls-buttons">
                <button
                    onClick={() => startRecord().then(onAfter)}
                    className="btn btn-record"
                >
                    🔴 Record
                </button>
                <button
                    onClick={() => stop().then(onAfter)}
                    className="btn btn-stop"
                >
                    ⏹️ Stop
                </button>
                <button
                    onClick={() => selected && play(selected, {speed, jitter_time:jt, jitter_hold:jh, loop}).then(onAfter)}
                    disabled={!selected}
                    className="btn btn-play"
                >
                    ▶️ Play Selected
                </button>
            </div>

            {/* Settings Grid */}
            <div className="controls-settings">
                <div className="setting-group">
                    <label className="setting-label">Speed</label>
                    <input
                        type="number"
                        step="0.05"
                        value={speed}
                        onChange={e => setSpeed(parseFloat(e.target.value || "1"))}
                        className="setting-input"
                    />
                </div>
                <div className="setting-group">
                    <label className="setting-label">Jitter Time</label>
                    <input
                        type="number"
                        step="0.01"
                        value={jt}
                        onChange={e => setJt(parseFloat(e.target.value || "0"))}
                        className="setting-input"
                    />
                </div>
                <div className="setting-group">
                    <label className="setting-label">Jitter Hold</label>
                    <input
                        type="number"
                        step="0.01"
                        value={jh}
                        onChange={e => setJh(parseFloat(e.target.value || "0"))}
                        className="setting-input"
                    />
                </div>
                <div className="setting-group">
                    <label className="setting-label">Loop</label>
                    <input
                        type="number"
                        step="1"
                        value={loop}
                        onChange={e => setLoop(parseInt(e.target.value || "1"))}
                        className="setting-input"
                    />
                </div>
            </div>

            {/* Hotkeys Info */}
            <div className="hotkeys-info">
                <p>
                    <strong>Hotkeys:</strong>
                    <code className="hotkey">LCTL+R</code> record,
                    <code className="hotkey">LCTL+Q</code> stop,
                    <code className="hotkey">LCTL+S/P/D</code> post-record options
                </p>
            </div>
        </div>
    )
}
