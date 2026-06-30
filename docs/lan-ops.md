# EquiSense Lite — Mac + iPhone LAN Operations Guide

This guide covers everything you need to run a reliable live-feed session between
your **MacBook** (backend + dashboard) and **iPhone** (recorder) over a local
Wi-Fi network.  It is written for macOS Ventura / Sonoma and iOS 16+.

---

## 1  Prerequisites checklist

| Item | Confirmed? |
|------|-----------|
| MacBook and iPhone on the **same Wi-Fi network** | ☐ |
| Backend running on Mac (`make dev-backend`) | ☐ |
| Frontend running on Mac (`make dev-frontend`) | ☐ |
| iOS app configured with Mac's **LAN IP** (not `localhost`) | ☐ |
| macOS Firewall allows inbound on port **8000** | ☐ |

---

## 2  Find your Mac's LAN IP

Open **Terminal** and run:

```bash
ipconfig getifaddr en0   # Wi-Fi (most common on MacBook)
# If that returns nothing, try:
ipconfig getifaddr en1
# Or list all interfaces:
ifconfig | grep "inet " | grep -v 127.0.0.1
```

The result will look like `192.168.1.42`.  Use this IP everywhere below.

> **Why not `localhost`?**  From the iPhone, `localhost` resolves to the
> *iPhone itself*, not the Mac.  Always use the numeric LAN IP.

---

## 3  Start the backend

```bash
cd backend
make dev-backend   # uvicorn on 0.0.0.0:8000 (listens on all interfaces)
```

Verify it is reachable from the Mac:

```bash
curl http://localhost:8000/health   # → {"status":"ok"}
```

Verify from the iPhone (Safari or a terminal on the same network):

```
http://192.168.1.42:8000/health
```

---

## 4  Configure the iOS app

Open the **Settings** tab in EquiSenseLiteRecorder and set:

| Field | Value |
|-------|-------|
| API Base URL | `http://192.168.1.42:8000` *(replace with your Mac IP)* |
| API Token | `dev-token` (or your `API_TOKEN` env value) |

Tap **Save** and verify with the built-in **Test Connection** button (health
check turns green).

---

## 5  macOS Firewall

If the iPhone cannot reach the Mac, the firewall is the most common cause.

1. **System Settings → Network → Firewall → Options…**
2. Confirm the firewall is **on** (recommended) but that incoming connections
   are allowed for `uvicorn` / Python.
3. The quickest test: temporarily disable the firewall, re-test, then re-enable
   and add an explicit allow rule for port 8000.

Alternatively, allow the port via Terminal:

```bash
# Allow inbound TCP on port 8000 (requires admin password)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp $(which python3)
```

---

## 6  WebSocket — `ws://` vs `wss://`

| Scenario | Protocol |
|----------|----------|
| Local LAN (dev) | `ws://` — the frontend derives this automatically from `VITE_API_URL=http://…` |
| Production (Render + Netlify) | `wss://` — derived automatically from `VITE_API_URL=https://…` |

You **never** need to configure the WS URL manually.  The frontend replaces
`http` with `ws` (and `https` with `wss`) at runtime.

---

## 7  Live-feed quick-start sequence

```
1. make dev-backend      (Mac Terminal 1)
2. make dev-frontend     (Mac Terminal 2)
3. Open http://localhost:5173 in Safari/Chrome on the Mac
4. Enter API token in the Token field
5. Open EquiSenseLiteRecorder on iPhone
6. Settings → set Base URL to http://<mac-ip>:8000
7. Horse & Session tab → Start Session (note the session ID)
8. Recording tab → Start Recording
9. Mac dashboard: live panel appears automatically within ~1 s
```

---

## 8  Health indicators (Phase 6.1)

The live panel now shows a health bar below the status badge:

| Indicator | Meaning |
|-----------|---------|
| **Rate** | Effective sample rate received at the browser (Hz). Expected ~50 Hz at 50 Hz recording cadence. |
| **Latency** | `now − latest sample ts_ms` — end-to-end delay from sensor capture to browser display. Green < 500 ms, amber < 2 s, red ≥ 2 s. |
| **Buffer** | Total samples in the rolling window (max 1 500). |

