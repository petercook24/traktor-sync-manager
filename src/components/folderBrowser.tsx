import { useState, useCallback, useEffect } from "react";
import { api } from "../utils/api";

// ── Folder browser ────────────────────────────────────────────────────────────
export function FolderBrowser({ onSelect } : { onSelect: (value: string) => void }) {

  const [current, setCurrent] = useState<string | null>(null);
  const [dirs, setDirs]       = useState<string[]>([]);
  const [drives, setDrives]   = useState<string[]>([]);
  const [parent, setParent]   = useState<string | null>(null);
  const [newName, setNewName] = useState<string>("");
  const [selected, setSelected] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const browse = useCallback(async (path: string | null) => {
    setLoading(true);
    const d = await api(`/api/browse${path ? "?path=" + encodeURIComponent(path) : ""}`);
    setLoading(false);
    if (d.error) 
        return;
    setCurrent(d.current || null); 
    setDirs(d.dirs || []);
    setDrives(d.drives || []); 
    setParent(d.parent || null);
  }, []);

  useEffect(() => { browse(""); }, []);

  const mkdir = async () => {
    if (!newName.trim() || !current) 
        return;
    const d = await api("/api/mkdir", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ parent: current, name: newName.trim() }) });
    if (d.path) { 
        setNewName(""); 
        browse(d.path); 
    }
  };

  const short = (p: string | null) => p ? p.replace(/\\/g,"/").split("/").filter(Boolean).pop() || p : "";

  return (
    <div style={{display:"flex", flexDirection:"column", height:"100%", minHeight:0}}>
      {current
        ? <div className="breadcrumb">📂 <strong>{current}</strong></div>
        : <div className="breadcrumb">Choose a drive</div>}

      {/* scrollable folder list */}
      <div style={{flex:1, overflowY:"auto", minHeight:0}}>
        {current && parent &&
          <div className="f-item up-row" onClick={() => browse(parent)}>↩ Go up</div>}
        {!current && drives.map(d =>
          <div key={d} className="f-item drive-row" onClick={() => browse(d)}>💾 {d}</div>)}
        {current &&
          <div className="f-item drive-row" onClick={() => { setCurrent(null); setDirs([]); browse(""); }}>
            💾 <span style={{color:"var(--muted)"}}>Switch drive…</span>
          </div>}
        {loading && <div className="empty"><span className="spin"/> Loading…</div>}
        {dirs.map(d => <div key={d} className="f-item" onClick={() => browse(d)}>📁 {short(d)}</div>)}
        {!loading && current && dirs.length === 0 && <div className="empty">Empty folder</div>}
      </div>

      <div className="f-actions">
        <div className="new-folder-row">
          <input className="nf-input" placeholder="New folder name…" value={newName}
            onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key==="Enter" && mkdir()}/>
          <button className="btn sm" onClick={mkdir} disabled={!newName.trim()||!current}>+ Create</button>
        </div>
        <button className="btn sm accent" onClick={() => { if (current) { setSelected(current); onSelect(current); }}} disabled={!current}>
          ✅ Select
        </button>
      </div>
      {selected && <div className="dest-badge">✓ {selected}</div>}
    </div>
  );
}