import os
import json
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.ml_engine import MLEngine, FEATURE_COLS

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "projects.sqlite")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="AI-Powered Integrated Project Monitoring Platform",
    description="MoSPI / IPMD Infrastructure Project Monitoring, Risk Prediction & Early Warning System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ML Engine
ml_engine = MLEngine()
try:
    ml_engine.load_saved_models()
except Exception as e:
    print(f"Warning: ML Engine load error: {e}")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- API ENDPOINTS -----------------

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    total_projects = cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    total_orig_cost = cursor.execute("SELECT SUM(orig_cost) FROM projects").fetchone()[0] or 0.0
    total_rev_cost = cursor.execute("SELECT SUM(rev_cost) FROM projects").fetchone()[0] or 0.0
    total_exp = cursor.execute("SELECT SUM(expenditure) FROM projects").fetchone()[0] or 0.0
    
    high_risk = cursor.execute("SELECT COUNT(*) FROM projects WHERE risk_level='HIGH'").fetchone()[0]
    med_risk = cursor.execute("SELECT COUNT(*) FROM projects WHERE risk_level='MEDIUM'").fetchone()[0]
    low_risk = cursor.execute("SELECT COUNT(*) FROM projects WHERE risk_level='LOW'").fetchone()[0]
    
    delayed_count = cursor.execute("SELECT COUNT(*) FROM projects WHERE delay_months > 0").fetchone()[0]
    overrun_count = cursor.execute("SELECT COUNT(*) FROM projects WHERE cost_overrun_pct > 0").fetchone()[0]
    anomaly_count = cursor.execute("SELECT COUNT(*) FROM projects WHERE is_anomaly=1").fetchone()[0]
    
    avg_delay = cursor.execute("SELECT AVG(delay_months) FROM projects WHERE delay_months > 0").fetchone()[0] or 0.0
    avg_prog = cursor.execute("SELECT AVG(progress) FROM projects").fetchone()[0] or 0.0
    avg_gap = cursor.execute("SELECT AVG(progress_gap) FROM projects").fetchone()[0] or 0.0
    
    conn.close()
    
    return {
        "total_projects": total_projects,
        "total_original_cost_cr": round(total_orig_cost, 1),
        "total_revised_cost_cr": round(total_rev_cost, 1),
        "total_expenditure_cr": round(total_exp, 1),
        "total_cost_growth_cr": round(max(0.0, total_rev_cost - total_orig_cost), 1),
        "high_risk_count": high_risk,
        "medium_risk_count": med_risk,
        "low_risk_count": low_risk,
        "delayed_projects_count": delayed_count,
        "overrun_projects_count": overrun_count,
        "anomaly_projects_count": anomaly_count,
        "average_delay_months": round(avg_delay, 1),
        "average_physical_progress_pct": round(avg_prog, 1),
        "average_progress_gap_pct": round(avg_gap, 1)
    }

@app.get("/api/projects")
def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    ministry: Optional[str] = None,
    sector: Optional[str] = None,
    state: Optional[str] = None,
    risk_level: Optional[str] = None,
    is_anomaly: Optional[int] = None,
    sort_by: str = Query("orig_cost", pattern="^(orig_cost|rev_cost|expenditure|progress|delay_months|cost_overrun_pct|progress_gap)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM projects WHERE 1=1"
    params = []
    
    if search:
        query += " AND (project_name LIKE ? OR project_code LIKE ? OR agency LIKE ?)"
        s = f"%{search.strip()}%"
        params.extend([s, s, s])
        
    if ministry and ministry != "ALL":
        query += " AND ministry = ?"
        params.append(ministry)
        
    if sector and sector != "ALL":
        query += " AND sector = ?"
        params.append(sector)
        
    if state and state != "ALL":
        query += " AND state LIKE ?"
        params.append(f"%{state}%")
        
    if risk_level and risk_level != "ALL":
        query += " AND risk_level = ?"
        params.append(risk_level)
        
    if is_anomaly is not None:
        query += " AND is_anomaly = ?"
        params.append(is_anomaly)
        
    # Total count for pagination
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total_count = cursor.execute(count_query, params).fetchone()[0]
    
    # Ordering & pagination
    query += f" ORDER BY {sort_by} {sort_order.upper()} LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    
    rows = cursor.execute(query, params).fetchall()
    
    projects = []
    for r in rows:
        d = dict(r)
        if "history_json" in d and d["history_json"]:
            try:
                d["history"] = json.loads(d["history_json"])
            except:
                d["history"] = []
        else:
            d["history"] = []
        del d["history_json"]
        projects.append(d)
        
    conn.close()
    
    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
        "projects": projects
    }