Use the **⏸ Pause** button to freeze the chart without disconnecting the
WebSocket (useful during demo commentary).

---

## 9  Backend stream-metrics endpoint

For operator debugging, an authenticated endpoint returns live-feed statistics:

```
GET /sessions/{session_id}/live/stats
Header: X-API-Token: <token>
```

Example response:

```json
{
  "session_id": 42,
  "active_subscribers": 1,
  "ingest_count": 312,
  "broadcast_count": 287,
  "coalesced_count": 25,
  "queue_drop_count": 0,
  "ingest_rate_per_s": 4.93,
  "broadcast_rate_per_s": 4.56
}
```

| Field | Description |
|-------|-------------|
| `ingest_count` | Total `live-ingest` POST calls received |
| `broadcast_count` | Calls that were actually broadcast to subscribers |
| `coalesced_count` | Calls skipped by the 50 ms rate limiter |
| `queue_drop_count` | Items dropped from subscriber queues (backpressure) |
| `ingest_rate_per_s` | Rolling 5-second ingest rate |
| `broadcast_rate_per_s` | Rolling 5-second broadcast rate |

---

## 10  Troubleshooting matrix

### iPhone can record but live chart never appears

| Check | Action |
|-------|--------|
| Same Wi-Fi? | Both devices must be on the same SSID |
| Correct base URL? | Must be `http://<mac-ip>:8000`, not `localhost` |
| Backend running? | `curl http://<mac-ip>:8000/health` from iPhone browser |
| macOS Firewall? | See §5 above |
| Token mismatch? | iOS app token must match `API_TOKEN` env var on backend |
| Session active? | Live panel only shows for a session that has been started |

### Repeated reconnect loops

| Check | Action |
|-------|--------|
| Backend crashed? | Check Terminal 1 for Python tracebacks |
| Wi-Fi interference? | Move devices closer to the router |
| IP changed mid-session? | Mac DHCP lease renewed; restart iOS app with new IP |
| Token wrong? | WS close code 4001 = auth failure — check token |
| Session ID wrong? | WS close code 4004 = session not found |

### High latency / stutter

| Check | Action |
|-------|--------|
| Wi-Fi congestion | Use 5 GHz band if router supports it |
| Backend CPU? | Coalescing kicks in at > 20 msg/s — check `coalesced_count` in stats |
| Slow browser tab? | Chrome DevTools → Performance; check for long tasks |
| Buffer too large? | Click **Clear** to flush the rolling buffer |
| iOS background throttling? | Keep the iPhone screen on during recording |

### Chart is paused / frozen (Pause button visible)

Click **▶ Resume** in the panel header.  Pausing stops buffer updates but
keeps the WebSocket alive, so no data is lost at the backend.

---

## 11  Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `API_TOKEN` | `dev-token` | Shared secret for all API and WS auth |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL used by the frontend |
| `LIVE_MIN_BROADCAST_INTERVAL` | `0.05` | Minimum seconds between WS broadcasts (coalescing) |
| `LIVE_SUBSCRIBER_QUEUE_SIZE` | `50` | Max items in per-subscriber outgoing queue |

Change `LIVE_MIN_BROADCAST_INTERVAL` to `0.1` (100 ms) if you notice high
`coalesced_count` on a congested network; this reduces broadcast rate by half
while keeping the chart visually smooth.

---

## 12  Network diagram

```
iPhone (Wi-Fi)
  └─ POST /sessions/{id}/live-ingest  every ~200 ms
       └─ FastAPI (Mac, 0.0.0.0:8000)
            ├─ per-session metrics (ingest/broadcast/coalesced/drops)
            └─ WS broadcast → per-subscriber bounded queue (drop-oldest)
                  └─ Mac browser (ws://localhost:8000/sessions/{id}/live)
                        └─ LiveFeedPanel (rolling chart, health bar, pause/resume)
```
