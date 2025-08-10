import { useEffect, useRef } from 'react'

export default function EventsPanel({ onMode }){
    const pre = useRef()
    useEffect(()=>{
        const es = new EventSource('/api/events')
        es.onmessage = (m)=>{
            try{
                const obj = JSON.parse(m.data)
                if(obj.event==='MODE' && onMode) onMode(obj.mode)
                pre.current.textContent += JSON.stringify(obj) + "\n"
                pre.current.scrollTop = pre.current.scrollHeight
            }catch(e){}
        }
        return ()=> es.close()
    },[])
    return (
        <article>
            <header><strong>Events</strong></header>
            <pre ref={pre} className="events" />
        </article>
    )
}
