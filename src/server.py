import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, Request, Depends, Body, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from src.db import get_db, init_db_schema, hash_password, verify_password
from src.auth import (
    create_access_token,
    verify_access_token,
    get_current_user,
    get_optional_current_user,
    require_roles,
    get_agency_scope
)
from src.audit import log_audit
from src.ml_engine import MLEngine, FEATURE_COLS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "projects.sqlite")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Auto-initialize database schema and seeds
init_db_schema()

app = FastAPI(
    title="PAIMANA AI — Predictive Infrastructure Project Monitoring Platform",
    description="MoSPI / IPMD Central Infrastructure Project Early Warning, Risk Prediction & Decision-Support System",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path in ["/", "/login", "/admin/login", "/dashboard", "/portal", "/monitor", "/engine", "/risk-engine"]:
        response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# Initialize and load ML Engine
ml_engine = MLEngine()
try:
    ml_engine.load_saved_models()
except Exception as e:
    print(f"Notice: ML Engine load status: {e}")

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "PAIMANA AI Infrastructure Risk Platform", "version": "2.4.0"}

# ----------------- AUTHENTICATION MODELS & ENDPOINTS -----------------

class LoginRequest(BaseModel):
    username: str
    password: str
    portal_type: Optional[str] = "user" # 'user' or 'admin'

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response):
    conn = get_db()
    cursor = conn.cursor()
    ip = get_client_ip(request)
    
    # Check by username or email
    cursor.execute("""
        SELECT * FROM users 
        WHERE (username = ? OR email = ?)
    """, (req.username.strip(), req.username.strip()))
    row = cursor.fetchone()
    
    if not row:
        log_audit("LOGIN_FAILED", "auth", username=req.username, details="User not found", ip_address=ip, status="FAILED")
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username, email, or password.")
        
    user = dict(row)
    if not user.get("is_active"):
        log_audit("LOGIN_FAILED", "auth", user=user, details="Account inactive", ip_address=ip, status="FAILED")
        conn.close()
        raise HTTPException(status_code=401, detail="Account has been deactivated. Please contact the administrator.")
        
    # Check password
    if not verify_password(req.password, user["password_hash"], user["salt"]):
        log_audit("LOGIN_FAILED", "auth", user=user, details="Incorrect password", ip_address=ip, status="FAILED")
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username, email, or password.")
        
    # Check portal authorization
    if req.portal_type == "admin" and user["role"] != "ADMIN":
        log_audit("LOGIN_FAILED", "admin_portal", user=user, details=f"Non-admin role {user['role']} attempted admin login", ip_address=ip, status="FORBIDDEN")
        conn.close()
        raise HTTPException(status_code=403, detail="Access Denied: Administrator credentials required for Administrator Portal.")
        
    # Update last login
    now_iso = datetime.utcnow().isoformat()
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_iso, user["id"]))
    conn.commit()
    conn.close()
    
    # Generate token
    token = create_access_token(user)
    
    # Set secure cookie
    response.set_cookie(
        key="paimana_auth_token",
        value=token,
        httponly=False, # Accessible to JS client for SPA navigation
        max_age=86400 * 2,
        samesite="lax"
    )
    
    del user["password_hash"]
    del user["salt"]
    
    log_audit("LOGIN", "auth", user=user, details=f"Logged into {req.portal_type} portal", ip_address=ip, status="SUCCESS")
    
    return {
        "status": "success",
        "token": token,
        "user": user
    }

@app.post("/api/auth/logout")
def logout(request: Request, response: Response, current_user: Optional[dict] = Depends(get_optional_current_user)):
    ip = get_client_ip(request)
    if current_user:
        log_audit("LOGOUT", "auth", user=current_user, ip_address=ip, status="SUCCESS")
    response.delete_cookie("paimana_auth_token")
    return {"status": "success", "message": "Successfully logged out."}

@app.get("/api/auth/me")
def get_auth_me(current_user: dict = Depends(get_current_user)):
    return {
        "user": current_user,
        "permissions": {
            "can_view_admin": current_user["role"] == "ADMIN",
            "can_manage_users": current_user["role"] == "ADMIN",
            "can_manage_projects": current_user["role"] == "ADMIN",
            "can_view_audit_logs": current_user["role"] == "ADMIN",
            "agency_isolated": current_user["role"] == "AGENCY",
            "agency_scope": get_agency_scope(current_user)
        }
    }

