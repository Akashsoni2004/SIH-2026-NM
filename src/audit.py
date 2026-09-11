from datetime import datetime
from typing import Optional
from src.db import get_db

def log_audit(
    action: str,
    resource: Optional[str] = None,
    user: Optional[dict] = None,
    username: Optional[str] = None,
    role: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    status: str = "SUCCESS"
):
    """Asynchronously or synchronously writes an entry to the audit_logs table."""
    try:
        user_id = user.get("id") if user else None
        uname = username or (user.get("username") if user else "anonymous")
        u_role = role or (user.get("role") if user else "PUBLIC")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, role, action, resource, details, ip_address, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            uname,
            u_role,
            action,
            resource,
            details,
            ip_address,
            status,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: Audit log recording failed: {e}")
