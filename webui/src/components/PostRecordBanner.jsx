import { stopRecord } from '../api.js'
import { useState } from 'react'

export default function PostRecordBanner({ visible, onAfter }){
    const [name,setName]=useState("")
    if(!visible) return null
    return (
        <article className="postrec">
            <div className="grid">
                <strong>Post-record options</strong>
                <input placeholder="file name (optional)" value={name} onChange={e=>setName(e.target.value)} />
                <button onClick={()=>stopRecord('save', name.trim()||null).then(()=>{ setName(""); onAfter(); })}>Save</button>
                <button onClick={()=>stopRecord('play_now').then(onAfter)}>Play once</button>
                <button className="secondary" onClick={()=>stopRecord('discard').then(onAfter)}>Discard</button>
                <small>You can also press <kbd>LCTL+S</kbd> / <kbd>LCTL+P</kbd> / <kbd>LCTL+D</kbd> on the keyboard.</small>
            </div>
        </article>
    )
}