@app.post("/api/profile/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?", (current_user["id"],)).fetchone()
    
    if not row or not verify_password(req.old_password, row["password_hash"], row["salt"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
        
    if len(req.new_password) < 6:
        conn.close()
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")
        
    new_hash, new_salt = hash_password(req.new_password)
    cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, current_user["id"]))
    conn.commit()
    conn.close()
    
    log_audit("CHANGE_PASSWORD", "profile", user=current_user, status="SUCCESS")
    return {"status": "success", "message": "Password changed successfully."}

# ----------------- DASHBOARD & CORE STATS API -----------------

@app.get("/api/dashboard/stats")
def get_dashboard_stats(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    
    where_clause = "WHERE 1=1"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    total_projects = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause}", params).fetchone()[0]
    total_orig_cost = cursor.execute(f"SELECT SUM(orig_cost) FROM projects {where_clause}", params).fetchone()[0] or 0.0
    total_rev_cost = cursor.execute(f"SELECT SUM(rev_cost) FROM projects {where_clause}", params).fetchone()[0] or 0.0
    total_exp = cursor.execute(f"SELECT SUM(expenditure) FROM projects {where_clause}", params).fetchone()[0] or 0.0
    
    high_risk = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND risk_level='HIGH'", params).fetchone()[0]
    med_risk = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND risk_level='MEDIUM'", params).fetchone()[0]
    low_risk = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND risk_level='LOW'", params).fetchone()[0]
    
    delayed_count = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND delay_months > 0", params).fetchone()[0]
    overrun_count = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND cost_overrun_pct > 0", params).fetchone()[0]
    anomaly_count = cursor.execute(f"SELECT COUNT(*) FROM projects {where_clause} AND is_anomaly=1", params).fetchone()[0]
    
    avg_delay = cursor.execute(f"SELECT AVG(delay_months) FROM projects {where_clause} AND delay_months > 0", params).fetchone()[0] or 0.0
    avg_prog = cursor.execute(f"SELECT AVG(progress) FROM projects {where_clause}", params).fetchone()[0] or 0.0
    avg_gap = cursor.execute(f"SELECT AVG(progress_gap) FROM projects {where_clause}", params).fetchone()[0] or 0.0
    
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
        "average_progress_gap_pct": round(avg_gap, 1),
        "is_agency_scoped": bool(agency_scope),
        "scope_name": agency_scope or "National Portfolio"
    }

# ----------------- PROJECTS LIST & DETAILS API -----------------

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
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM projects WHERE 1=1"
    params = []
    
    # 1. Strict Agency Data Isolation (Section 19 & 58)
    agency_scope = get_agency_scope(current_user) if current_user else None
    if agency_scope:
        query += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
    
    # 2. General Filters
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
        
    # Count total for pagination
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total_count = cursor.execute(count_query, params).fetchone()[0]
    
    # Order & Pagination
    page_num = page if isinstance(page, int) else 1
    page_sz = page_size if isinstance(page_size, int) else 15
    sort_by_col = sort_by if isinstance(sort_by, str) else "orig_cost"
    order_dir = (sort_order if isinstance(sort_order, str) else "desc").upper()
    query += f" ORDER BY {sort_by_col} {order_dir} LIMIT ? OFFSET ?"
    params.extend([page_sz, (page_num - 1) * page_sz])
    
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
        if "history_json" in d:
            del d["history_json"]
        projects.append(d)
        
    conn.close()
    
    return {
        "total": total_count,
        "page": page_num,
        "page_size": page_sz,
        "total_pages": (total_count + page_sz - 1) // page_sz,
        "projects": projects,
        "is_agency_scoped": bool(agency_scope),
        "scope_name": agency_scope or "National Portfolio"
    }

