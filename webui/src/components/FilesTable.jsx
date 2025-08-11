import { useState } from 'react'
import { renameFile, deleteFile } from '../api.js'

export default function FilesTable({ files, selected, setSelected, onAfter }){
    const [filter,setFilter]=useState("")
    const rows = (files||[]).filter(f=>f.name.toLowerCase().includes(filter.toLowerCase()))

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex justify-between items-center">
                    <h3 className="text-lg font-semibold text-gray-900">Recordings</h3>
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="Search recordings..."
                            value={filter}
                            onChange={e => setFilter(e.target.value)}
                            className="pl-8 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <span className="text-gray-400">🔍</span>
                        </div>
                    </div>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                    <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Modified</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                    {rows.map(file => {
                        const dt = new Date(file.mtime * 1000).toLocaleString();
                        const isSelected = selected === file.name;

                        return (
                            <tr
                                key={file.name}
                                className={`hover:bg-gray-50 cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                                onClick={() => setSelected(file.name)}
                            >
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className={`text-sm ${isSelected ? 'font-semibold text-blue-900' : 'text-gray-900'}`}>
                                        {isSelected && <span className="text-blue-500 mr-2">▶</span>}
                                        {file.name}
                                    </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {file.size} B
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {dt}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                                    <button
                                        onClick={async (e) => {
                                            e.stopPropagation();
                                            const newName = prompt("New name (no path, .json optional):", file.name);
                                            if (!newName) return;
                                            await renameFile(file.name, newName);
                                            onAfter();
                                        }}
                                        className="text-indigo-600 hover:text-indigo-900 transition-colors"
                                    >
                                        Rename
                                    </button>
                                    <button
                                        onClick={async (e) => {
                                            e.stopPropagation();
                                            if (!confirm(`Delete ${file.name}?`)) return;
                                            await deleteFile(file.name);
                                            if (selected === file.name) setSelected(null);
                                            onAfter();
                                        }}
                                        className="text-red-600 hover:text-red-900 transition-colors"
                                    >
                                        Delete
                                    </button>
                                </td>
                            </tr>
                        );
                    })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}