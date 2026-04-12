interface Playlist {
  name: string;
  count: number;
}

interface PlaylistPickerProps {
  playlists: Playlist[];
  selected: Set<string>;
  setSelected: (value: Set<string> | ((prev: Set<string>) => Set<string>)) => void;
  loading: boolean;
}

export function PlaylistPicker({ playlists, selected, setSelected, loading }: PlaylistPickerProps) {
  const all  = () => setSelected(new Set(playlists.map(p => p.name)));
  const none = () => setSelected(new Set());
  const toggle = (name: string) => setSelected(prev => {
    const n = new Set(prev); 
    n.has(name) ? n.delete(name) : n.add(name); 
    return n;
  });

  return (
    <>
      {playlists.length > 0 && (
        <div className="pl-controls">
          <button className="btn sm" onClick={all}>All</button>
          <button className="btn sm" onClick={none}>None</button>
        </div>
      )}
      {loading && <div className="empty"><span className="spin"/> Parsing…</div>}
      {!loading && playlists.length === 0 && <div className="empty">No playlists loaded.</div>}
      {playlists.map(pl => (
        <div key={pl.name} className={`pl-item ${selected.has(pl.name) ? "on" : ""}`} onClick={() => toggle(pl.name)}>
          <div className="chk">{selected.has(pl.name) && <span className="chk-mark">✓</span>}</div>
          <span className="pl-name">{pl.name}</span>
          <span className="pl-count">{pl.count} trk</span>
        </div>
      ))}
    </>
  );
}