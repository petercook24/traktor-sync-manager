const BASE = "http://localhost:5123";

export const api = async (url: string, opts?: any) => { 
    const r = await fetch(BASE + url, opts); 
    return r.json(); 
};

// Heartbeat — tell the server we're still alive every 3 seconds
// When the tab closes, pings stop and the server shuts itself down
setInterval(() => {
  fetch(BASE + "/api/heartbeat", { method: "POST" }).catch(() => {});
}, 3000);
