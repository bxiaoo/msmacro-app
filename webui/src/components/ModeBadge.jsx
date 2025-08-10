export default function ModeBadge({ mode }){
    return <span className="badge">{mode || '...'}</span>;
}
