import { useRef, useEffect } from "react";

// ── Log display ───────────────────────────────────────────────────────────────
export function LogPanel({ log }: { log: any[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { 
    if (ref.current) 
        ref.current.scrollTop = ref.current.scrollHeight; 
  }, [log]);
  
  const cls = (t: string) => ({ 
        ok:"l-ok", 
        skip:"l-skip", 
        warn:"l-warn",
        error:"l-error", 
        track:"l-track", 
        done:"l-done" 
    }[t] || "");

  const summary = (log.find(l => l.type==="done") || {}).summary;

  if (!log.length) 
    return null;

  return (
    <div className="log-area" ref={ref}>
      {log.filter(l => l.type !== "done").map((l,i) => <div key={i} className={cls(l.type)}>{l.msg}</div>)}
      {summary && (
        <div className="summary">
          <div className="s-stat"><span className="s-val">{summary.pl_exported ?? summary.created+summary.updated}</span><span className="s-key">Playlists</span></div>
          {summary.tr_copied > 0 && <div className="s-stat"><span className="s-val">{summary.tr_copied}</span><span className="s-key">Tracks copied</span></div>}
          {summary.added_tracks > 0 && <div className="s-stat"><span className="s-val">{summary.added_tracks}</span><span className="s-key">Tracks added</span></div>}
          {summary.bytes_copied && summary.bytes_copied !== "—" && <div className="s-stat"><span className="s-val">{summary.bytes_copied}</span><span className="s-key">Data</span></div>}
          {summary.tr_skipped > 0 && <div className="s-stat"><span className="s-val" style={{color:"var(--muted)"}}>{summary.tr_skipped}</span><span className="s-key">Skipped</span></div>}
          {summary.tr_missing > 0 && <div className="s-stat"><span className="s-val" style={{color:"var(--error)"}}>{summary.tr_missing}</span><span className="s-key">Not found</span></div>}
          {summary.created  > 0 && <div className="s-stat"><span className="s-val">{summary.created}</span><span className="s-key">Created</span></div>}
          {summary.updated  > 0 && <div className="s-stat"><span className="s-val" style={{color:"var(--warn)"}}>{summary.updated}</span><span className="s-key">Updated</span></div>}
        </div>
      )}
    </div>
  );
}
