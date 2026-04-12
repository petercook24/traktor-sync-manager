import { useState, useRef, useEffect } from "react";
import { PlaylistPicker } from "./playlistPicker";
import { LogPanel } from "./logPanel";
import { api } from "../utils/api";
 interface ItunesTabProps {
  log: any[]; 
  setLog: (value: any[] | ((prev: any[]) => any[])) => void; 
  setExporting: (value: boolean | ((prev: boolean) => boolean)) => void; 
  exporting: boolean 
}

// ── iTunes Sync Tab ───────────────────────────────────────────────────────────
export function ItunesTab({ log, setLog, setExporting, exporting } : ItunesTabProps ) {

  const [itunesPath, setItunesPath] = useState("");
  const [nmlPath, setNmlPath]       = useState("");
  const [playlists, setPlaylists]   = useState([]);
  const [selected, setSelected]     = useState(new Set<string>());
  const [loading, setLoading]       = useState(false);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    api("/api/detect-itunes").then(d => { 
      if (d.path) { 
        setItunesPath(d.path); 
        load(d.path); 
      }
    });

    api("/api/detect-nml").then(d => { 
      if (d.path) 
        setNmlPath(d.path); 
      });

  }, []);

  const load = async (path: string | null) => {
    if (!path) 
      return;
    setLoading(true); 
    setPlaylists([]);
    const d = await api(`/api/parse-itunes?path=${encodeURIComponent(path)}`);
    setLoading(false);
    if (d.playlists) { 
      setPlaylists(d.playlists); 
      setSelected(new Set<string>(d.playlists.map((p: { name: string }) => p.name))); 
    }
    if (d.error) 
      alert("Error: " + d.error);
  };

  const startSync = async () => {
    if (!itunesPath || !nmlPath || !selected.size) 
      return;

    setLog([]); 
    setExporting(true);

    await api("/api/sync-itunes", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ itunes_path: itunesPath, nml_path: nmlPath, selected: [...selected] }) });

    pollRef.current = setInterval(async () => {
        const d = await api("/api/progress");
        setLog(d.log || []);
        if (d.done) { 

          if(pollRef.current) 
            clearInterval(pollRef.current);

          setExporting(false); 
        }
    }, 400);
  };

  return (
    <div className="page">
      <div className="path-row">
        <span className="path-label">iTunes XML</span>
        <input className="path-input" value={itunesPath} onChange={e => setItunesPath(e.target.value)}
          placeholder="Path to iTunes Music Library.xml…" onKeyDown={e => e.key==="Enter" && load(itunesPath)}/>
        <button className="btn sm" onClick={() => load(itunesPath)} disabled={!itunesPath||loading}>
          {loading ? <span className="spin"/> : "Load"}
        </button>
      </div>

      <div className="path-row" style={{borderTop:"none"}}>
        <span className="path-label">collection.nml</span>
        <input className="path-input" value={nmlPath} onChange={e => setNmlPath(e.target.value)}
          placeholder="Path to Traktor collection.nml…"/>
      </div>

      <div className="columns">
        <div className="col">
          <div className="col-header">
            <span className="col-title">iTunes Playlists</span>
            <span style={{fontFamily:"DM Mono,monospace",fontSize:"0.67rem",color:"var(--muted)"}}>{selected.size}/{playlists.length}</span>
          </div>
          <div className="col-body">
            <PlaylistPicker playlists={playlists} selected={selected} setSelected={setSelected} loading={loading}/>
          </div>
        </div>

        <div className="col">
          <div className="col-header"><span className="col-title">What happens</span></div>
          <div className="col-body">
            <div style={{fontSize:"0.83rem", lineHeight:1.8, color:"var(--muted)"}}>
              <p style={{color:"var(--text)", marginBottom:12}}>
                Selected iTunes playlists will be created or updated directly inside your Traktor <code style={{color:"var(--accent)"}}>collection.nml</code>.
              </p>
              <p>• Tracks already in Traktor's collection are matched and reused.</p>
              <p>• New tracks are added to Traktor's <strong style={{color:"var(--text)"}}>COLLECTION</strong>.</p>
              <p>• If a playlist with the same name exists in Traktor it will be <strong style={{color:"var(--warn)"}}>replaced</strong>.</p>
              <p>• Audio files are <strong style={{color:"var(--text)"}}>not moved</strong> — only the references are updated.</p>
              <p style={{marginTop:12, color:"var(--warn)"}}>⚠ Close Traktor before syncing.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bottom-bar">
        <div className="bottom-info">
          <strong>{selected.size}</strong> iTunes playlist{selected.size!==1?"s":""} will sync to Traktor
        </div>
        <button className="btn accent" onClick={startSync} disabled={!itunesPath||!nmlPath||!selected.size||exporting}>
          {exporting ? <><span className="spin"/> Syncing…</> : "Sync to Traktor →"}
        </button>
      </div>
      <LogPanel log={log}/>
    </div>
  );
}
