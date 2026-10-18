# TATA Power-DDL Feeder GIS & Single Line Diagram (SLD) Portal

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900.svg)](https://leafletjs.com/)
[![Coverage](https://img.shields.io/badge/Poles%20Plotted-100%25%20(7%2C828%2F7%2C828)-success.svg)]()
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

An enterprise-grade, high-performance Web GIS and Single Line Diagram (SLD) network portal engineered for **Tata Power Delhi Distribution Limited (TPDDL)** covering **Zone 515 (Mangolpuri)** and **Zone 518 (Sultanpuri)**.

---

## ⚡ Key Highlights & Verified Database Metrics

* **Total Consumers Connected:** **136,355**
* **Total Network Poles:** **7,828** (100.0% fully resolved & plotted)
* **Total Connected Load:** **271.6 MW** (271,626 kW)
* **Primary Grid Substations:** **9 Grids** (Mangol Puri 1 & 2, Rohini 2, 20, 22, P.P. 2, and interconnects)
* **11kV Trunk Feeders:** **39 Trunk Lines**
* **11kV Sub-Feeders (Branch Lines):** **208 Lines**
* **Distribution Transformers (DTs):** **1,680 DTs**
* **Zone 515 (Mangolpuri):** 63,545 consumers | 3,061 poles | 142.2 MW load | 5 grids
* **Zone 518 (Sultanpuri):** 72,810 consumers | 4,767 poles | 129.4 MW load | 4 grids

---

## 🚀 Salient Portal Features

1. **Enterprise Feeder GIS Map:**
   * High-resolution Google Maps Street, Satellite Hybrid, and OpenStreetMap basemaps.
   * Real-time map rotation and live 360° interactive compass with bearing indicator.
   * Feeder line Minimum Spanning Tree (MST) route tracing with customizable max-span thresholds.
   * On-map filter drawer positioned directly below Leaflet zoom controls.
   * Detailed pole inspection modal with Google Street View / Directions links.

2. **Interactive Single Line Diagram (SLD):**
   * Grid &rarr; Trunk Feeder &rarr; Sub-Feeder &rarr; Substation &rarr; Distribution Transformer (DT) electrical hierarchy tree.
   * Real-time search, load metrics (kW), consumer counts, and DT drilldown modals with CSV export.

3. **Master Consumer Directory:**
   * Rapid search by Consumer Account (CA) number, Meter number, Pole ID, or address.
   * Segment filtering for **High Commercial (HCB)**, **Small Commercial (SCB)**, and **High Revenue (HRB)**.
   * 1-click zoom to pole coordinates directly on the GIS map.

4. **Distribution Network Outage & Fault Simulator:**
   * Outage planning mode with hierarchical cascading selectors for Trunk, Sub-Feeder, DT, and Pole.
   * Real-time calculation of dropped load (kW) and affected consumers.
   * Visual outage impact highlighting directly on the map.

5. **Executive Analytics Dashboard:**
   * Breakdown of consumer segments, load distributions, and pole resolution telemetry.

---

## 💻 Local Quick Start (Windows)

Simply double-click the included batch launcher:
```text
START_FEEDER_GIS_PORTAL.bat
```
This launcher will automatically:
1. Verify Python 3.10+ installation.
2. Install dependencies (`fastapi`, `uvicorn`) if missing.
3. Automatically extract the high-compression SQLite network database (`network_gis.db.gz`).
4. Start the local server and open your default browser to `http://127.0.0.1:8000`.

### Manual CLI Start:
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python server.py
# Or: uvicorn web_gis.server:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## ☁️ Free Cloud Deployment on Render.com

Deploy this portal online for free:

### Method 1: Using the Render Dashboard (Web UI)
1. Go to [Render.com](https://dashboard.render.com/) and sign in (using GitHub).
2. Click **New +** &rarr; **Web Service**.
3. Connect your repository: `shubham300701/TPDDL-Feeder-GIS-Portal`.
4. Configure the settings:
   * **Name:** `tpddl-feeder-gis-portal`
   * **Region:** Any (e.g. `Oregon (US West)` or `Frankfurt (EU Central)`)
   * **Branch:** `main`
   * **Root Directory:** *(leave blank)*
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python server.py`
   * **Instance Type:** `Free`
5. Click **Create Web Service**.
6. Render will build and deploy the application. Your free live URL will be ready at:
   `https://tpddl-feeder-gis-portal.onrender.com`

### Method 2: Render Blueprint (render.yaml)
1. In Render, select **New +** &rarr; **Blueprint**.
2. Connect `shubham300701/TPDDL-Feeder-GIS-Portal`.
3. Render reads the included `render.yaml` automatically and configures the web service in 1 click!

---

## 📁 Repository Structure

```text
TPDDL-Feeder-GIS-Portal/
├── server.py                  # Root application launcher for Render & local
├── requirements.txt           # Python dependencies (FastAPI, Uvicorn)
├── render.yaml                # Render.com Cloud Deployment Blueprint
├── START_FEEDER_GIS_PORTAL.bat# 1-Click Windows Local Launcher
├── network_gis.db.gz          # High-compression SQLite database (11.7 MB, extracts to 92 MB)
├── .gitignore                 # Excludes raw large uncompressed DB and cache
├── README.md                  # Comprehensive Documentation
└── web_gis/
    ├── server.py              # FastAPI Backend REST API & DB Queries
    ├── network_gis.db.gz      # Backup compressed database
    └── static/
        ├── index.html         # Modern Responsive GIS & SLD Single Page Application
        ├── leaflet-rotate.js  # Map rotation & bearing support
        └── tpddl_logo_clean.png
```

---

## 🛡️ License & Attribution
Proprietary network management software designed for **Tata Power Delhi Distribution Limited (TPDDL)**.
Developed by **Shubham** (`@shubham300701`).
