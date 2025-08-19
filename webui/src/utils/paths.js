export const ensureJson = (s) => (s && !/\.json$/i.test(s) ? `${s}.json` : s);
export const stripLeadingSlash = (s) => (s || '').replace(/^\/+/, '');
export const splitPath = (s) => stripLeadingSlash(s).split('/').filter(Boolean);
export const joinPath = (...parts) => parts.filter(Boolean).join('/');
export const dirname = (s) => { const p = splitPath(s); p.pop(); return p.join('/') ; };
export const basename = (s) => { const p = splitPath(s); return p.pop() || '' ; };