@app.get("/api/projects/{project_code}")
def get_project_detail(project_code: str):
    conn = get_db()
    cursor = conn.cursor()
    
    row = cursor.execute("SELECT * FROM projects WHERE project_code = ?", (project_code,)).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project = dict(row)
    if "history_json" in project and project["history_json"]:
        try:
            project["history"] = json.loads(project["history_json"])
        except:
            project["history"] = []
    else:
        project["history"] = []
    del project["history_json"]
    
    # Run ML prediction on project attributes
    prediction = ml_engine.predict_project(project)
    project["ai_prediction"] = prediction
    
    return project

class WhatIfSimulationRequest(BaseModel):
    orig_cost: float
    rev_cost: float
    expenditure: float
    progress: float
    time_elapsed_months: float = 24.0
    planned_duration_months: float = 36.0
    progress_velocity: float = 1.0
    expenditure_velocity: float = 5.0
    delay_slippage: float = 0.0

@app.post("/api/predict")
def simulate_prediction(req: WhatIfSimulationRequest):
    p_dict = req.model_dump()
    prediction = ml_engine.predict_project(p_dict)
    return prediction

@app.get("/api/analytics/sectors")
def get_sector_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT 
            sector,
            COUNT(*) as project_count,
            SUM(orig_cost) as total_orig_cost,
            SUM(rev_cost) as total_rev_cost,
            SUM(expenditure) as total_exp,
            AVG(delay_months) as avg_delay,
            AVG(progress) as avg_progress,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count,
            SUM(CASE WHEN is_anomaly=1 THEN 1 ELSE 0 END) as anomaly_count
        FROM projects
        GROUP BY sector
        ORDER BY total_rev_cost DESC
    """).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_orig_cost"] = round(d["total_orig_cost"] or 0, 1)
        d["total_rev_cost"] = round(d["total_rev_cost"] or 0, 1)
        d["total_exp"] = round(d["total_exp"] or 0, 1)
        d["avg_delay"] = round(d["avg_delay"] or 0, 1)
        d["avg_progress"] = round(d["avg_progress"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/analytics/ministries")
def get_ministry_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT 
            ministry,
            COUNT(*) as project_count,
            SUM(orig_cost) as total_orig_cost,
            SUM(rev_cost) as total_rev_cost,
            AVG(delay_months) as avg_delay,
            AVG(cost_overrun_pct) as avg_cost_overrun,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count
        FROM projects
        GROUP BY ministry
        ORDER BY project_count DESC
    """).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_orig_cost"] = round(d["total_orig_cost"] or 0, 1)
        d["total_rev_cost"] = round(d["total_rev_cost"] or 0, 1)
        d["avg_delay"] = round(d["avg_delay"] or 0, 1)
        d["avg_cost_overrun"] = round(d["avg_cost_overrun"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/analytics/states")
def get_state_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT 
            state,
            COUNT(*) as project_count,
            SUM(rev_cost) as total_cost,
            AVG(delay_months) as avg_delay,
            AVG(progress) as avg_progress,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count
        FROM projects
        WHERE state != 'Unknown'
        GROUP BY state
        ORDER BY project_count DESC
    """).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_cost"] = round(d["total_cost"] or 0, 1)
        d["avg_delay"] = round(d["avg_delay"] or 0, 1)
        d["avg_progress"] = round(d["avg_progress"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/anomalies")
def get_anomalies(limit: int = Query(20, ge=1, le=100)):
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT * FROM projects 
        WHERE is_anomaly = 1 
        ORDER BY progress_gap DESC 
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    anomalies = []
    for r in rows:
        d = dict(r)
        if "history_json" in d:
            del d["history_json"]
        # build anomaly rationale
        gap = d.get("progress_gap", 0)
        p = d.get("progress", 0)
        fp = d.get("financial_progress_pct", 0)
        d["anomaly_reason"] = f"Financial Progress is {fp:.1f}% while Physical Ground Progress is only {p:.1f}% (Progress Gap: {gap:.1f}%)"
        anomalies.append(d)
    return anomalies

@app.get("/api/filters")
def get_filter_options():
    conn = get_db()
    cursor = conn.cursor()
    
    ministries = [r[0] for r in cursor.execute("SELECT DISTINCT ministry FROM projects WHERE ministry != 'Unknown Ministry' ORDER BY ministry").fetchall()]
    sectors = [r[0] for r in cursor.execute("SELECT DISTINCT sector FROM projects WHERE sector != 'Unknown Sector' ORDER BY sector").fetchall()]
    states = [r[0] for r in cursor.execute("SELECT DISTINCT state FROM projects WHERE state != 'Unknown' AND state NOT LIKE 'Multi-States%' ORDER BY state").fetchall()]
    
    conn.close()
    return {
        "ministries": ministries,
        "sectors": sectors,
        "states": states,
        "risk_levels": ["HIGH", "MEDIUM", "LOW"]
    }

@app.get("/api/model/benchmarks")
def get_benchmarks():
    return ml_engine.benchmarks

# Serve Static UI Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>AI Project Monitoring System API Running</h1><p>Frontend index.html not yet built.</p>")
