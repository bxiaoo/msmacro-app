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
        <div className="bg-white p-4 relative rounded-tl-[8px] rounded-tr-[8px] w-full max-h-[65vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex-shrink-0">
                <h3 className="font-['Roboto:Bold',_sans-serif] font-bold text-[16px] text-gray-900">Live Events</h3>
            </div>
            <div className="flex-1 min-h-0 bg-gray-100 overflow-y-auto">
                <pre 
                    ref={pre} 
                    className="p-3 text-xs font-mono leading-tight text-gray-800 whitespace-pre-wrap overflow-x-auto overflow-y-auto h-full w-full break-words"
                    style={{ 
                        fontFamily: 'Monaco, Consolas, "Lucida Console", monospace',
                        wordWrap: 'break-word',
                        overflowWrap: 'break-word'
                    }}
                />
            </div>
        </div>
    )
}
