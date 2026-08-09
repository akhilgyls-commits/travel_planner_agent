# Departures — Frontend

A static, no-build-step web UI for the Travel Planning Agent API. Vanilla
HTML/CSS/JS — no npm install required.

**Design concept:** a departures-board and boarding-pass idiom. The trip
request is framed as a boarding pass; the generated itinerary appears as a
torn ticket stub; follow-up questions go through a "control tower"
transmission log. See `styles.css` for the full token system (colors, type).

## Run it

You need the backend API running first (see the root `README.md` /
`ACTIVATION.md`).

**Option A — open directly:**
Just open `index.html` in a browser. Some browsers restrict `fetch()` from
`file://` pages — if requests silently fail, use Option B instead.

**Option B — tiny local server (recommended):**
```bash
cd frontend
python -m http.server 5173
```
Then visit http://localhost:5173.

**Option C — Docker (served via nginx):**
From the project root:
```bash
docker compose up --build
```
This starts both the API (port 8000) and the frontend (port 5173) together.
Visit http://localhost:5173.

## Configuring the API URL

By default the frontend calls `http://localhost:8000/api/v1`. If your API
runs elsewhere, click **API settings** in the top bar and enter the new base
URL — it's saved in `localStorage` so you only need to do this once per
browser.

## Files

| File | Purpose |
|---|---|
| `index.html` | Page structure |
| `styles.css` | Design tokens + all styling |
| `app.js` | API calls, form handling, chat/session logic (no dependencies except `marked` + `DOMPurify` from CDN, used to safely render the itinerary's Markdown) |
| `Dockerfile` / `nginx.conf` | Static-file container for deployment |
