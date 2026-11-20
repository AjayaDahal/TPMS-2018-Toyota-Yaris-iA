# 04 — Interactive 3-D Viewer & Renders (TPMS Monitor Panel)

Offline Three.js r160 interactive 3-D engineering inspector matching the Mach-X template.

```bash
python3 04-viewer/make_viewer.py
python3 04-viewer/serve_viewer.py    # -> http://127.0.0.1:28776/viewer/
```

- `viewer/` — Offline Three.js r160 viewer (`index.html`, `style.css`, `app.js`, `manifest.json`, `vendor/`, `parts/` exported from `tpms_panel.step`, `media/`)
- `renders/` — KiCad 10 front, back, and isometric ray-traced PCB renders
