import { useEffect, useRef } from 'react'

export default function EventsPanel({ onMode }){
    const pre = useRef()

    useEffect(()=>{
        const es = new EventSource('/api/events')
        es.onmessage = (m)=>{
            try{
                const obj = JSON.parse(m.data)

                // server now sends {type:"mode"} and {type:"files"} events
                const evtType = obj.type || obj.event
                if(evtType === 'mode' && onMode){
                    onMode(obj.mode)
                }

                const timestamp = new Date().toISOString().split('T')[1].split('.')[0]
                const eventLine = `${timestamp} ${JSON.stringify(obj)}\n`

                if(pre.current){
                    pre.current.textContent += eventLine
                    pre.current.scrollTop = pre.current.scrollHeight
                }
            }catch(e){}
        }
        return ()=> es.close()
    },[onMode])

    return (
        <div className="card events-card">
            <div className="events-header">
                <h3 className="events-title">Live Events</h3>
            </div>
            <div className="events-content">
                <pre ref={pre} className="events-display" />
            </div>
        </div>
    )
}
