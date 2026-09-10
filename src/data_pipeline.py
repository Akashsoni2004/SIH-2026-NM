import os
import re
import sys
import sqlite3
import openpyxl
import pandas as pd
import numpy as np
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
WORKSPACE_DIR = os.path.dirname(os.path.dirname(__file__))

FILES = [
    ("April", "FlashReport_April2026.xlsx", datetime(2026, 4, 1)),
    ("May", "FlashReport_May2026.xlsx", datetime(2026, 5, 1)),
    ("June", "FlashReport_June_2026.xlsx", datetime(2026, 6, 1)),
    ("July", "FlashReport_July_2026.xlsx", datetime(2026, 7, 1))
]

def parse_date(date_str):
    if not date_str or str(date_str).strip() in ['-', 'NA', 'None', '', 'nan']:
        return None
    date_str = str(date_str).strip()
    m = re.match(r'(\d{1,2})/(\d{4})', date_str)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        return datetime(year, month, 1)
    return None

def parse_float(val):
    if val is None or pd.isna(val):
        return np.nan
    val_str = str(val).replace(',', '').strip()
    m = re.search(r'[-+]?\d*\.?\d+', val_str)
    if m:
        try:
            return float(m.group(0))
        except:
            return np.nan
    return np.nan

def parse_project_cell(text):
    if text is None:
        return "Unknown Project", "Unknown Agency", None, None, None
    lines = [l.strip() for l in str(text).split('\n') if l.strip()]
    raw_str = " ".join(lines)
    agency = "Unknown Agency"
    project_code = None
    ocms_code = None
    pmgid = None
    
    code_match = re.search(r'\((\d{5,7})\)', raw_str)
    if code_match:
        project_code = code_match.group(1)
        
    ocms_match = re.search(r'\(([A-Z]\d{7,9}|-)\)', raw_str)
    if ocms_match and ocms_match.group(1) != '-':
        ocms_code = ocms_match.group(1)
        
    p_matches = re.findall(r'\(([^)]+)\)', raw_str)
    if p_matches:
        for m in p_matches:
            if not m.isdigit() and not re.match(r'^[A-Z]\d+$', m) and m != '-' and '/' not in m:
                agency = m
                break
                
    p_name = raw_str.split('(')[0].strip() if '(' in raw_str else raw_str
    if not p_name and len(lines) > 0:
        p_name = lines[0]
        
    return p_name, agency, project_code, ocms_code, pmgid

def parse_double_val(val_str):
    if val_str is None or pd.isna(val_str):
        return None, None
    s = str(val_str).strip().replace('\n', ' ')
    m = re.match(r'^([^(]+)(?:\(([^)]*)\))?', s)
    if m:
        v1 = m.group(1).strip() if m.group(1) else None
        v2 = m.group(2).strip() if m.group(2) else None
        return v1, v2
    return s, None

