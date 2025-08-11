export default function ModeBadge({ mode }){
    const colors = {
        IDLE: 'bg-gray-100 text-gray-800',
        RECORDING: 'bg-red-100 text-red-800 animate-pulse',
        PLAYING: 'bg-green-100 text-green-800',
        POSTRECORD: 'bg-yellow-100 text-yellow-800',
        '...': 'bg-gray-100 text-gray-500'
    };

    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[mode] || colors['...']}`}>
            {mode === 'RECORDING' && <div className="w-2 h-2 bg-red-500 rounded-full mr-1.5 animate-ping"></div>}
            {mode || '...'}
        </span>
    );
}