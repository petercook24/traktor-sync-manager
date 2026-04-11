import { useState } from "react";
import { ExportTab } from "./components/exportTab";
import { ItunesTab } from "./components/iTunesTab";

// ── App root ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]         = useState("export");
  const [log, setLog]         = useState<any[]>([]);
  const [exporting, setExp]   = useState(false);

  return (
    <div className="shell">
      <header>
        <h1>Traktor Exporter</h1>
        <span>playlist export &amp; sync tool</span>
      </header>
      <div className="tabs">
        <div className={`tab ${tab==="export"?"active":""}`} onClick={() => setTab("export")}>Export to USB</div>
        <div className={`tab ${tab==="itunes"?"active":""}`} onClick={() => setTab("itunes")}>Sync from iTunes</div>
      </div>
      {tab === "export"
        ? <ExportTab log={log} setLog={setLog} exporting={exporting} setExporting={setExp}/>
        : <ItunesTab log={log} setLog={setLog} exporting={exporting} setExporting={setExp}/>}
    </div>
  );
}