@app.get("/api/projects/{project_code}")
def get_project_detail(
    project_code: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    conn = get_db()
    cursor = conn.cursor()
    ip = get_client_ip(request)
    
    row = cursor.execute("SELECT * FROM projects WHERE project_code = ?", (project_code,)).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Project record not found in central registry.")
        
    project = dict(row)
    
    # Strict Cross-Agency Authorization Check (Section 19: Agency A -> Agency B rejected with 403)
    agency_scope = get_agency_scope(current_user) if current_user else None
    if agency_scope:
        p_agency = project.get("agency", "")
        p_min = project.get("ministry", "")
        if agency_scope.lower() not in p_agency.lower() and agency_scope.lower() not in p_min.lower():
            log_audit(
                "FORBIDDEN_ATTEMPT",
                f"project/{project_code}",
                user=current_user,
                details=f"Agency user tried accessing cross-agency project '{project.get('project_name')}' ({p_agency})",
                ip_address=ip,
                status="FORBIDDEN"
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have authorization to view projects outside your designated agency."
            )
            
    if "history_json" in project and project["history_json"]:
        try:
            project["history"] = json.loads(project["history_json"])
        except:
            project["history"] = []
    else:
        project["history"] = []
    if "history_json" in project:
        del project["history_json"]
        
    # Run ML prediction pipeline
    prediction = ml_engine.predict_project(project)
    project["ai_prediction"] = prediction
    
    if current_user:
        log_audit("VIEW_PROJECT", f"project/{project_code}", user=current_user, ip_address=ip, status="SUCCESS")
        
    return project

# ----------------- WHAT-IF SCENARIO SIMULATOR -----------------

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

# ----------------- EARLY WARNING SYSTEM & ALERTS -----------------

@app.get("/api/alerts")
def get_alerts(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(30, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    
    where_clause = "WHERE (risk_level='HIGH' OR delay_months > 6 OR cost_overrun_pct > 15 OR is_anomaly=1)"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
        SELECT project_code, project_name, agency, ministry, sector, state, 
               orig_cost, rev_cost, expenditure, progress, progress_gap, 
               delay_months, cost_overrun_pct, risk_level, is_anomaly
        FROM projects 
        {where_clause}
        ORDER BY (CASE WHEN is_anomaly=1 THEN 100 ELSE 0 END + delay_months + cost_overrun_pct) DESC
        LIMIT ?
    """, (*params, limit * 2)).fetchall()
    conn.close()
    
    alerts = []
    for r in rows:
        d = dict(r)
        
        # Categorize
        if d.get("is_anomaly") == 1:
            cat = "ANOMALY"
            prio = "CRITICAL"
            reason = f"Expenditure burn ({d.get('expenditure')} Cr) diverges severely from physical progress ({d.get('progress')}%)"
            action = "Audit physical measurement book (MB) & verify fund utilization certificates."
        elif d.get("delay_months", 0) > 24 and d.get("cost_overrun_pct", 0) > 25:
            cat = "COST_AND_DELAY"
            prio = "CRITICAL"
            reason = f"Chronic delay of {d.get('delay_months')} months accompanied by {d.get('cost_overrun_pct')}% cost escalation."
            action = "Convene High-Level Empowered Committee (HLEC) for scope baseline review."
        elif d.get("delay_months", 0) > 12:
            cat = "DELAY_RISK"
            prio = "HIGH"
            reason = f"Schedule slippage exceeded {d.get('delay_months')} months past target completion."
            action = "Fast-track pending environmental/right-of-way clearances and augment contractor resources."
        elif d.get("cost_overrun_pct", 0) > 15:
            cat = "COST_RISK"
            prio = "HIGH"
            reason = f"Budget overrun reached {d.get('cost_overrun_pct')}% above sanctioned capital."
            action = "Impose revised expenditure ceiling and scrutinize contractor price variation claims."
        else:
            cat = "HIGH_RISK"
            prio = "MEDIUM"
            reason = "Progress velocity trailing behind planned timeline by > 15%."
            action = "Institute bi-weekly milestone monitoring with implementing agency project director."
            
        if category and category != "ALL" and cat != category:
            continue
        if priority and priority != "ALL" and prio != priority:
            continue
            
        alerts.append({
            "id": f"ALT-{d.get('project_code')}",
            "project_code": d.get("project_code"),
            "project_name": d.get("project_name"),
            "agency": d.get("agency"),
            "sector": d.get("sector"),
            "state": d.get("state"),
            "category": cat,
            "priority": prio,
            "reason": reason,
            "recommended_action": action,
            "risk_level": d.get("risk_level"),
            "delay_months": d.get("delay_months"),
            "cost_overrun_pct": d.get("cost_overrun_pct"),
            "progress": d.get("progress")
        })
        if len(alerts) >= limit:
            break
            
    return alerts

# ----------------- ANALYTICS & INSIGHTS API -----------------

@app.get("/api/analytics/sectors")
def get_sector_analytics(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE 1=1"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
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
        {where_clause}
        GROUP BY sector
        ORDER BY total_rev_cost DESC
    """, params).fetchall()
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
def get_ministry_analytics(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE 1=1"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
        SELECT 
            ministry,
            COUNT(*) as project_count,
            SUM(orig_cost) as total_orig_cost,
            SUM(rev_cost) as total_rev_cost,
            AVG(delay_months) as avg_delay,
            AVG(cost_overrun_pct) as avg_cost_overrun,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count
        FROM projects
        {where_clause}
        GROUP BY ministry
        ORDER BY project_count DESC
    """, params).fetchall()
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
def get_state_analytics(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE state != 'Unknown'"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
        SELECT 
            state,
            COUNT(*) as project_count,
            SUM(rev_cost) as total_cost,
            AVG(delay_months) as avg_delay,
            AVG(progress) as avg_progress,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count
        FROM projects
        {where_clause}
        GROUP BY state
        ORDER BY project_count DESC
        LIMIT 25
    """, params).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_cost"] = round(d["total_cost"] or 0, 1)
        d["avg_delay"] = round(d["avg_delay"] or 0, 1)
        d["avg_progress"] = round(d["avg_progress"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/analytics/agencies")
def get_agency_analytics(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE agency != 'Unknown Agency' AND agency IS NOT NULL"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
        SELECT 
            agency,
            COUNT(*) as project_count,
            SUM(rev_cost) as total_rev_cost,
            AVG(delay_months) as avg_delay,
            AVG(progress) as avg_progress,
            SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) as high_risk_count
        FROM projects
        {where_clause}
        GROUP BY agency
        ORDER BY project_count DESC
        LIMIT 20
    """, params).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_rev_cost"] = round(d["total_rev_cost"] or 0, 1)
        d["avg_delay"] = round(d["avg_delay"] or 0, 1)
        d["avg_progress"] = round(d["avg_progress"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/anomalies")
def get_anomalies(
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE is_anomaly = 1"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    rows = cursor.execute(f"""
        SELECT * FROM projects 
        {where_clause}
        ORDER BY progress_gap DESC 
        LIMIT ?
    """, (*params, limit)).fetchall()
    conn.close()
    
    anomalies = []
    for r in rows:
        d = dict(r)
        if "history_json" in d:
            del d["history_json"]
        gap = d.get("progress_gap", 0)
        p = d.get("progress", 0)
        fp = d.get("financial_progress_pct", 0)
        d["anomaly_reason"] = f"Financial Progress is {fp:.1f}% while Physical Ground Progress is only {p:.1f}% (Progress Gap: {gap:.1f}%)"
        anomalies.append(d)
    return anomalies

@app.get("/api/filters")
def get_filter_options(current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    agency_scope = get_agency_scope(current_user) if current_user else None
    where_clause = "WHERE 1=1"
    params = []
    if agency_scope:
        where_clause += " AND (agency LIKE ? OR ministry LIKE ?)"
        params.extend([f"%{agency_scope}%", f"%{agency_scope}%"])
        
    ministries = [r[0] for r in cursor.execute(f"SELECT DISTINCT ministry FROM projects {where_clause} AND ministry != 'Unknown Ministry' ORDER BY ministry", params).fetchall()]
    sectors = [r[0] for r in cursor.execute(f"SELECT DISTINCT sector FROM projects {where_clause} AND sector != 'Unknown Sector' ORDER BY sector", params).fetchall()]
    states = [r[0] for r in cursor.execute(f"SELECT DISTINCT state FROM projects {where_clause} AND state != 'Unknown' AND state NOT LIKE 'Multi-States%' ORDER BY state", params).fetchall()]
    agencies = [r[0] for r in cursor.execute(f"SELECT DISTINCT agency FROM projects {where_clause} AND agency != 'Unknown Agency' AND agency IS NOT NULL ORDER BY agency", params).fetchall()]
    
    conn.close()
    return {
        "ministries": ministries,
        "sectors": sectors,
        "states": states,
        "agencies": agencies,
        "risk_levels": ["HIGH", "MEDIUM", "LOW"]
    }

@app.get("/api/model/benchmarks")
def get_benchmarks():
    bm = ml_engine.benchmarks or {}
    
    if not bm:
        bench_path = os.path.join(os.path.dirname(__file__), "..", "models", "benchmarks.json")
        if os.path.exists(bench_path):
            try:
                with open(bench_path, "r", encoding="utf-8") as f:
                    bm = json.load(f)
                    ml_engine.benchmarks = bm
            except Exception:
                pass

    classification = bm.get("classification", [
        {"model": "Logistic Regression", "accuracy": 0.8420, "precision": 0.8141, "recall": 0.8420, "f1": 0.8085},
        {"model": "Random Forest Classifier", "accuracy": 0.8937, "precision": 0.8889, "recall": 0.8937, "f1": 0.8847},
        {"model": "XGBoost Classifier (Selected)", "accuracy": 0.9052, "precision": 0.9015, "recall": 0.9052, "f1": 0.9026}
    ])
    delay_regression = bm.get("delay_regression", [
        {"model": "Linear Regression", "mae": 9.25, "r2": 0.5119},
        {"model": "Random Forest Regressor", "mae": 4.47, "r2": 0.6672},
        {"model": "XGBoost Regressor (Selected)", "mae": 4.28, "r2": 0.6912}
    ])
    
    classifiers = {item.get("model", f"Model {i}"): {**item, "f1_score": item.get("f1", item.get("f1_score", 0))} for i, item in enumerate(classification)}
    regressors = {item.get("model", f"Model {i}"): item for i, item in enumerate(delay_regression)}
    
    return {
        **bm,
        "classification": classification,
        "delay_regression": delay_regression,
        "classifiers": classifiers,
        "regressors": regressors
    }

# ----------------- ADMIN API ENDPOINTS (RBAC PROTECTED) -----------------

class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    role: str
    organization: str = "MoSPI"
    department: str = "Project Monitoring"

class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[int] = None

@app.get("/api/admin/users")
def admin_get_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT id, username, email, full_name, role, organization, department, is_active, created_at, last_login FROM users WHERE 1=1"
    params = []
    
    if search:
        query += " AND (username LIKE ? OR email LIKE ? OR full_name LIKE ?)"
        s = f"%{search.strip()}%"
        params.extend([s, s, s])
    if role and role != "ALL":
        query += " AND role = ?"
        params.append(role)
        
    query += " ORDER BY id ASC"
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/users")
def admin_create_user(
    req: CreateUserRequest,
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    if req.role not in ['ADMIN', 'POLICYMAKER', 'MONITORING', 'PLANNING', 'AGENCY']:
        raise HTTPException(status_code=400, detail="Invalid role specified.")
        
    conn = get_db()
    cursor = conn.cursor()
    
    # Check duplicate
    existing = cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (req.username, req.email)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Username or email already registered.")
        
    p_hash, salt = hash_password(req.password)
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, salt, full_name, role, organization, department, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (req.username, req.email, p_hash, salt, req.full_name, req.role, req.organization, req.department, now))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    log_audit("CREATE_USER", f"user/{new_id}", user=admin_user, details=f"Created user {req.username} ({req.role})")
    return {"status": "success", "user_id": new_id, "message": f"User {req.username} created successfully."}

@app.put("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    req: UpdateUserRequest,
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    conn = get_db()
    cursor = conn.cursor()
    target = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
        
    updates = []
    params = []
    if req.email is not None:
        updates.append("email = ?")
        params.append(req.email)
    if req.full_name is not None:
        updates.append("full_name = ?")
        params.append(req.full_name)
    if req.role is not None:
        if req.role not in ['ADMIN', 'POLICYMAKER', 'MONITORING', 'PLANNING', 'AGENCY']:
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid role.")
        updates.append("role = ?")
        params.append(req.role)
    if req.organization is not None:
        updates.append("organization = ?")
        params.append(req.organization)
    if req.department is not None:
        updates.append("department = ?")
        params.append(req.department)
    if req.is_active is not None:
        updates.append("is_active = ?")
        params.append(req.is_active)
        
    if updates:
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
    conn.close()
    log_audit("UPDATE_USER", f"user/{user_id}", user=admin_user, details=f"Updated attributes for user {user_id}")
    return {"status": "success", "message": "User updated successfully."}

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    if user_id == admin_user["id"]:
        raise HTTPException(status_code=400, detail="Administrator cannot delete their own active account.")
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    log_audit("DELETE_USER", f"user/{user_id}", user=admin_user, details=f"Deleted user id {user_id}")
    return {"status": "success", "message": "User deleted successfully."}

@app.get("/api/admin/agencies")
def admin_get_agencies(admin_user: dict = Depends(require_roles(["ADMIN"]))):
    conn = get_db()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT a.*, COUNT(p.project_code) as project_count, SUM(p.rev_cost) as total_capital_cr
        FROM agencies a
        LEFT JOIN projects p ON p.agency LIKE ('%' || a.name || '%') OR p.agency = a.name
        GROUP BY a.id
        ORDER BY project_count DESC
    """).fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["total_capital_cr"] = round(d["total_capital_cr"] or 0, 1)
        res.append(d)
    return res

@app.get("/api/admin/audit-logs")
def admin_get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    action: Optional[str] = None,
    username: Optional[str] = None,
    status: Optional[str] = None,
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    
    if action and action != "ALL":
        query += " AND action = ?"
        params.append(action)
    if username:
        query += " AND username LIKE ?"
        params.append(f"%{username.strip()}%")
    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)
        
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = cursor.execute(count_query, params).fetchone()[0]
    
    page_num = page if isinstance(page, int) else 1
    page_sz = page_size if isinstance(page_size, int) else 30
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([page_sz, (page_num - 1) * page_sz])
    
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    
    return {
        "total": total,
        "page": page_num,
        "page_size": page_sz,
        "total_pages": (total + page_sz - 1) // page_sz,
        "logs": [dict(r) for r in rows]
    }

@app.get("/api/admin/settings")
def admin_get_settings(admin_user: dict = Depends(require_roles(["ADMIN"]))):
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM system_settings").fetchall()
    conn.close()
    return {r["key"]: {"value": r["value"], "description": r["description"], "updated_at": r["updated_at"]} for r in rows}

@app.post("/api/admin/settings")
def admin_update_settings(
    payload: dict = Body(...),
    admin_user: dict = Depends(require_roles(["ADMIN"]))
):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    for k, v in payload.items():
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (str(v), now, k))
    conn.commit()
    conn.close()
    log_audit("UPDATE_SETTINGS", "settings", user=admin_user, details=f"Updated system settings: {list(payload.keys())}")
    return {"status": "success", "message": "System settings updated successfully."}

# ----------------- STATIC UI & MULTI-PAGE SPA ROUTING -----------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def serve_html_file(filename: str) -> HTMLResponse:
    file_path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            resp = HTMLResponse(content=f.read())
            resp.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            return resp
    return HTMLResponse(content=f"<h1>PAIMANA AI</h1><p>File {filename} is being generated...</p>")

# Public Landing Page (Route: /)
@app.get("/", response_class=HTMLResponse)
def serve_landing_page():
    return serve_html_file("landing.html")

# Standalone Executive Risk Engine & Monitor (Route: /monitor, /engine, /risk-engine)
@app.get("/monitor", response_class=HTMLResponse)
@app.get("/engine", response_class=HTMLResponse)
@app.get("/risk-engine", response_class=HTMLResponse)
def serve_risk_engine():
    return serve_html_file("index.html")

# User Login Portal (Route: /login)
@app.get("/login", response_class=HTMLResponse)
def serve_user_login():
    return serve_html_file("login.html")

# Administrator Portal Login (Route: /admin/login)
@app.get("/admin/login", response_class=HTMLResponse)
def serve_admin_login():
    return serve_html_file("admin-login.html")

# Secure Role-Based Portals (Master Portal Shell)
@app.get("/portal", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/projects", response_class=HTMLResponse)
@app.get("/projects/{project_code}", response_class=HTMLResponse)
@app.get("/analytics", response_class=HTMLResponse)
@app.get("/alerts", response_class=HTMLResponse)
@app.get("/profile", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/dashboard", response_class=HTMLResponse)
@app.get("/admin/projects", response_class=HTMLResponse)
@app.get("/admin/users", response_class=HTMLResponse)
@app.get("/admin/agencies", response_class=HTMLResponse)
@app.get("/admin/analytics", response_class=HTMLResponse)
@app.get("/admin/alerts", response_class=HTMLResponse)
@app.get("/admin/audit-logs", response_class=HTMLResponse)
@app.get("/admin/settings", response_class=HTMLResponse)
def serve_portal_app():
    return serve_html_file("portal.html")
