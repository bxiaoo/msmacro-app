import { ensureJson, splitPath, joinPath } from '../utils/paths.js';

// Build a hierarchical tree from status.tree items (or from strings)
export function buildTree(items){
  const ROOT = new Map();

  const ensureDir = (parts) => {
    let cur = ROOT;
    let accum = '';
    for(const part of parts){
      accum = accum ? `${accum}/${part}` : part;
      if(!cur.has(part)){
        cur.set(part, { type:'dir', name: part, rel: accum, children: new Map() });
      }
      const node = cur.get(part);
      cur = node.children;
    }
    return cur;
  };

  for(const raw of (items||[])){
    let rel = '';
    if(typeof raw === 'string'){
      rel = ensureJson(raw);
    } else if(raw && typeof raw === 'object'){
      // status.tree provides { name: 'a/b/c', path, size, mtime }
      rel = ensureJson(raw.name || raw.rel || '');
    }
    rel = String(rel).replace(/^\/+/, '');
    if(!rel) continue;

    const parts = splitPath(rel);
    const fileName = parts.pop();
    const dirMap = ensureDir(parts);
    dirMap.set(`__file__:${joinPath(...parts, fileName)}`, {
      type:'file',
      name:fileName,
      rel: joinPath(...parts, fileName),
      size: Number(raw?.size || 0),
      mtime: Number(raw?.mtime || 0),
      meta: raw?.meta
    });
  }

  const toArray = (m) => {
    const out = [];
    for(const [key, val] of m){
      if(key.startsWith('__file__:')) out.push(val);
      else out.push({ ...val, children: toArray(val.children || new Map()) });
    }
    // sort: dirs first by name, then files by mtime desc then name
    out.sort((a,b)=>{
      if(a.type!==b.type) return a.type==='dir'?-1:1;
      if(a.type==='dir') return a.name.localeCompare(b.name);
      return (b.mtime - a.mtime) || a.name.localeCompare(b.name);
    });
    return out;
  };

  return toArray(ROOT);
}

export function flattenFiles(nodes){
  const out=[];
  for(const n of (nodes||[])){
    if(n.type==='file') out.push(n);
    else if(n.type==='dir') out.push(...flattenFiles(n.children));
  }
  return out;
}
