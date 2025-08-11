export default function ModeBadge({ mode }){
    const getModeClass = (mode) => {
        switch(mode) {
            case 'IDLE': return 'idle';
            case 'RECORDING': return 'recording';
            case 'PLAYING': return 'playing';
            case 'POSTRECORD': return 'postrecord';
            default: return 'loading';
        }
    };

    return (
        <span className={`mode-badge ${getModeClass(mode)}`}>
            {mode === 'RECORDING' && <div className="recording-dot"></div>}
            {mode || '...'}
        </span>
    );
}