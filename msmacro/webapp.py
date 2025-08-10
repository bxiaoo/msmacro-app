import asyncio, json, os, re, time
from pathlib import Path

from aiohttp import web

from .config import SETTINGS
from .ipc import send
from .events import path as events_path

# ---------- helpers ----------
SAFE_NAME = re.compile(r'^[A-Za-z0-9._-]+$')

def _rec_dir() -> Path:
    p = Path(SETTINGS.record_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _rec_path(name: str) -> Path:
    if not name.endswith(".json"):
        name += ".json"
    if not SAFE_NAME.match(Path(name).name):
        raise web.HTTPBadRequest(reason="bad filename")
    p = _rec_dir() / Path(name).name
    # ensure we stay inside the recordings dir
    if p.resolve().parent != _rec_dir().resolve():
        raise web.HTTPBadRequest(reason="bad path")
    return p

async def _ok(data=None):
    return web.json_response({"ok": True, "result": data})

async def _err(msg, status=400):
    return web.json_response({"ok": False, "error": msg}, status=status)

# ---------- API handlers ----------
async def api_status(request):
    try:
        st = await send(SETTINGS.socket_path, {"cmd": "status"})
    except Exception as e:
        return await _err(f"daemon: {e}", 503)
    # attach listing summary
    files = []
    for f in sorted(_rec_dir().glob("*.json")):
        try:
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            })
        except FileNotFoundError:
            pass
    st["files"] = files
    return await _ok(st)

async def api_record_start(request):
    await send(SETTINGS.socket_path, {"cmd": "record_start"})
    return await _ok("recording")

async def api_record_stop(request):
    payload = await request.json()
    action = payload.get("action", "discard")
    name = payload.get("name")
    res = await send(SETTINGS.socket_path, {"cmd":"record_stop","action":action,"name":name})
    return await _ok(res)

async def api_play(request):
    payload = await request.json()
    file = payload.get("file")
    if not file:
        raise web.HTTPBadRequest(reason="missing file")
    args = {
        "cmd": "play",
        "file": file,
        "speed": float(payload.get("speed", 1.0)),
        "jitter_time": float(payload.get("jitter_time", 0.0)),
        "jitter_hold": float(payload.get("jitter_hold", 0.0)),
        "loop": int(payload.get("loop", 1)),
    }
    res = await send(SETTINGS.socket_path, args)
    return await _ok(res)

async def api_stop(request):
    res = await send(SETTINGS.socket_path, {"cmd":"stop"})
    return await _ok(res)

async def api_rename(request):
    payload = await request.json()
    old = payload.get("old")
    new = payload.get("new")
    if not old or not new:
        raise web.HTTPBadRequest(reason="missing names")
    src = _rec_path(old)
    dst = _rec_path(new)
    if not src.exists():
        raise web.HTTPNotFound(text="source missing")
    if dst.exists():
        raise web.HTTPConflict(text="destination exists")
    src.rename(dst)
    return await _ok({"renamed": [src.name, dst.name]})

async def api_delete(request):
    name = request.match_info["name"]
    p = _rec_path(name)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    return await _ok({"deleted": name})

# SSE: live event stream from msmacro.events
async def api_events(request):
    resp = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await resp.prepare(request)

    path = events_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).touch(exist_ok=True)

    try:
        with open(path, "r") as f:
            f.seek(0, os.SEEK_END)
            hb = 0
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.25)
                    hb += 1
                    if hb % 40 == 0:  # ~10s heartbeat
                        try:
                            await resp.write(b": hb\n\n")
                        except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
                            break
                    continue

                payload = line.strip().encode()
                try:
                    await resp.write(b"data: " + payload + b"\n\n")
                except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
                    # client went away; end cleanly
                    break
    finally:
        # With SSE, do not call write_eof(); the client closed the stream.
        pass

    return resp