def extract_report(month_label, fname, report_date):
    filepath = os.path.join(WORKSPACE_DIR, fname)
    if not os.path.exists(filepath):
        print(f"Warning: File {filepath} does not exist.")
        return pd.DataFrame()
        
    print(f"Parsing {month_label} report from {fname}...")
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb["Table 1"]
    
    projects = []
    current_ministry = "Unknown Ministry"
    current_sector = "Unknown Sector"
    in_t6 = False
    
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if idx < 100:
            continue
        vals = [c for c in row if c is not None]
        line = " ".join([str(c).strip() for c in vals])
        
        if "Table 6: All Ongoing Projects" in line:
            in_t6 = True
            continue
        if not in_t6:
            continue
        if "Sl.No" in line and "Project Name" in line:
            continue
        if "All Ongoing Projects" in line and ("2026" in line or "2025" in line):
            continue
        if line.startswith("Total (") or "Total (" in line:
            continue
            
        # Sector / Ministry hierarchy
        if row[0] is None:
            for c in row:
                if c is not None:
                    text = str(c).strip()
                    if "Ministry of" in text or "Department of" in text:
                        current_ministry = text
                    elif text != "Sl.No" and not text.isdigit() and len(text) < 70 and not "Total" in text:
                        current_sector = text
                    break
            continue
            
        # Project row
        if str(row[0]).strip().isdigit():
            p_cell = row[4] if len(row) > 4 and row[4] is not None else (row[5] if len(row) > 5 and row[5] is not None else None)
            p_name, agency, p_code, ocms_code, pmgid = parse_project_cell(p_cell)
            
            if not p_code:
                all_text = " ".join([str(c) for c in row if c is not None])
                p_code_match = re.search(r'\((\d{5,7})\)', all_text)
                if p_code_match:
                    p_code = p_code_match.group(1)
                    
            if not p_code:
                continue
                
            state = "Unknown"
            for s_col in [23, 24, 22, 25]:
                if len(row) > s_col and row[s_col] is not None:
                    state = str(row[s_col]).strip()
                    break
                    
            app_raw = None
            for d_col in [29, 30, 28, 31]:
                if len(row) > d_col and row[d_col] is not None:
                    app_raw = row[d_col]
                    break
            app_date, start_date = parse_double_val(app_raw)
            
            doc_raw = None
            for doc_col in [36, 37, 35, 38]:
                if len(row) > doc_col and row[doc_col] is not None:
                    doc_raw = row[doc_col]
                    break
            target_doc, revised_doc = parse_double_val(doc_raw)
            
            cost_raw = None
            for c_col in [45, 46, 44, 47]:
                if len(row) > c_col and row[c_col] is not None:
                    cost_raw = row[c_col]
                    break
            orig_cost, rev_cost = parse_double_val(cost_raw)
            
            exp_val = None
            for e_col in [52, 53, 51, 54]:
                if len(row) > e_col and row[e_col] is not None:
                    exp_val = row[e_col]
                    break
                    
            prog_val = None
            for p_col in [60, 61, 59, 62]:
                if len(row) > p_col and row[p_col] is not None:
                    prog_val = row[p_col]
                    break
                    
            orig_c = parse_float(orig_cost)
            rev_c = parse_float(rev_cost) if rev_cost else orig_c
            exp = parse_float(exp_val)
            prog = parse_float(prog_val)
            
            projects.append({
                "project_code": str(p_code),
                "project_name": p_name,
                "agency": agency,
                "ministry": current_ministry,
                "sector": current_sector,
                "state": state,
                "app_date": app_date,
                "start_date": start_date,
                "target_doc": target_doc,
                "revised_doc": revised_doc,
                "orig_cost": orig_c if pd.notna(orig_c) and orig_c > 0 else 0.0,
                "rev_cost": rev_c if pd.notna(rev_c) and rev_c > 0 else (orig_c if pd.notna(orig_c) and orig_c > 0 else 0.0),
                "expenditure": exp if pd.notna(exp) and exp >= 0 else 0.0,
                "progress": prog if pd.notna(prog) and 0 <= prog <= 100 else 0.0,
                "report_month": month_label,
                "report_date": report_date
            })
            
    df = pd.DataFrame(projects)
    print(f"Extracted {len(df)} projects for {month_label}.")
    return df

