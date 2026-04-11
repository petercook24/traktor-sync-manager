import { useState, useRef, useEffect } from "react";
import { api } from "../utils/api";
import { PlaylistPicker } from "./playlistPicker";
import { FolderBrowser } from "./folderBrowser";
import { LogPanel } from "./logPanel";

// ── Export Tab ────────────────────────────────────────────────────────────────
export function ExportTab({ log, setLog, setExporting, exporting } : { log: any[]; setLog: (value: any[] | ((prev: any[]) => any[])) => void; setExporting: (value: boolean | ((prev: boolean) => boolean)) => void; exporting: boolean }) {
  const [nmlPath, setNmlPath]     = useState("");
  const [playlists, setPlaylists] = useState([]);
  const [selected, setSelected]   = useState(new Set<string>());
  const [dest, setDest]           = useState("");
  const [copyTracks, setCopy]     = useState(true);
  const [loading, setLoading]     = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api("/api/detect-nml").then(d => { if (d.path) { 
      setNmlPath(d.path); 
      load(d.path); 
    } });
  }, []);

  const load = async (path: string | null) => {
    if (!path) 
      return;
    setLoading(true); 
    setPlaylists([]);
    const d = await api(`/api/parse-nml?path=${encodeURIComponent(path)}`);
    setLoading(false);
    if (d.playlists) { 
      setPlaylists(d.playlists); 
      setSelected(new Set(d.playlists.map((p: { name: string }) => p.name))); }
  };

  const startExport = async () => {
    if (!nmlPath || !dest || !selected.size) 
      return;
    setLog([]); 
    setExporting(true);
    await api("/api/export", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ nml_path: nmlPath, dest, selected: [...selected], copy_tracks: copyTracks }) });
    
    pollRef.current = setInterval(async () => {
      const d = await api("/api/progress");
      setLog(d.log || []);
      if (d.done) { 
        if (pollRef.current) 
          clearInterval(pollRef.current);

        setExporting(false); 
      }
    }, 400);
  };

  return (
    <div className="page">
      <div className="path-row">
        <span className="path-label">collection.nml</span>
        <input className="path-input" value={nmlPath} onChange={e => setNmlPath(e.target.value)}
          placeholder="Path to collection.nml…" onKeyDown={e => e.key==="Enter" && load(nmlPath)}/>
        <button className="btn sm" onClick={() => load(nmlPath)} disabled={!nmlPath||loading}>
          {loading ? <span className="spin"/> : "Load"}
        </button>
      </div>

      <div className="columns">
        <div className="col">
          <div className="col-header">
            <span className="col-title">Traktor Playlists</span>
            <span style={{fontFamily:"DM Mono,monospace",fontSize:"0.67rem",color:"var(--muted)"}}>{selected.size}/{playlists.length}</span>
          </div>
          <div className="col-body">
            <PlaylistPicker playlists={playlists} selected={selected} setSelected={setSelected} loading={loading}/>
          </div>
        </div>

        <div className="col">
          <div className="col-header"><span className="col-title">Destination Folder</span></div>
          <div className="col-body">
            <FolderBrowser onSelect={setDest}/>
          </div>
        </div>
      </div>

      <div className="bottom-bar">
        <div className="bottom-info">
          <strong>{selected.size}</strong> playlist{selected.size!==1?"s":""} selected
          {dest && <> → <strong style={{color:"var(--accent)"}}>{dest}</strong></>}
        </div>
        <div className="toggle-row">
          <div className={`toggle ${copyTracks?"on":""}`} onClick={() => setCopy(v=>!v)}>
            <div className="toggle-knob"/>
          </div>
          Copy audio
        </div>
        <button className="btn accent" onClick={startExport} disabled={!nmlPath||!dest||!selected.size||exporting}>
          {exporting ? <><span className="spin"/> Exporting…</> : "Export →"}
        </button>
      </div>
      <LogPanel log={log}/>
    </div>
  );
}
