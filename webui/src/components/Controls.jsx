import { startRecord, stop, play } from '../api.js'
import { useState } from 'react'

export default function Controls({ selected, onAfter }){
    const [speed,setSpeed]=useState(1.00)
    const [jt,setJt]=useState(0.00)
    const [jh,setJh]=useState(0.00)
    const [loop,setLoop]=useState(1)

    return (
        <article>
            <header><strong>Controls</strong></header>
            <div className="grid">
                <button onClick={()=>startRecord().then(onAfter)}>Record</button>
                <button onClick={()=>stop().then(onAfter)}>Stop</button>
                <button onClick={()=>selected && play(selected,{speed,jitter_time:jt,jitter_hold:jh,loop}).then(onAfter)}
                        disabled={!selected}>Play selected</button>
                <label>Speed <input type="number" step="0.05" value={speed} onChange={e=>setSpeed(parseFloat(e.target.value||"1"))}/></label>
                <label>Jitter time <input type="number" step="0.01" value={jt} onChange={e=>setJt(parseFloat(e.target.value||"0"))}/></label>
                <label>Jitter hold <input type="number" step="0.01" value={jh} onChange={e=>setJh(parseFloat(e.target.value||"0"))}/></label>
                <label>Loop <input type="number" step="1" value={loop} onChange={e=>setLoop(parseInt(e.target.value||"1"))}/></label>
            </div>
            <small>Hotkeys: <kbd>LCTL+R</kbd> record, <kbd>LCTL+Q</kbd> stop record/play, <kbd>LCTL+S/P/D</kbd> post-record options</small>
        </article>
    )
}