def build_longitudinal_dataset():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    monthly_dfs = {}
    for month_label, fname, report_date in FILES:
        df_m = extract_report(month_label, fname, report_date)
        monthly_dfs[month_label] = df_m

    # Base dataset is the latest available month (July 2026)
    base_df = monthly_dfs["July"].copy()
    if base_df.empty:
        raise RuntimeError("Failed to parse July 2026 report.")
        
    # Helper to calculate delay in months
    def get_delay_months(target_str, rev_str):
        t = parse_date(target_str)
        r = parse_date(rev_str)
        if t and r:
            return max(-60, min(360, (r.year - t.year) * 12 + (r.month - t.month)))
        return 0

    # Calculate initial delay
    base_df["delay_months"] = [
        get_delay_months(row["target_doc"], row["revised_doc"]) 
        for _, row in base_df.iterrows()
    ]
    
    # Financial progress % & Progress Gap
    base_df["cost_overrun_pct"] = np.where(
        base_df["orig_cost"] > 0,
        np.maximum(0.0, ((base_df["rev_cost"] - base_df["orig_cost"]) / base_df["orig_cost"]) * 100.0),
        0.0
    )
    base_df["cost_growth"] = np.maximum(0.0, base_df["rev_cost"] - base_df["orig_cost"])
    base_df["financial_progress_pct"] = np.where(
        base_df["rev_cost"] > 0,
        np.clip((base_df["expenditure"] / base_df["rev_cost"]) * 100.0, 0.0, 200.0),
        0.0
    )
    base_df["progress_gap"] = base_df["financial_progress_pct"] - base_df["progress"]
    
    # Compute elapsed time and planned duration
    def get_time_features(row):
        s_date = parse_date(row["start_date"]) or parse_date(row["app_date"])
        t_doc = parse_date(row["target_doc"])
        rep_date = row["report_date"]
        
        elapsed = 12.0
        duration = 36.0
        if s_date:
            elapsed = max(1.0, (rep_date.year - s_date.year) * 12.0 + (rep_date.month - s_date.month))
            if t_doc:
                duration = max(1.0, (t_doc.year - s_date.year) * 12.0 + (t_doc.month - s_date.month))
            else:
                duration = max(elapsed, 36.0)
        return elapsed, duration

    time_feats = [get_time_features(row) for _, row in base_df.iterrows()]
    base_df["time_elapsed_months"] = [tf[0] for tf in time_feats]
    base_df["planned_duration_months"] = [tf[1] for tf in time_feats]
    base_df["time_utilization_pct"] = np.clip(
        (base_df["time_elapsed_months"] / base_df["planned_duration_months"]) * 100.0, 
        0.0, 500.0
    )
    
    # Merge monthly progression across April, May, June, July for longitudinal velocity
    apr_df = monthly_dfs["April"].set_index("project_code")
    may_df = monthly_dfs["May"].set_index("project_code")
    jun_df = monthly_dfs["June"].set_index("project_code")
    
    progress_velocities = []
    exp_velocities = []
    delay_slippages = []
    histories = []
    
    for _, row in base_df.iterrows():
        p_code = row["project_code"]
        p_apr = apr_df.loc[p_code]["progress"] if p_code in apr_df.index else row["progress"]
        p_may = may_df.loc[p_code]["progress"] if p_code in may_df.index else p_apr
        p_jun = jun_df.loc[p_code]["progress"] if p_code in jun_df.index else p_may
        p_jul = row["progress"]
        
        e_apr = apr_df.loc[p_code]["expenditure"] if p_code in apr_df.index else row["expenditure"]
        e_may = may_df.loc[p_code]["expenditure"] if p_code in may_df.index else e_apr
        e_jun = jun_df.loc[p_code]["expenditure"] if p_code in jun_df.index else e_may
        e_jul = row["expenditure"]
        
        # Delay slippage
        d_apr = get_delay_months(
            apr_df.loc[p_code]["target_doc"], apr_df.loc[p_code]["revised_doc"]
        ) if p_code in apr_df.index else row["delay_months"]
        d_jul = row["delay_months"]
        
        pv = (p_jul - p_apr) / 3.0 if pd.notna(p_jul) and pd.notna(p_apr) else 0.0
        ev = (e_jul - e_apr) / 3.0 if pd.notna(e_jul) and pd.notna(e_apr) else 0.0
        ds = max(0, d_jul - d_apr)
        
        progress_velocities.append(round(pv, 2))
        exp_velocities.append(round(ev, 2))
        delay_slippages.append(ds)
        
        # Monthly history payload for UI charts
        history_points = [
            {"month": "April 2026", "progress": float(p_apr), "expenditure": float(e_apr)},
            {"month": "May 2026", "progress": float(p_may), "expenditure": float(e_may)},
            {"month": "June 2026", "progress": float(p_jun), "expenditure": float(e_jun)},
            {"month": "July 2026", "progress": float(p_jul), "expenditure": float(e_jul)}
        ]
        histories.append(history_points)
        
    base_df["progress_velocity"] = progress_velocities
    base_df["expenditure_velocity"] = exp_velocities
    base_df["delay_slippage"] = delay_slippages
    
    # Target Risk Level Assignment
    def classify_risk(row):
        d = row["delay_months"]
        c = row["cost_overrun_pct"]
        gap = row["progress_gap"]
        prog = row["progress"]
        slip = row["delay_slippage"]
        
        if d > 12 or c > 20 or (gap > 25 and prog < 50) or slip >= 3:
            return "HIGH"
        elif d > 0 or c > 0 or gap > 12:
            return "MEDIUM"
        else:
            return "LOW"
            
    base_df["risk_level"] = [classify_risk(row) for _, row in base_df.iterrows()]
    
    # Store history as JSON string for sqlite/parquet
    import json
    base_df["history_json"] = [json.dumps(h) for h in histories]
    
    # Save parquet (if pyarrow available) and csv
    csv_path = os.path.join(DATA_DIR, "projects_master.csv")
    base_df.to_csv(csv_path, index=False)
    try:
        parquet_path = os.path.join(DATA_DIR, "projects_master.parquet")
        base_df.to_parquet(parquet_path, index=False)
        print(f"Saved master parquet to {parquet_path}")
    except Exception as e:
        print(f"Parquet engine not available, relying on CSV and SQLite ({e})")
    
    # Save SQLite database
    db_path = os.path.join(DATA_DIR, "projects.sqlite")
    conn = sqlite3.connect(db_path)
    base_df.to_sql("projects", conn, if_exists="replace", index=False)
    # Create index on project_code, ministry, sector, state, risk_level
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON projects (project_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk ON projects (risk_level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_min ON projects (ministry)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec ON projects (sector)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_state ON projects (state)")
    conn.commit()
    conn.close()
    print(f"Saved SQLite database with indices to {db_path}")
    return base_df

if __name__ == "__main__":
    df = build_longitudinal_dataset()
    print("\nDataset Build Complete! Summary:")
    print(f"Total Projects: {len(df)}")
    print(f"Risk Counts:\n{df['risk_level'].value_counts()}")
    print(f"Total Original Cost: ₹{df['orig_cost'].sum():,.1f} Cr")
    print(f"Total Revised Cost: ₹{df['rev_cost'].sum():,.1f} Cr")
    print(f"Total Expenditure: ₹{df['expenditure'].sum():,.1f} Cr")
