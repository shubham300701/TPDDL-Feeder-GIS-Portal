"""
TATA Power-DDL Feeder GIS & SLD Portal - Root Launcher
Delegates directly to web_gis.server.app
"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from web_gis.server import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[GIS SERVER] Starting TATA Power-DDL GIS Portal on http://{host}:{port} ...")
    uvicorn.run("web_gis.server:app", host=host, port=port, reload=False)
