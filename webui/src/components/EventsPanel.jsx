import { useEffect, useRef } from 'react'

export default function EventsPanel({ onMode }){
    const pre = useRef()

    useEffect(()=>{
        const es = new EventSource('/api/events')
        es.onmessage = (m)=>{
            try{
                const obj = JSON.parse(m.data)
                if(obj.event==='MODE' && onMode) onMode(obj.mode)

                // Create formatted event entry
                const timestamp = new Date().toISOString().split('T')[1].split('.')[0]
                const eventLine = `${timestamp} ${JSON.stringify(obj)}\n`

                pre.current.textContent += eventLine
                pre.current.scrollTop = pre.current.scrollHeight
            }catch(e){}
        }
        return ()=> es.close()
    },[])

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">Live Events</h3>
            </div>
            <div className="p-4">
                <div className="bg-gray-50 rounded-md p-4 h-64 overflow-y-auto">
                    <pre ref={pre} className="font-mono text-sm text-gray-700 whitespace-pre-wrap" />
                </div>
            </div>
        </div>
    )
}