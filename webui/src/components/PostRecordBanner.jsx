import { saveLast, previewLast, discardLast } from '../api.js'
import { useState } from 'react'

export default function PostRecordBanner({ visible, onAfter }){
    const [name,setName]=useState("")
    const [busy, setBusy] = useState(false);

    const handleSave = async () => {
      if (!name.trim()) return;             // backend also validates
      setBusy(true);
      try {
        await saveLast(name.trim());
        setName("");
        onAfter?.();
      } finally {
        setBusy(false);
      }
    };
  
    const handlePlayOnce = async () => {
      setBusy(true);
      try {
        // you can pass speed/jitter if you expose UI controls:
        await previewLast({ speed: 1.0 });
        onAfter?.(); // refresh status if you want
      } finally {
        setBusy(false);
      }
    };
  
    const handleDiscard = async () => {
      setBusy(true);
      try {
        await discardLast();
        onAfter?.();
      } finally {
        setBusy(false);
      }
    };

    if(!visible) return null

    return (
        <div className="postrecord-banner">
            <div className="postrecord-content">
                <div className="postrecord-icon">⚠️</div>
                <div className="postrecord-body">
                    <h3 className="postrecord-title">Choose what to do with your recording</h3>
                    <div className="postrecord-actions">
                        <input
                            type="text"
                            placeholder="File name (optional)"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className="postrecord-input"
                        />
                        <button
                            onClick={handleSave}
                            className="btn btn-save"
                            disabled={busy || !name.trim()}
                            title={!name.trim() ? "Enter a name to enable Save" : ""}
                        >
                            💾 Save
                        </button>
                        <button
                            onClick={handlePlayOnce}
                            className="btn btn-play-once"
                            disabled={busy}
                        >
                            ▶️ Play Once
                        </button>
                        <button
                            className="btn btn-discard"
                            onClick={handleDiscard}
                            disabled={busy}
                        >
                            🗑️ Discard
                        </button>
                    </div>
                    <p className="postrecord-hint">
                        Use <code className="hotkey">LCTL+S/P/D</code> keyboard shortcuts
                    </p>
                </div>
            </div>
        </div>
    )
}
