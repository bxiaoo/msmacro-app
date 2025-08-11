import { stopRecord } from '../api.js'
import { useState } from 'react'

export default function PostRecordBanner({ visible, onAfter }){
    const [name,setName]=useState("")
    if(!visible) return null

    return (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6 rounded-r-lg">
            <div className="flex items-start">
                <div className="flex-shrink-0">
                    <div className="w-5 h-5 text-yellow-400">⚠️</div>
                </div>
                <div className="ml-3 flex-1">
                    <h3 className="text-sm font-medium text-yellow-800 mb-3">Choose what to do with your recording</h3>
                    <div className="flex flex-wrap gap-3 items-center">
                        <input
                            type="text"
                            placeholder="File name (optional)"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className="px-3 py-2 border border-yellow-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                        />
                        <button
                            onClick={() => stopRecord('save', name.trim() || null).then(() => { setName(""); onAfter(); })}
                            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md font-medium transition-colors"
                        >
                            💾 Save
                        </button>
                        <button
                            onClick={() => stopRecord('play_now').then(onAfter)}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors"
                        >
                            ▶️ Play Once
                        </button>
                        <button
                            className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-md font-medium transition-colors"
                            onClick={() => stopRecord('discard').then(onAfter)}
                        >
                            🗑️ Discard
                        </button>
                    </div>
                    <p className="mt-2 text-xs text-yellow-700">
                        Use <code className="px-1 py-0.5 bg-yellow-200 rounded">LCTL+S/P/D</code> keyboard shortcuts
                    </p>
                </div>
            </div>
        </div>
    )
}