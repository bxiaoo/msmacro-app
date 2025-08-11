import { startRecord, stop, play } from '../api.js'
import { useState } from 'react'

export default function Controls({ selected, onAfter }){
    const [speed,setSpeed]=useState(1.00)
    const [jt,setJt]=useState(0.00)
    const [jh,setJh]=useState(0.00)
    const [loop,setLoop]=useState(1)

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Controls</h3>

            {/* Action Buttons */}
            <div className="flex gap-3 mb-6">
                <button
                    onClick={() => startRecord().then(onAfter)}
                    className="flex-1 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-medium transition-colors duration-200"
                >
                    🔴 Record
                </button>
                <button
                    onClick={() => stop().then(onAfter)}
                    className="flex-1 bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg font-medium transition-colors duration-200"
                >
                    ⏹️ Stop
                </button>
                <button
                    onClick={() => selected && play(selected, {speed, jitter_time:jt, jitter_hold:jh, loop}).then(onAfter)}
                    disabled={!selected}
                    className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg font-medium transition-colors duration-200"
                >
                    ▶️ Play Selected
                </button>
            </div>

            {/* Settings Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Speed</label>
                    <input
                        type="number"
                        step="0.05"
                        value={speed}
                        onChange={e => setSpeed(parseFloat(e.target.value || "1"))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Jitter Time</label>
                    <input
                        type="number"
                        step="0.01"
                        value={jt}
                        onChange={e => setJt(parseFloat(e.target.value || "0"))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Jitter Hold</label>
                    <input
                        type="number"
                        step="0.01"
                        value={jh}
                        onChange={e => setJh(parseFloat(e.target.value || "0"))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Loop</label>
                    <input
                        type="number"
                        step="1"
                        value={loop}
                        onChange={e => setLoop(parseInt(e.target.value || "1"))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
            </div>

            {/* Hotkeys Info */}
            <div className="mt-4 p-3 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-600">
                    <strong>Hotkeys:</strong>
                    <code className="mx-1 px-1.5 py-0.5 bg-gray-200 rounded text-xs">LCTL+R</code> record,
                    <code className="mx-1 px-1.5 py-0.5 bg-gray-200 rounded text-xs">LCTL+Q</code> stop,
                    <code className="mx-1 px-1.5 py-0.5 bg-gray-200 rounded text-xs">LCTL+S/P/D</code> post-record options
                </p>
            </div>
        </div>
    )
}