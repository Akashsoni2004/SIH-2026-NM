import os
import sqlite3
import hashlib
import secrets
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "projects.sqlite")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    expected_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(expected_hash, password_hash)

def init_db_schema():
    """Initializes tables for auth, agencies, audit logs, and settings if not present."""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN', 'POLICYMAKER', 'MONITORING', 'PLANNING', 'AGENCY')),
            organization TEXT NOT NULL DEFAULT 'MoSPI',
            department TEXT NOT NULL DEFAULT 'Project Monitoring',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    """)
    
    # 2. Agencies Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            org_type TEXT NOT NULL DEFAULT 'PSU / Central Agency',
            ministry TEXT NOT NULL,
            contact_email TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    
    # 3. Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            status TEXT NOT NULL DEFAULT 'SUCCESS',
            timestamp TEXT NOT NULL
        )
    """)
    
    # 4. System Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    
    # Seed default settings
    default_settings = [
        ("high_risk_threshold", "70", "Risk score threshold above which projects are classified as HIGH risk"),
        ("delay_alarm_months", "6", "Schedule delay in months triggering high-priority delay alarm"),
        ("cost_overrun_alarm_pct", "15", "Cost overrun percentage triggering critical escalation notice"),
        ("anomaly_sensitivity", "0.05", "Isolation Forest anomaly contamination factor"),
        ("model_version", "XGBoost-v2.4-MoSPI", "Active machine learning risk prediction engine release")
    ]
    for key, val, desc in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        """, (key, val, desc, datetime.utcnow().isoformat()))
        
    # Seed default agencies based on existing projects
    existing_agencies = cursor.execute("SELECT COUNT(*) FROM agencies").fetchone()[0]
    if existing_agencies == 0:
        cursor.execute("""
            SELECT DISTINCT agency, ministry 
            FROM projects 
            WHERE agency != 'Unknown Agency' AND agency IS NOT NULL
            LIMIT 40
        """)
        agency_rows = cursor.fetchall()
        for idx, (ag_name, ag_min) in enumerate(agency_rows):
            short_code = ag_name[:12].upper().replace(" ", "-").replace("[", "").replace("]", "")
            cursor.execute("""
                INSERT OR IGNORE INTO agencies (code, name, org_type, ministry, contact_email, is_active)
                VALUES (?, ?, 'Central Implementing Agency', ?, ?, 1)
            """, (f"AGY-{idx+101}", ag_name, ag_min or 'Central Sector', f"contact@{short_code.lower()}.gov.in"))
            
        # Ensure NHAI and AAI are explicitly registered
        cursor.execute("""
            INSERT OR IGNORE INTO agencies (code, name, org_type, ministry, contact_email, is_active)
            VALUES ('AGY-NHAI', 'National Highways Authority of India [NHAI]', 'Statutory Authority', 'Ministry of Road Transport and Highways', 'nodal@nhai.gov.in', 1)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO agencies (code, name, org_type, ministry, contact_email, is_active)
            VALUES ('AGY-AAI', 'Airport Authority of India [AAI]', 'Public Sector Enterprise', 'Ministry of Civil Aviation', 'ed-monitoring@aai.gov.in', 1)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO agencies (code, name, org_type, ministry, contact_email, is_active)
            VALUES ('AGY-RAIL', 'Ministry of Railways', 'Government Department', 'Ministry of Railways', 'gati-shakti@railways.gov.in', 1)
        """)

    # Seed demo users for jury / evaluation
    existing_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing_users == 0:
        demo_users = [
            (
                "admin", "admin@paimana.gov.in", "Admin@2026",
                "Dr. Rajesh Verma", "ADMIN", "Infrastructure and Project Monitoring Division",
                "MoSPI IPMD Headquarters"
            ),
            (
                "policymaker", "policymaker@paimana.gov.in", "Policy@2026",
                "Smt. Ananya Sen", "POLICYMAKER", "Ministry of Statistics & Programme Implementation",
                "National Infrastructure Advisory Council"
            ),
            (
                "monitoring", "monitoring@paimana.gov.in", "Monitor@2026",
                "Shri Vikram Malhotra", "MONITORING", "Project Monitoring & Evaluation Division",
                "IPMD Project Cell"
            ),
            (
                "planning", "planning@paimana.gov.in", "Plan@2026",
                "Dr. Meenakshi Sundaram", "PLANNING", "NITI Aayog / MoSPI Macro Cell",
                "Infrastructure Planning Division"
            ),
            (
                "nhai_officer", "nhai.officer@paimana.gov.in", "Agency@2026",
                "Eng. Sunil Deshmukh", "AGENCY", "National Highways Authority of India [NHAI]",
                "Highways Project Directorate"
            ),
            (
                "aai_officer", "aai.officer@paimana.gov.in", "Agency@2026",
                "Capt. Rakesh Sharma", "AGENCY", "Airport Authority of India [AAI]",
                "Civil Aviation Projects Directorate"
            ),
            (
                "railways_officer", "railways.officer@paimana.gov.in", "Agency@2026",
                "Shri Alok Mathur", "AGENCY", "Ministry of Railways",
                "Rail Infrastructure & Modernization Division"
            )
        ]
        
        now = datetime.utcnow().isoformat()
        for uname, email, raw_pwd, name, role, org, dept in demo_users:
            p_hash, salt = hash_password(raw_pwd)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt, full_name, role, organization, department, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (uname, email, p_hash, salt, name, role, org, dept, now))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db_schema()
    print("Database schema successfully initialized and seeded.")