# ---------- UI (static single page) ----------
INDEX_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>MS Macro</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:20px;max-width:900px}
h1{margin:0 0 10px}
#mode{display:inline-block;padding:4px 8px;border-radius:6px;background:#eee}
section{margin-top:18px;padding:12px;border:1px solid #ddd;border-radius:8px}
button{padding:8px 12px;margin:4px;border-radius:6px;border:1px solid #ccc;cursor:pointer}
input[type="number"]{width:80px}
table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #eee;padding:8px;text-align:left}
.badge{padding:2px 6px;border-radius:6px;background:#eee}
.small{font-size:12px;color:#666}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
</style>
</head>
<body>
  <h1>MS Macro <span id="mode" class="badge">...</span></h1>

  <section>
    <div class="row">
      <button id="btn-record">Record</button>
      <button id="btn-stop">Stop</button>
      <button id="btn-play">Play selected</button>
      <label>Speed <input id="speed" type="number" step="0.05" value="1.00"></label>
      <label>Jitter time <input id="jt" type="number" step="0.01" value="0.00"></label>
      <label>Jitter hold <input id="jh" type="number" step="0.01" value="0.00"></label>
      <label>Loop <input id="loop" type="number" step="1" value="1"></label>
    </div>
    <div class="small">Hotkeys: LALT+R (start record), LALT+Q (stop/playback/bridge choices)</div>
  </section>

  <section id="postrec" style="display:none; background:#fff7e6; border-color:#ffd591">
    <div class="row">
      <strong>Post-record options:</strong>
      <input id="savename" placeholder="file name (optional)" />
      <button id="ui-save">Save</button>
      <button id="ui-play-once">Play once</button>
      <button id="ui-discard">Discard</button>
      <span class="small">You can also press LCTL+S / LCTL+P / LCTL+D on the keyboard.</span>
    </div>
  </section>

  <section>
    <h3>Recordings</h3>
    <table id="files"><thead><tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr></thead><tbody></tbody></table>
  </section>

  <section>
    <h3>Events</h3>
    <pre id="events" style="max-height:240px;overflow:auto;background:#fafafa;border:1px solid #eee;padding:8px"></pre>
  </section>

<script>
const fmtBytes = b => (b<1024? b+' B' : b<1024*1024? (b/1024).toFixed(1)+' KB' : (b/1048576).toFixed(1)+' MB');
const fmtDate = t => new Date(t*1000).toLocaleString();

function showPostrec(on){ document.getElementById('postrec').style.display = on?'block':'none'; }

let selected = null;

async function refresh(){
  const r = await fetch('/api/status'); const j = await r.json();
  if(!j.ok) { document.getElementById('mode').innerText = 'daemon offline'; return; }
  document.getElementById('mode').innerText = j.result.mode;
  const tbody = document.querySelector('#files tbody'); tbody.innerHTML='';
  for(const f of j.result.files){
    const tr = document.createElement('tr');
    tr.innerHTML = '<td><a href="#" class="sel">'+f.name+'</a></td>'+
                   '<td>'+fmtBytes(f.size)+'</td>'+
                   '<td>'+fmtDate(f.mtime)+'</td>'+
                   '<td>'+
                   '<button class="rename">Rename</button>'+
                   '<button class="delete">Delete</button>'+
                   '</td>';
    tbody.appendChild(tr);
  }
}

document.addEventListener('click', async (e)=>{
  if(e.target.classList.contains('sel')){
    e.preventDefault();
    selected = e.target.textContent;
    document.querySelectorAll('.sel').forEach(a=>a.style.fontWeight='normal');
    e.target.style.fontWeight='bold';
  }
  if(e.target.id==='btn-record'){
    await fetch('/api/record/start', {method:'POST'});
  }
  if(e.target.id==='btn-stop'){
    await fetch('/api/stop', {method:'POST'});
  }
  if(e.target.id==='btn-play'){
    if(!selected){ alert('select a file first'); return; }
    const body = {
      file: selected,
      speed: parseFloat(document.getElementById('speed').value||'1'),
      jitter_time: parseFloat(document.getElementById('jt').value||'0'),
      jitter_hold: parseFloat(document.getElementById('jh').value||'0'),
      loop: parseInt(document.getElementById('loop').value||'1')
    };
    await fetch('/api/play', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  }
  if(e.target.classList.contains('rename')){
    const name = e.target.closest('tr').querySelector('.sel').textContent;
    const nn = prompt('New name (without path, .json optional):', name);
    if(!nn) return;
    await fetch('/api/files/rename', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({old:name, new:nn})});
    selected = nn.endsWith('.json')? nn : nn + '.json';
    refresh();
  }
  if(e.target.classList.contains('delete')){
    const name = e.target.closest('tr').querySelector('.sel').textContent;
    if(!confirm('Delete '+name+'?')) return;
    await fetch('/api/files/'+encodeURIComponent(name), {method:'DELETE'});
    if(selected===name) selected=null;
    refresh();
  }
  if(e.target.id==='ui-save'){
    const n = document.getElementById('savename').value.trim() || null;
    fetch('/api/record/stop', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'save', name:n})}).then(()=>{ showPostrec(false); refresh(); });
  }
  if(e.target.id==='ui-play-once'){
    fetch('/api/record/stop', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'play_now'})});
    // we keep the banner visible; daemon will re-open POSTRECORD after play
  }
  if(e.target.id==='ui-discard'){
    fetch('/api/record/stop', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'discard'})}).then(()=>{ showPostrec(false); });
  }

});

function startEvents(){
  const ev = document.getElementById('events');
  const es = new EventSource('/api/events');
  es.onmessage = (m)=>{
    try{
      const obj = JSON.parse(m.data);
      ev.textContent += JSON.stringify(obj)+'\\n';
      ev.scrollTop = ev.scrollHeight;
      if(obj.event==='SAVED' || obj.event==='DISCARDED' || obj.event==='PLAY_STOP'){ refresh(); }
      if(obj.event==='MODE'){ document.getElementById('mode').innerText = obj.mode; }
      if(obj.event==='MODE'){
        document.getElementById('mode').innerText = obj.mode;
        if(obj.mode==='POSTRECORD'){ showPostrec(true); }
        if(obj.mode==='BRIDGE'){ showPostrec(false); }
      }
      if(obj.event==='SAVED' || obj.event==='DISCARDED'){ showPostrec(false); refresh(); }
      if(obj.event==='PLAY_STOP'){ refresh(); /* menu will stay open since mode returns to POSTRECORD */ }
      if(obj.event==='CHOICE_MENU'){ showPostrec(true); }
    }catch(e){}
  };
}

refresh(); startEvents();
</script>
</body></html>
"""

async def ui_index(request):
    return web.Response(text=INDEX_HTML, content_type="text/html")

# ---------- app factory / main ----------
def make_app():
    app = web.Application()
    app.add_routes([
        web.get("/", ui_index),
        web.get("/api/status", api_status),
        web.post("/api/record/start", api_record_start),
        web.post("/api/record/stop", api_record_stop),
        web.post("/api/play", api_play),
        web.post("/api/stop", api_stop),
        web.post("/api/files/rename", api_rename),
        web.delete("/api/files/{name}", api_delete),
        web.get("/api/events", api_events),
    ])
    return app

def main(host="0.0.0.0", port=8787):
    app = make_app()
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    main(args.host, args.port)
