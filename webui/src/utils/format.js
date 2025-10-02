export function formatBytes(n){
    if(!Number.isFinite(n)) return '-';
    const u=['B','KB','MB','GB'];
    let i=0, v=n;
    while(v>=1024 && i<u.length-1){ v/=1024; i++; }
    return `${v.toFixed(i===0?0:1)} ${u[i]}`;
  }
  export function formatMTime(ts){
    if(!Number.isFinite(ts)) return '-';
    try{ return new Date(ts*1000).toLocaleString(); }catch{ return '-'; }
  }
  