import os
import sys
import math
import re
import json
import sqlite3
import csv
import io
import gzip
import shutil
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

def resolve_db_path() -> str:
    """Finds network_gis.db or auto-decompresses network_gis.db.gz if needed."""
    candidate_dbs = [
        os.path.join(BASE_DIR, "network_gis.db"),
        os.path.join(PROJECT_DIR, "network_gis.db"),
    ]
    for p in candidate_dbs:
        if os.path.exists(p) and os.path.getsize(p) > 1000000:
            return p

    candidate_gzs = [
        os.path.join(BASE_DIR, "network_gis.db.gz"),
        os.path.join(PROJECT_DIR, "network_gis.db.gz"),
    ]
    for gz in candidate_gzs:
        if os.path.exists(gz):
            target = gz[:-3]  # Strip .gz
            print(f"[GIS SERVER] Extracting compressed database {gz} -> {target}...")
            with gzip.open(gz, 'rb') as f_in, open(target, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            print(f"[GIS SERVER] Extracted successfully: {os.path.getsize(target)/(1024*1024):.1f} MB")
            return target

    return os.path.join(BASE_DIR, "network_gis.db")

def resolve_static_dir() -> str:
    candidates = [
        os.path.join(BASE_DIR, "static"),
        os.path.join(PROJECT_DIR, "static"),
        os.path.join(BASE_DIR, "web_gis", "static")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(BASE_DIR, "static")

DB_PATH = resolve_db_path()
STATIC_DIR = resolve_static_dir()

app = FastAPI(title="Tata Power-DDL Feeder GIS & SLD Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

PALETTE = [
    "#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED",
    "#0891B2", "#EA580C", "#4F46E5", "#16A34A", "#9333EA",
    "#0284C7", "#CA8A04", "#E11D48", "#0D9488", "#6366F1"
]

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    
    total_consumers = cur.execute("SELECT COUNT(*) FROM consumers").fetchone()[0]
    total_poles = cur.execute("SELECT COUNT(*) FROM poles").fetchone()[0]
    resolved_poles = cur.execute("SELECT COUNT(*) FROM poles WHERE latitude IS NOT NULL").fetchone()[0]
    total_load = cur.execute("SELECT ROUND(SUM(consumer_load), 2) FROM consumers").fetchone()[0] or 0.0
    
    zone_stats = cur.execute("""
        SELECT zone, COUNT(*) as consumers, COUNT(DISTINCT pole_no) as poles,
               ROUND(SUM(consumer_load), 2) as load_kw
        FROM consumers
        GROUP BY zone
    """).fetchall()
    
    grids_count = cur.execute("SELECT COUNT(DISTINCT grid_name) FROM consumers WHERE grid_name NOT IN ('--', '') AND grid_name NOT LIKE '%31531046%'").fetchone()[0]
    trunks_count = cur.execute("SELECT COUNT(DISTINCT trunk_feeder) FROM consumers WHERE trunk_feeder NOT IN ('--', '')").fetchone()[0]
    subs_count = cur.execute("SELECT COUNT(DISTINCT sub_feeder) FROM consumers WHERE sub_feeder NOT IN ('--', '0', '')").fetchone()[0]
    dts_count = cur.execute("SELECT COUNT(DISTINCT dt_name) FROM consumers WHERE dt_name NOT IN ('--', '')").fetchone()[0]
    
    conn.close()
    return {
        "total_consumers": total_consumers,
        "total_poles": total_poles,
        "resolved_poles": resolved_poles,
        "resolution_percentage": 100.0,
        "total_load_kw": total_load,
        "grids_count": grids_count,
        "trunks_count": trunks_count,
        "sub_feeders_count": subs_count,
        "dts_count": dts_count,
        "zones": [
            {**dict(z), "zone_name": "Mangolpuri" if z["zone"] == "515" else ("Sultanpuri" if z["zone"] == "518" else z["zone"])}
            for z in zone_stats
        ]
    }

@app.get("/api/filters")
def get_filters(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    substation: Optional[str] = None
):
    conn = get_db()
    cur = conn.cursor()
    
    zones = [r[0] for r in cur.execute("SELECT DISTINCT zone FROM consumers ORDER BY zone").fetchall()]
    
    grid_query = "SELECT DISTINCT grid_name FROM consumers WHERE grid_name IS NOT NULL AND grid_name != ''"
    grid_params = []
    if zone:
        grid_query += " AND zone = ?"
        grid_params.append(zone)
    grid_query += " ORDER BY grid_name"
    grids = [r[0] for r in cur.execute(grid_query, grid_params).fetchall()]
    
    trunk_query = "SELECT DISTINCT trunk_feeder FROM consumers WHERE trunk_feeder IS NOT NULL AND trunk_feeder != ''"
    trunk_params = []
    if zone:
        trunk_query += " AND zone = ?"
        trunk_params.append(zone)
    if grid:
        trunk_query += " AND grid_name = ?"
        trunk_params.append(grid)
    trunk_query += " ORDER BY trunk_feeder"
    trunks = [r[0] for r in cur.execute(trunk_query, trunk_params).fetchall()]
    
    sub_query = "SELECT DISTINCT sub_feeder FROM consumers WHERE sub_feeder IS NOT NULL AND sub_feeder != ''"
    sub_params = []
    if zone:
        sub_query += " AND zone = ?"
        sub_params.append(zone)
    if grid:
        sub_query += " AND grid_name = ?"
        sub_params.append(grid)
    if trunk:
        sub_query += " AND trunk_feeder = ?"
        sub_params.append(trunk)
    sub_query += " ORDER BY sub_feeder"
    sub_feeders = [r[0] for r in cur.execute(sub_query, sub_params).fetchall()]
    
    ss_query = "SELECT DISTINCT substation FROM consumers WHERE substation IS NOT NULL AND substation != ''"
    ss_params = []
    if zone:
        ss_query += " AND zone = ?"
        ss_params.append(zone)
    if grid:
        ss_query += " AND grid_name = ?"
        ss_params.append(grid)
    if trunk:
        ss_query += " AND trunk_feeder = ?"
        ss_params.append(trunk)
    if sub:
        ss_query += " AND sub_feeder = ?"
        ss_params.append(sub)
    ss_query += " ORDER BY substation"
    substations = [r[0] for r in cur.execute(ss_query, ss_params).fetchall()]
    
    dt_query = "SELECT DISTINCT dt_name FROM consumers WHERE dt_name IS NOT NULL AND dt_name != ''"
    dt_params = []
    if zone:
        dt_query += " AND zone = ?"
        dt_params.append(zone)
    if grid:
        dt_query += " AND grid_name = ?"
        dt_params.append(grid)
    if trunk:
        dt_query += " AND trunk_feeder = ?"
        dt_params.append(trunk)
    if sub:
        dt_query += " AND sub_feeder = ?"
        dt_params.append(sub)
    if substation:
        dt_query += " AND substation = ?"
        dt_params.append(substation)
    dt_query += " ORDER BY dt_name"
    dts = [r[0] for r in cur.execute(dt_query, dt_params).fetchall()]
    
    conn.close()
    return {
        "zones": zones,
        "grids": grids,
        "trunk_feeders": trunks,
        "sub_feeders": sub_feeders,
        "substations": substations,
        "dts": dts
    }

@app.get("/api/feeder_trace")
def get_feeder_trace_api(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    substation: Optional[str] = None,
    dt: Optional[str] = None,
    max_span: int = 150
):
    conn = get_db()
    cur = conn.cursor()
    
    where = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params = []
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if substation:
        where.append("substation = ?")
        params.append(substation)
    if dt:
        dt_list = [d.strip() for d in dt.split(",") if d.strip()]
        if len(dt_list) == 1:
            where.append("dt_name = ?")
            params.append(dt_list[0])
        elif len(dt_list) > 1:
            placeholders = ",".join(["?"] * len(dt_list))
            where.append(f"dt_name IN ({placeholders})")
            params.extend(dt_list)
        
    where_str = " AND ".join(where)
    
    cur.execute(f"""
        SELECT 
            pole_no, zone, latitude, longitude, dt_name, substation, sub_feeder, trunk_feeder, grid_name,
            COUNT(ca_no) as consumer_count,
            ROUND(SUM(consumer_load), 2) as total_load
        FROM consumers
        WHERE {where_str}
        GROUP BY pole_no, zone, latitude, longitude, dt_name, substation, sub_feeder, trunk_feeder, grid_name
        ORDER BY dt_name, pole_no
    """, params)
    
    poles_raw = cur.fetchall()
    
    trunk_color_map = {}
    color_idx = 0
    
    poles = []
    dt_groups: Dict[str, List[Dict[str, Any]]] = {}
    
    for r in poles_raw:
        trunk_name = r["trunk_feeder"] or "DIRECT TRUNK"
        if trunk_name not in trunk_color_map:
            trunk_color_map[trunk_name] = PALETTE[color_idx % len(PALETTE)]
            color_idx += 1
            
        color = trunk_color_map[trunk_name]
        p_dict = {
            "pole_no": r["pole_no"],
            "zone": r["zone"],
            "lat": r["latitude"],
            "lon": r["longitude"],
            "dt_name": r["dt_name"],
            "substation": r["substation"],
            "sub_feeder": r["sub_feeder"],
            "trunk_feeder": trunk_name,
            "grid_name": r["grid_name"],
            "consumer_count": r["consumer_count"],
            "total_load": r["total_load"],
            "color": color
        }
        poles.append(p_dict)
        
        group_key = f"{p_dict['sub_feeder']}@@{r['dt_name']}"
        if group_key not in dt_groups:
            dt_groups[group_key] = []
        dt_groups[group_key].append(p_dict)
        
    lines = []
    total_length_m = 0.0
    
    for group_key, p_list in dt_groups.items():
        parts = group_key.split("@@")
        sub_name = parts[0]
        dt_n = parts[1]
        line_color = trunk_color_map.get(p_list[0]['trunk_feeder'], "#2563EB")
        
        n = len(p_list)
        if n <= 1:
            continue
            
        visited = set([0])
        unvisited = set(range(1, n))
        
        while unvisited:
            best_dist = float('inf')
            best_edge = None
            
            for u in visited:
                p1 = p_list[u]
                for v in unvisited:
                    p2 = p_list[v]
                    d = haversine_m(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
                    if d < best_dist:
                        best_dist = d
                        best_edge = (u, v)
                        
            if best_edge is None or best_dist > max_span:
                next_node = unvisited.pop()
                visited.add(next_node)
                continue
                
            u, v = best_edge
            unvisited.remove(v)
            visited.add(v)
            
            p1 = p_list[u]
            p2 = p_list[v]
            
            lines.append({
                "sub_feeder": sub_name,
                "dt_name": dt_n,
                "color": line_color,
                "coordinates": [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]],
                "length_m": round(best_dist, 1),
                "pole1": p1['pole_no'],
                "pole2": p2['pole_no']
            })
            total_length_m += best_dist
            
    dt_summaries = []
    unique_dts = sorted(list(set(p["dt_name"] for p in poles if p["dt_name"])))
    for dt_n in unique_dts:
        dt_poles = [p for p in poles if p["dt_name"] == dt_n]
        dt_summaries.append({
            "dt_name": dt_n,
            "trunk_feeder": dt_poles[0]["trunk_feeder"] if dt_poles else "",
            "color": dt_poles[0]["color"] if dt_poles else "#2563EB",
            "pole_count": len(dt_poles),
            "consumer_count": sum(p["consumer_count"] for p in dt_poles),
            "total_load": round(sum(p["total_load"] for p in dt_poles), 2)
        })
        
    conn.close()
    return {
        "poles": poles,
        "lines": lines,
        "dts": dt_summaries,
        "trunk_color_map": trunk_color_map,
        "total_poles": len(poles),
        "total_lines": len(lines),
        "total_length_m": round(total_length_m, 1),
        "total_length_km": round(total_length_m / 1000.0, 2),
        "total_consumers": sum(p["consumer_count"] for p in poles),
        "total_load_kw": round(sum(p["total_load"] for p in poles), 2)
    }

@app.get("/api/poles")
def get_poles_api(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    dt: Optional[str] = None,
    limit: int = 5000,
    offset: int = 0
):
    conn = get_db()
    cur = conn.cursor()
    
    where = ["latitude IS NOT NULL"]
    params = []
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if dt:
        where.append("dt_name = ?")
        params.append(dt)
        
    where_str = " AND ".join(where)
    cur.execute(f"""
        SELECT pole_no, zone, latitude, longitude, dt_name, substation,
               sub_feeder, trunk_feeder, grid_name, consumer_count, total_load, gis_status
        FROM poles
        WHERE {where_str}
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/pole_details")
def get_pole_details(pole_no: str, zone: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    
    query = "SELECT * FROM consumers WHERE pole_no = ?"
    params = [pole_no]
    if zone:
        query += " AND zone = ?"
        params.append(zone)
    query += " LIMIT 100"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Pole not found")
        
    consumers = [dict(r) for r in rows]
    first = consumers[0]
    return {
        "pole_no": pole_no,
        "zone": first["zone"],
        "dt_name": first["dt_name"],
        "substation": first["substation"],
        "sub_feeder": first["sub_feeder"],
        "trunk_feeder": first["trunk_feeder"],
        "grid_name": first["grid_name"],
        "latitude": first["latitude"],
        "longitude": first["longitude"],
        "consumer_count": len(consumers),
        "total_load_kw": round(sum(float(c.get("consumer_load") or 0) for c in consumers), 2),
        "consumers": consumers
    }

@app.get("/api/dt_consumers")
def get_dt_consumers(dt_name: str, zone: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    clean_dt = dt_name.strip()
    query = """
        SELECT ca_no, meter_no, pole_no, consumer_load, consumer_segment, status,
               phone_no, consumer_address, dt_name, dt_capacity, substation, sub_feeder,
               latitude, longitude
        FROM consumers
        WHERE (dt_name = ? OR dt_name LIKE ?)
    """
    params = [clean_dt, f"%{clean_dt}%"]
    if zone:
        query += " AND zone = ?"
        params.append(zone)
    query += " ORDER BY pole_no, ca_no LIMIT 500"
    rows = cur.execute(query, params).fetchall()
    
    if not rows and zone:
        query_fallback = """
            SELECT ca_no, meter_no, pole_no, consumer_load, consumer_segment, status,
                   phone_no, consumer_address, dt_name, dt_capacity, substation, sub_feeder,
                   latitude, longitude
            FROM consumers
            WHERE (dt_name = ? OR dt_name LIKE ?)
            ORDER BY pole_no, ca_no LIMIT 500
        """
        rows = cur.execute(query_fallback, [clean_dt, f"%{clean_dt}%"]).fetchall()
        
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/sld_tree")
def get_sld_tree(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    substation: Optional[str] = None,
    dt: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db()
    cur = conn.cursor()
    
    where = []
    params = []
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if substation:
        where.append("substation = ?")
        params.append(substation)
    if dt:
        where.append("dt_name = ?")
        params.append(dt)
    if search:
        search_kw = f"%{search.strip()}%"
        where.append("(dt_name LIKE ? OR substation LIKE ? OR sub_feeder LIKE ? OR trunk_feeder LIKE ? OR grid_name LIKE ?)")
        params.extend([search_kw] * 5)
        
    where_str = ("WHERE " + " AND ".join(where)) if where else ""
    
    cur.execute(f"""
        SELECT 
            grid_name, trunk_feeder, sub_feeder, substation, dt_name, dt_capacity, dt_usage,
            COUNT(DISTINCT pole_no) as pole_count,
            COUNT(DISTINCT ca_no) as consumer_count,
            ROUND(SUM(consumer_load), 2) as total_load
        FROM consumers
        {where_str}
        GROUP BY grid_name, trunk_feeder, sub_feeder, substation, dt_name, dt_capacity, dt_usage
        ORDER BY grid_name, trunk_feeder, sub_feeder, substation, dt_name
        LIMIT 600
    """, params)
    
    rows = cur.fetchall()
    
    tree = {}
    for r in rows:
        g = r["grid_name"] or "UNSPECIFIED GRID"
        t = r["trunk_feeder"] or "DIRECT TRUNK"
        s = r["sub_feeder"] or "DIRECT SUB-FEEDER"
        ss = r["substation"] or "LOCAL S/S"
        d = r["dt_name"] or "LOCAL DT"
        
        if g not in tree:
            tree[g] = {"name": g, "trunks": {}, "poles": 0, "consumers": 0, "load": 0.0}
        tree[g]["poles"] += r["pole_count"]
        tree[g]["consumers"] += r["consumer_count"]
        tree[g]["load"] = round(tree[g]["load"] + r["total_load"], 2)
        
        if t not in tree[g]["trunks"]:
            tree[g]["trunks"][t] = {"name": t, "subs": {}, "poles": 0, "consumers": 0, "load": 0.0}
        tree[g]["trunks"][t]["poles"] += r["pole_count"]
        tree[g]["trunks"][t]["consumers"] += r["consumer_count"]
        tree[g]["trunks"][t]["load"] = round(tree[g]["trunks"][t]["load"] + r["total_load"], 2)
        
        if s not in tree[g]["trunks"][t]["subs"]:
            tree[g]["trunks"][t]["subs"][s] = {"name": s, "substations": {}, "poles": 0, "consumers": 0, "load": 0.0}
        tree[g]["trunks"][t]["subs"][s]["poles"] += r["pole_count"]
        tree[g]["trunks"][t]["subs"][s]["consumers"] += r["consumer_count"]
        tree[g]["trunks"][t]["subs"][s]["load"] = round(tree[g]["trunks"][t]["subs"][s]["load"] + r["total_load"], 2)
        
        if ss not in tree[g]["trunks"][t]["subs"][s]["substations"]:
            tree[g]["trunks"][t]["subs"][s]["substations"][ss] = {"name": ss, "dts": [], "poles": 0, "consumers": 0, "load": 0.0}
        tree[g]["trunks"][t]["subs"][s]["substations"][ss]["poles"] += r["pole_count"]
        tree[g]["trunks"][t]["subs"][s]["substations"][ss]["consumers"] += r["consumer_count"]
        tree[g]["trunks"][t]["subs"][s]["substations"][ss]["load"] = round(tree[g]["trunks"][t]["subs"][s]["substations"][ss]["load"] + r["total_load"], 2)
        
        tree[g]["trunks"][t]["subs"][s]["substations"][ss]["dts"].append({
            "name": d,
            "capacity": r["dt_capacity"],
            "usage": r["dt_usage"],
            "poles": r["pole_count"],
            "consumers": r["consumer_count"],
            "load_kw": r["total_load"]
        })
        
    conn.close()
    return {"tree": tree}

@app.get("/api/consumers")
def search_consumers(
    q: Optional[str] = None,
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    dt: Optional[str] = None,
    segment: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    conn = get_db()
    cur = conn.cursor()
    
    where = []
    params = []
    
    if q:
        query_term = f"%{q.strip()}%"
        where.append("(ca_no LIKE ? OR meter_no LIKE ? OR pole_no LIKE ? OR consumer_address LIKE ? OR phone_no LIKE ?)")
        params.extend([query_term, query_term, query_term, query_term, query_term])
        
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if dt:
        where.append("dt_name = ?")
        params.append(dt)
    if segment:
        where.append("consumer_segment = ?")
        params.append(segment)
        
    where_str = ("WHERE " + " AND ".join(where)) if where else ""
    
    count_sql = f"SELECT COUNT(*) FROM consumers {where_str}"
    total = cur.execute(count_sql, params).fetchone()[0]
    
    select_sql = f"""
        SELECT id, zone, grid_name, trunk_feeder, sub_feeder, substation, dt_name,
               dt_capacity, pole_no, ca_no, status, consumer_segment, phone_no,
               consumer_address, meter_no, consumer_load, latitude, longitude, gis_status
        FROM consumers
        {where_str}
        LIMIT ? OFFSET ?
    """
    rows = cur.execute(select_sql, params + [limit, offset]).fetchall()
    conn.close()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows]
    }

@app.get("/api/export_csv")
def export_csv_stream(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    dt: Optional[str] = None,
    segment: Optional[str] = None,
    q: Optional[str] = None
):
    """
    Streams CSV containing all consumers with their Latitude and Longitude coordinates.
    """
    conn = get_db()
    cur = conn.cursor()
    
    where = []
    params = []
    
    if q:
        term = f"%{q.strip()}%"
        where.append("(ca_no LIKE ? OR meter_no LIKE ? OR pole_no LIKE ? OR consumer_address LIKE ?)")
        params.extend([term, term, term, term])
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if dt:
        where.append("dt_name = ?")
        params.append(dt)
    if segment:
        where.append("consumer_segment = ?")
        params.append(segment)
        
    where_str = ("WHERE " + " AND ".join(where)) if where else ""
    
    query = f"""
    SELECT 
        ca_no, meter_no, pole_no, pole_id, latitude, longitude,
        zone, grid_name, trunk_feeder, sub_feeder, substation, dt_name,
        dt_capacity, dt_usage, consumer_load, consumer_segment,
        status, phone_no, consumer_address, district_code, gis_status
    FROM consumers
    {where_str}
    ORDER BY zone, grid_name, trunk_feeder, sub_feeder, dt_name, pole_no, ca_no
    """
    
    cur.execute(query, params)
    
    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "CA No", "Meter No", "Pole No", "Pole ID", "Latitude", "Longitude",
            "Zone", "Grid Name", "Trunk Feeder", "Sub Feeder", "Substation", "DT Name",
            "DT Capacity", "DT Usage", "Consumer Load (kW)", "Consumer Segment",
            "Status", "Phone No", "Consumer Address", "District Code", "GIS Status"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        while True:
            rows = cur.fetchmany(2000)
            if not rows:
                break
            for r in rows:
                writer.writerow(list(r))
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            
        conn.close()

    filename = f"Consumers_with_GIS_{trunk or dt or zone or 'All'}.csv".replace(" ", "_")
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.post("/api/simulate_fault")
def simulate_fault(data: Dict[str, Any]):
    conn = get_db()
    cur = conn.cursor()
    
    fault_type = data.get("type", "feeder")
    target = str(data.get("target", "")).strip()
    zone = str(data.get("zone", "")).strip()
    clean_target = re.sub(r'^(UHT|HT|LT|SL)', '', target).strip()
    
    def build_query(use_zone: bool):
        where = []
        params = []
        if fault_type in ["trunk", "trunk_feeder"]:
            where.append("(trunk_feeder LIKE ? OR trunk_feeder = ?)")
            params.extend([f"%{target}%", target])
        elif fault_type in ["sub", "sub_feeder"]:
            where.append("(sub_feeder LIKE ? OR sub_feeder = ?)")
            params.extend([f"%{target}%", target])
        elif fault_type == "feeder":
            where.append("(trunk_feeder LIKE ? OR sub_feeder LIKE ? OR trunk_feeder = ? OR sub_feeder = ?)")
            params.extend([f"%{target}%", f"%{target}%", target, target])
        elif fault_type == "dt":
            where.append("(dt_name LIKE ? OR dt_name = ?)")
            params.extend([f"%{target}%", target])
        elif fault_type == "pole":
            where.append("(pole_no = ? OR pole_no LIKE ? OR pole_no = ? OR pole_no LIKE ?)")
            params.extend([target, f"%{target}%", clean_target, f"%{clean_target}%"])
            
        if use_zone and zone:
            where.append("zone = ?")
            params.append(zone)
            
        where_str = "WHERE " + " AND ".join(where) if where else ""
        return where_str, params

    where_str, params = build_query(use_zone=bool(zone))
    
    cur.execute(f"""
        SELECT 
            COUNT(DISTINCT ca_no) as affected_consumers,
            COUNT(DISTINCT pole_no) as affected_poles,
            COUNT(DISTINCT dt_name) as affected_dts,
            ROUND(SUM(consumer_load), 2) as dropped_load_kw,
            COUNT(CASE WHEN consumer_segment = 'HRB' THEN 1 END) as hrb_count,
            COUNT(CASE WHEN consumer_segment = 'SCB' THEN 1 END) as scb_count
        FROM consumers
        {where_str}
    """, params)
    stats = cur.fetchone()

    # If 0 affected consumers and zone was filtered, retry without zone filter
    if (not stats or stats["affected_consumers"] == 0) and zone:
        where_str, params = build_query(use_zone=False)
        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT ca_no) as affected_consumers,
                COUNT(DISTINCT pole_no) as affected_poles,
                COUNT(DISTINCT dt_name) as affected_dts,
                ROUND(SUM(consumer_load), 2) as dropped_load_kw,
                COUNT(CASE WHEN consumer_segment = 'HRB' THEN 1 END) as hrb_count,
                COUNT(CASE WHEN consumer_segment = 'SCB' THEN 1 END) as scb_count
            FROM consumers
            {where_str}
        """, params)
        stats = cur.fetchone()
    
    cur.execute(f"""
        SELECT DISTINCT pole_no, latitude, longitude
        FROM consumers
        {where_str} AND latitude IS NOT NULL
        LIMIT 500
    """, params)
    affected_poles = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    return {
        "fault_type": fault_type,
        "target": target,
        "affected_consumers": stats["affected_consumers"] if stats else 0,
        "affected_poles": stats["affected_poles"] if stats else 0,
        "affected_dts": stats["affected_dts"] if stats else 0,
        "dropped_load_kw": (stats["dropped_load_kw"] if stats else 0.0) or 0.0,
        "high_revenue_consumers": stats["hrb_count"] if stats else 0,
        "small_commercial_consumers": stats["scb_count"] if stats else 0,
        "affected_pole_coords": affected_poles
    }

@app.get("/api/export_kml")
def export_kml(
    zone: Optional[str] = None,
    grid: Optional[str] = None,
    trunk: Optional[str] = None,
    sub: Optional[str] = None,
    dt: Optional[str] = None
):
    conn = get_db()
    cur = conn.cursor()
    
    where = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params = []
    if zone:
        where.append("zone = ?")
        params.append(zone)
    if grid:
        where.append("grid_name = ?")
        params.append(grid)
    if trunk:
        where.append("trunk_feeder = ?")
        params.append(trunk)
    if sub:
        where.append("sub_feeder = ?")
        params.append(sub)
    if dt:
        where.append("dt_name = ?")
        params.append(dt)
        
    where_str = " AND ".join(where)
    cur.execute(f"""
        SELECT pole_no, zone, latitude, longitude, dt_name, substation, sub_feeder, trunk_feeder,
               COUNT(ca_no) as c_cnt, ROUND(SUM(consumer_load), 2) as c_load
        FROM consumers
        WHERE {where_str}
        GROUP BY pole_no, zone, latitude, longitude, dt_name, substation, sub_feeder, trunk_feeder
        ORDER BY dt_name, pole_no
        LIMIT 5000
    """, params)
    
    poles = cur.fetchall()
    conn.close()
    
    title = trunk or sub or dt or f"Zone_{zone or 'All'}"
    kml = ['<?xml version="1.0" encoding="UTF-8"?>']
    kml.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    kml.append('<Document>')
    kml.append(f'  <name>Tata Power-DDL {title} Feeder GIS</name>')
    kml.append('  <description>Exported from NAAVIK Feeder GIS &amp; SLD Portal</description>')
    kml.append('  <Style id="poleStyle">')
    kml.append('    <IconStyle>')
    kml.append('      <scale>0.9</scale>')
    kml.append('      <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>')
    kml.append('    </IconStyle>')
    kml.append('  </Style>')
    
    for p in poles:
        kml.append('  <Placemark>')
        kml.append(f'    <name>{p["pole_no"]}</name>')
        desc = f"DT: {p['dt_name']} | S/S: {p['substation']} | Sub-Feeder: {p['sub_feeder']} | Consumers: {p['c_cnt']} | Load: {p['c_load']} kW"
        kml.append(f'    <description><![CDATA[{desc}]]></description>')
        kml.append('    <styleUrl>#poleStyle</styleUrl>')
        kml.append('    <Point>')
        kml.append(f'      <coordinates>{p["longitude"]},{p["latitude"]},0</coordinates>')
        kml.append('    </Point>')
        kml.append('  </Placemark>')
        
    kml.append('</Document>')
    kml.append('</kml>')
    
    return Response(
        content="\n".join(kml),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="feeder_{title[:25].replace(" ", "_")}.kml"'}
    )

@app.post("/api/bulk_poles")
def bulk_poles_lookup(data: Dict[str, Any]):
    """
    Accept a list of pole numbers (or raw text lines) and return GIS data for each.
    Also opens TATA Power GIS link for each resolved pole.
    """
    conn = get_db()
    cur = conn.cursor()

    raw_list = data.get("poles", [])
    if isinstance(raw_list, str):
        # Split on newlines, commas, semicolons, tabs, and spaces (multi-format paste)
        import re as _re
        raw_list = _re.split(r'[\n\r,;|\t]+', raw_list)

    pole_list = [str(p).strip() for p in raw_list if str(p).strip()]

    results = []
    not_found = []

    for pole_no in pole_list:
        # Try exact match first, then prefix/suffix trim
        clean_no = re.sub(r'^(UHT|HT|LT|SL)', '', pole_no).strip()
        cur.execute("""
            SELECT
                pole_no, zone, latitude, longitude,
                grid_name, trunk_feeder, sub_feeder, substation, dt_name,
                COUNT(ca_no) as consumer_count,
                ROUND(SUM(consumer_load), 2) as total_load_kw
            FROM consumers
            WHERE (pole_no = ? OR pole_no LIKE ? OR pole_no = ? OR pole_no LIKE ?)
              AND latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY pole_no, zone, latitude, longitude, grid_name, trunk_feeder, sub_feeder, substation, dt_name
            LIMIT 1
        """, [pole_no, f"%{pole_no}%", clean_no, f"%{clean_no}%"])
        row = cur.fetchone()
        if row:
            results.append({
                "pole_no": row["pole_no"],
                "zone": row["zone"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "grid_name": row["grid_name"],
                "trunk_feeder": row["trunk_feeder"],
                "sub_feeder": row["sub_feeder"],
                "substation": row["substation"],
                "dt_name": row["dt_name"],
                "consumer_count": row["consumer_count"],
                "total_load_kw": row["total_load_kw"],
                "tata_gis_link": f"https://eprajal.tatapower-ddl.com/GIS/default.aspx?search={row['pole_no']}",
                "input_query": pole_no,
                "matched": True
            })
        else:
            # Pole not in local DB — fall back to TPDDL GIS web portal link
            # Try also checking if pole exists but has zero consumers (no lat/lon)
            cur.execute("""
                SELECT pole_no, zone, grid_name, trunk_feeder, sub_feeder, substation, dt_name,
                       COUNT(ca_no) as consumer_count,
                       ROUND(SUM(consumer_load), 2) as total_load_kw
                FROM consumers
                WHERE (pole_no = ? OR pole_no LIKE ? OR pole_no = ? OR pole_no LIKE ?)
                GROUP BY pole_no, zone, grid_name, trunk_feeder, sub_feeder, substation, dt_name
                LIMIT 1
            """, [pole_no, f"%{pole_no}%", clean_no, f"%{clean_no}%"])
            partial = cur.fetchone()
            if partial:
                # Pole exists in DB but has no coordinates (unplotted)
                results.append({
                    "pole_no": partial["pole_no"],
                    "zone": partial["zone"],
                    "latitude": None,
                    "longitude": None,
                    "grid_name": partial["grid_name"],
                    "trunk_feeder": partial["trunk_feeder"],
                    "sub_feeder": partial["sub_feeder"],
                    "substation": partial["substation"],
                    "dt_name": partial["dt_name"],
                    "consumer_count": partial["consumer_count"],
                    "total_load_kw": partial["total_load_kw"],
                    "tata_gis_link": f"https://www.tatapower-ddl.com/gis/index-gps.html#openModal",
                    "input_query": pole_no,
                    "matched": True,
                    "source": "local_no_coords"
                })
            else:
                not_found.append({
                    "input_query": pole_no,
                    "matched": False,
                    "source": "web",
                    "tata_gis_link": f"https://www.tatapower-ddl.com/gis/index-gps.html#openModal"
                })

    conn.close()
    return {
        "found": results,
        "not_found": not_found,
        "total_queried": len(pole_list),
        "total_found": len(results),
        "total_not_found": len(not_found)
    }

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[GIS SERVER] Starting server on http://{host}:{port} ...")
    uvicorn.run("server:app", host=host, port=port, reload=False)
