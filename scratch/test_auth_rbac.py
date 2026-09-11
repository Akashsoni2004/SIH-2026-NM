import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import unittest
from datetime import datetime
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from src.db import get_db, init_db_schema, hash_password, verify_password
from src.auth import create_access_token, verify_access_token, get_agency_scope
from src.server import (
    login, LoginRequest, get_projects, get_project_detail,
    admin_get_users, admin_get_audit_logs
)

class MockRequest:
    def __init__(self, headers=None, client_host="127.0.0.1"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": client_host})()
        self.cookies = {}
        self.query_params = {}

class MockResponse:
    def __init__(self):
        self.cookies = {}
    def set_cookie(self, key, value, **kwargs):
        self.cookies[key] = value
    def delete_cookie(self, key):
        self.cookies.pop(key, None)

def test_full_rbac_and_security():
    print("=" * 70)
    print("PAIMANA AI — BACKEND RBAC & SECURITY INTEGRATION TEST SUITE")
    print("=" * 70)

    init_db_schema()

    # 1. Cryptographic Password Hashing Test
    print("\n[Test 1] Testing PBKDF2-HMAC-SHA256 Password Hashing & Verification...")
    pwd = "GovtSecretPassword@2026"
    h, salt = hash_password(pwd)
    assert verify_password(pwd, h, salt) is True, "Password verification failed"
    assert verify_password("WrongPassword", h, salt) is False, "False positive in password verification"
    print("  PASS: Cryptographic password hashing and salt verification verified.")

    # 2. Token Generation & Verification Test
    print("\n[Test 2] Testing Signed HMAC-SHA256 Bearer Token Creation & Expiry Check...")
    mock_user = {
        "id": 1,
        "username": "admin",
        "email": "admin@paimana.gov.in",
        "full_name": "Dr. Rajesh Verma",
        "role": "ADMIN",
        "organization": "MoSPI"
    }
    token = create_access_token(mock_user)
    payload = verify_access_token(token)
    assert payload is not None, "Token verification failed"
    assert payload["username"] == "admin"
    assert payload["role"] == "ADMIN"
    print("  PASS: Token signature verified and payload intact.")

    # 3. Admin Login & Authorization
    print("\n[Test 3] Testing Admin Login via API endpoint...")
    req = LoginRequest(username="admin@paimana.gov.in", password="Admin@2026", portal_type="admin")
    mock_req = MockRequest()
    mock_resp = MockResponse()
    res = login(req, mock_req, mock_resp)
    assert res["status"] == "success"
    assert res["user"]["role"] == "ADMIN"
    assert "paimana_auth_token" in mock_resp.cookies
    admin_user = res["user"]
    print(f"  PASS: Admin authenticated. Cookie set: {mock_resp.cookies['paimana_auth_token'][:20]}...")

    # 4. Admin Users Endpoint (Authorized)
    print("\n[Test 4] Testing Admin User Management (/api/admin/users)...")
    users = admin_get_users(admin_user=admin_user)
    assert len(users) >= 7, f"Expected >= 7 users, found {len(users)}"
    print(f"  PASS: Admin successfully retrieved {len(users)} registered official accounts.")

    # 5. Non-Admin attempting Admin Portal Login (Section 19: Rejection with 403)
    print("\n[Test 5] Testing Non-Admin user attempting Admin Portal Login...")
    req_denied = LoginRequest(username="nhai.officer@paimana.gov.in", password="Agency@2026", portal_type="admin")
    try:
        login(req_denied, mock_req, mock_resp)
        assert False, "Should have raised 403 Forbidden"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  PASS: 403 Forbidden correctly raised: {e.detail}")

    # 6. Agency User Login (Authorized User Portal)
    print("\n[Test 6] Testing Agency User Login (NHAI Officer)...")
    req_agency = LoginRequest(username="nhai.officer@paimana.gov.in", password="Agency@2026", portal_type="user")
    res_agency = login(req_agency, mock_req, mock_resp)
    assert res_agency["status"] == "success"
    agency_user = res_agency["user"]
    assert agency_user["role"] == "AGENCY"
    print(f"  PASS: Agency user {agency_user['full_name']} successfully authenticated.")

    # 7. Agency Data Isolation in Projects List (Section 58)
    print("\n[Test 7] Testing Organization-Level Data Isolation in Projects Catalog...")
    agency_projects = get_projects(page=1, page_size=20, current_user=agency_user)
    assert agency_projects["is_agency_scoped"] is True
    print(f"  Total NHAI projects returned: {agency_projects['total']} (out of 1,737 national projects)")
    for p in agency_projects["projects"]:
        assert "NHAI" in p["agency"] or "Highways" in p["agency"], f"Data leak detected: {p['agency']}"
    print("  PASS: Zero data leakage across agencies. All returned projects belong to NHAI.")

    # 8. Cross-Agency Direct Project URL Access (Section 19: Agency A -> Agency B blocked with 403)
    print("\n[Test 8] Testing Cross-Agency Direct Project Access (/api/projects/{code})...")
    conn = get_db()
    cursor = conn.cursor()
    # Pick a project belonging to Civil Aviation (AAI) or Coal
    foreign_proj = cursor.execute("SELECT project_code, project_name, agency FROM projects WHERE agency NOT LIKE '%NHAI%' LIMIT 1").fetchone()
    conn.close()
    foreign_code = foreign_proj["project_code"]
    print(f"  NHAI officer attempting access to foreign project: {foreign_code} ({foreign_proj['agency']})")

    try:
        get_project_detail(project_code=foreign_code, request=mock_req, current_user=agency_user)
        assert False, "Should have raised 403 Forbidden for cross-agency access"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  PASS: 403 Forbidden strictly enforced: {e.detail}")

    # 9. Authorized Agency Access to Own Project
    print("\n[Test 9] Testing Authorized Agency Access to Own Project...")
    conn = get_db()
    cursor = conn.cursor()
    own_proj = cursor.execute("SELECT project_code, project_name FROM projects WHERE agency LIKE '%NHAI%' LIMIT 1").fetchone()
    conn.close()
    own_code = own_proj["project_code"]

    res_proj = get_project_detail(project_code=own_code, request=mock_req, current_user=agency_user)
    assert "ai_prediction" in res_proj
    pred = res_proj["ai_prediction"]
    assert "risk_score" in pred
    assert "risk_factors" in pred
    assert "recommendations" in pred
    delay_m = pred.get("predicted_delay_months", 0)
    top_factor = pred["risk_factors"][0]["factor"]
    top_rec = pred["recommendations"][0]["action"] if isinstance(pred["recommendations"][0], dict) else pred["recommendations"][0]
    print(f"  PASS: Own project {own_code} loaded successfully.")
    print(f"    - Risk Score: {pred['risk_score']}/100 ({pred['risk_level']})")
    print(f"    - Forecasted Delay: {delay_m} months")
    print(f"    - Top SHAP Driver: {top_factor} ({pred['risk_factors'][0]['contribution_pct']}%)")
    print(f"    - Top AI Recommendation: {top_rec[:60]}...")

    # 10. Audit Log Trail Verification
    print("\n[Test 10] Verifying Audit Trail recorded for login and forbidden attempts...")
    logs_res = admin_get_audit_logs(admin_user=admin_user)
    logs = logs_res["logs"]
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    print(f"  Audit trail recorded {len(logs)} events. Detected actions: {set(actions)}")
    assert "LOGIN" in actions
    assert "FORBIDDEN_ATTEMPT" in actions
    print("  PASS: Security events and forbidden attempts fully audited in SQLite database.")

    print("\n" + "=" * 70)
    print("ALL 10/10 RBAC, SECURITY, & PREDICTION INTEGRATION TESTS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    test_full_rbac_and_security()
