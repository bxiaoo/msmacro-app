export async function getStatus(){
    const r = await fetch('/api/status'); if(!r.ok) throw new Error('status');
    return r.json();
}
export async function startRecord(){ await fetch('/api/record/start',{method:'POST'}); }
export async function stopRecord(action, name){
    const body = { action }; if(name) body.name = name;
    const r = await fetch('/api/record/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    return r.json();
}
export async function play(file, opts){
    const r = await fetch('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file, ...opts})});
    return r.json();
}
export async function stop(){ await fetch('/api/stop',{method:'POST'}); }
export async function renameFile(oldName, newName){
    const r = await fetch('/api/files/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old:oldName,new:newName})});
    return r.json();
}
export async function deleteFile(name){ await fetch(`/api/files/${encodeURIComponent(name)}`,{method:'DELETE'}); }
