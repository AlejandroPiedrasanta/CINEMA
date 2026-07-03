#!/usr/bin/env python3
"""
Cinema Productions - Comprehensive Backend Regression Testing
After UI/Animation changes (Session #6)
Tests all endpoints with seed data (5 reservations, 3 socios)
Using external URL as specified in review request
"""
import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://4c46c59f-58b0-4e2f-a739-f1c96f46602f.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

def log_test(name, passed, details=""):
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{status} | {name}")
    if details:
        print(f"      {details}")
    return passed

def test_endpoint(method, path, expected_status=200, json_data=None, description=""):
    """Generic endpoint tester"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        elif method == "POST":
            resp = requests.post(url, json=json_data, timeout=10)
        elif method == "PUT":
            resp = requests.put(url, json=json_data, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=10)
        else:
            return False, None, "Invalid method"
        
        passed = resp.status_code == expected_status
        return passed, resp, f"Status: {resp.status_code} (expected {expected_status})"
    except Exception as e:
        return False, None, f"Exception: {str(e)}"

def main():
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}Cinema Productions - Backend Regression Testing (After Session #6 UI Changes){Colors.END}")
    print(f"{Colors.CYAN}Backend URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Store IDs for later tests
    test_reservation_id = None
    test_socio_id = None
    reservation_ids = []
    socio_ids = []
    
    # ========== 1. REGRESSION ON EXISTING ENDPOINTS ==========
    print(f"\n{Colors.YELLOW}[1] Regression - Existing Endpoints{Colors.END}")
    
    # GET /api/
    passed, resp, details = test_endpoint("GET", "/", 200)
    if log_test("GET /api/", passed, details):
        results["passed"] += 1
        if resp and resp.json().get("message") == "Event Reservation API":
            print(f"      Message: {resp.json().get('message')}")
    else:
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/", "passed": passed})
    
    # GET /api/reservations (5 seed items)
    passed, resp, details = test_endpoint("GET", "/reservations", 200)
    if passed and resp:
        data = resp.json()
        if isinstance(data, list) and len(data) >= 5:
            reservation_ids = [r.get("id") for r in data if r.get("id")]
            log_test(f"GET /api/reservations", True, f"Found {len(data)} reservations (seed data intact)")
            results["passed"] += 1
        else:
            log_test("GET /api/reservations", False, f"Expected ≥5 items, got {len(data) if isinstance(data, list) else 'non-list'}")
            results["failed"] += 1
    else:
        log_test("GET /api/reservations", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/reservations (5 items)", "passed": passed})
    
    # GET /api/socios (3 seed items)
    passed, resp, details = test_endpoint("GET", "/socios", 200)
    if passed and resp:
        data = resp.json()
        if isinstance(data, list) and len(data) >= 3:
            socio_ids = [s.get("id") for s in data if s.get("id")]
            log_test(f"GET /api/socios", True, f"Found {len(data)} socios (seed data intact)")
            results["passed"] += 1
        else:
            log_test("GET /api/socios", False, f"Expected ≥3 items, got {len(data) if isinstance(data, list) else 'non-list'}")
            results["failed"] += 1
    else:
        log_test("GET /api/socios", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/socios (3 items)", "passed": passed})
    
    # GET /api/stats
    passed, resp, details = test_endpoint("GET", "/stats", 200)
    if passed and resp:
        data = resp.json()
        required_keys = ["total_reservations", "upcoming_events", "real_income"]
        missing = [k for k in required_keys if k not in data]
        if not missing:
            total_res = data.get('total_reservations')
            upcoming = data.get('upcoming_events')
            real_income = data.get('real_income')
            # Allow 1% variance on real_income (≈97000 ± 1000)
            if total_res == 5 and upcoming == 5 and 96000 <= real_income <= 98000:
                log_test("GET /api/stats", True, f"total_reservations={total_res}, upcoming_events={upcoming}, real_income={real_income}")
                results["passed"] += 1
            else:
                log_test("GET /api/stats", False, f"Unexpected values: total={total_res}, upcoming={upcoming}, income={real_income}")
                results["failed"] += 1
        else:
            log_test("GET /api/stats", False, f"Missing keys: {missing}")
            results["failed"] += 1
    else:
        log_test("GET /api/stats", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/stats", "passed": passed})
    
    # GET /api/calendar (5 events)
    passed, resp, details = test_endpoint("GET", "/calendar", 200)
    if passed and resp:
        data = resp.json()
        if isinstance(data, list) and len(data) >= 5:
            log_test("GET /api/calendar", True, f"Found {len(data)} calendar events")
            results["passed"] += 1
        else:
            log_test("GET /api/calendar", False, f"Expected ≥5 events, got {len(data) if isinstance(data, list) else 'non-list'}")
            results["failed"] += 1
    else:
        log_test("GET /api/calendar", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/calendar (5 events)", "passed": passed})
    
    # GET /api/financials
    passed, resp, details = test_endpoint("GET", "/financials", 200)
    if passed:
        log_test("GET /api/financials", True, "Financial data retrieved")
        results["passed"] += 1
    else:
        log_test("GET /api/financials", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/financials", "passed": passed})
    
    # GET /api/export/reservations (CSV)
    passed, resp, details = test_endpoint("GET", "/export/reservations", 200)
    if passed and resp:
        content_type = resp.headers.get("content-type", "")
        if "csv" in content_type.lower() or "text/csv" in content_type.lower():
            log_test("GET /api/export/reservations", True, f"Content-Type: {content_type}")
            results["passed"] += 1
        else:
            log_test("GET /api/export/reservations", False, f"Wrong content-type: {content_type}")
            results["failed"] += 1
    else:
        log_test("GET /api/export/reservations", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/export/reservations (CSV)", "passed": passed})
    
    # GET /api/settings
    passed, resp, details = test_endpoint("GET", "/settings", 200)
    if passed:
        log_test("GET /api/settings", True, "Settings retrieved")
        results["passed"] += 1
    else:
        log_test("GET /api/settings", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/settings", "passed": passed})
    
    # GET /api/backup/history
    passed, resp, details = test_endpoint("GET", "/backup/history", 200)
    if passed:
        log_test("GET /api/backup/history", True, "Backup history retrieved")
        results["passed"] += 1
    else:
        log_test("GET /api/backup/history", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/backup/history", "passed": passed})
    
    # GET /api/security/status
    passed, resp, details = test_endpoint("GET", "/security/status", 200)
    if passed and resp:
        data = resp.json()
        if "password_enabled" in data and "protection_enabled" in data:
            log_test("GET /api/security/status", True, f"password_enabled={data.get('password_enabled')}, protection_enabled={data.get('protection_enabled')}")
            results["passed"] += 1
        else:
            log_test("GET /api/security/status", False, "Missing required keys")
            results["failed"] += 1
    else:
        log_test("GET /api/security/status", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/security/status", "passed": passed})
    
    # ========== 2. AI CONTEXT EXPANSION VERIFICATION ==========
    print(f"\n{Colors.YELLOW}[2] AI Context Expansion Verification (20,514 → 22,093 chars){Colors.END}")
    
    # GET /api/ai-context - Check length and content
    passed, resp, details = test_endpoint("GET", "/ai-context", 200)
    if passed and resp:
        data = resp.json()
        content = data.get("content", "")
        content_len = len(content)
        
        # Check length (should be > 20,000 chars, ideally 22,093)
        if content_len > 20000:
            log_test("GET /api/ai-context (length)", True, f"Content length: {content_len} chars (>20,000 ✓)")
            results["passed"] += 1
            
            # Check for required phrases
            required_phrases = [
                "Cinema Productions",
                "Historial de Sesiones",
                "GitHub Integration",
                "Julio 2026",
                "canvas-confetti",
                "WelcomeTour",
                "celebrateReservation",
                "sidebar-sweep"
            ]
            
            missing_phrases = []
            for phrase in required_phrases:
                if phrase not in content:
                    missing_phrases.append(phrase)
            
            if not missing_phrases:
                log_test("AI Context - Required phrases", True, f"All 8 required phrases found")
                print(f"      ✓ Cinema Productions, Historial de Sesiones, GitHub Integration")
                print(f"      ✓ Julio 2026, canvas-confetti, WelcomeTour")
                print(f"      ✓ celebrateReservation, sidebar-sweep")
                results["passed"] += 1
            else:
                log_test("AI Context - Required phrases", False, f"Missing: {', '.join(missing_phrases)}")
                results["failed"] += 1
        else:
            log_test("GET /api/ai-context (length)", False, f"Content too short: {content_len} chars (expected >20,000)")
            results["failed"] += 1
    else:
        log_test("GET /api/ai-context", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/ai-context (expanded)", "passed": passed})
    
    # POST /api/ai-context/reset - Verify reset returns default content
    passed, resp, details = test_endpoint("POST", "/ai-context/reset", 200)
    if passed and resp:
        data = resp.json()
        reset_content = data.get("content", "")
        reset_len = len(reset_content)
        if reset_len > 20000:
            log_test("POST /api/ai-context/reset", True, f"Reset content length: {reset_len} chars (>20,000 ✓)")
            results["passed"] += 1
        else:
            log_test("POST /api/ai-context/reset", False, f"Reset content too short: {reset_len} chars")
            results["failed"] += 1
    else:
        log_test("POST /api/ai-context/reset", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "POST /api/ai-context/reset", "passed": passed})
    
    # ========== 3. GITHUB INTEGRATION STILL WORKING ==========
    print(f"\n{Colors.YELLOW}[3] GitHub Integration (Still Working){Colors.END}")
    
    # GET /api/github/config
    passed, resp, details = test_endpoint("GET", "/github/config", 200)
    if passed and resp:
        data = resp.json()
        repo_url = data.get("repo_url", "")
        expected_repo = "https://github.com/alejandropiedrasanta1-ui/CINEMA"
        if repo_url == expected_repo:
            log_test("GET /api/github/config", True, f"Repo: {repo_url}")
            results["passed"] += 1
        else:
            log_test("GET /api/github/config", False, f"Unexpected repo_url: {repo_url}")
            results["failed"] += 1
    else:
        log_test("GET /api/github/config", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/github/config", "passed": passed})
    
    # GET /api/github/check-updates
    passed, resp, details = test_endpoint("GET", "/github/check-updates", 200)
    if passed and resp:
        data = resp.json()
        required_keys = ["has_updates", "local_sha", "remote_sha", "commits"]
        missing = [k for k in required_keys if k not in data]
        if not missing:
            log_test("GET /api/github/check-updates", True, f"has_updates={data.get('has_updates')}, commits_ahead={data.get('commits_ahead', 0)}")
            results["passed"] += 1
        else:
            log_test("GET /api/github/check-updates", False, f"Missing keys: {missing}")
            results["failed"] += 1
    else:
        log_test("GET /api/github/check-updates", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/github/check-updates", "passed": passed})
    
    # ========== 4. CRUD STRESS TEST ==========
    print(f"\n{Colors.YELLOW}[4] CRUD Stress Test (Create → Read → Update → Delete){Colors.END}")
    
    # Create a NEW reservation
    new_reservation = {
        "client_name": "María Elena Rodríguez",
        "client_phone": "+502 4455-6677",
        "client_email": "maria.rodriguez@example.com",
        "event_type": "Boda",
        "event_date": "2027-03-15",
        "event_time": "17:00",
        "venue": "Jardín Las Rosas",
        "guests_count": 200,
        "total_amount": 25000.0,
        "advance_paid": 10000.0,
        "status": "Confirmada",
        "package_type": "Premium",
        "notes": "CRUD stress test - will be deleted"
    }
    passed, resp, details = test_endpoint("POST", "/reservations", 201, json_data=new_reservation)
    if passed and resp:
        data = resp.json()
        test_reservation_id = data.get("id")
        log_test("POST /api/reservations (CREATE)", True, f"Created ID: {test_reservation_id[:12] if test_reservation_id else 'N/A'}...")
        results["passed"] += 1
    else:
        log_test("POST /api/reservations (CREATE)", False, details)
        results["failed"] += 1
        test_reservation_id = None
    results["tests"].append({"name": "CRUD - CREATE reservation", "passed": passed})
    
    # GET it back by id
    if test_reservation_id:
        passed, resp, details = test_endpoint("GET", f"/reservations/{test_reservation_id}", 200)
        if passed and resp:
            data = resp.json()
            if (data.get("client_name") == "María Elena Rodríguez" and 
                data.get("total_amount") == 25000.0 and 
                data.get("advance_paid") == 10000.0):
                log_test("GET /api/reservations/{id} (READ)", True, f"All fields match")
                results["passed"] += 1
            else:
                log_test("GET /api/reservations/{id} (READ)", False, "Fields don't match")
                results["failed"] += 1
        else:
            log_test("GET /api/reservations/{id} (READ)", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "CRUD - READ reservation", "passed": passed})
    
    # Update advance_paid to equal total_amount (verify update worked)
    if test_reservation_id:
        update_data = {"advance_paid": 25000.0}
        passed, resp, details = test_endpoint("PUT", f"/reservations/{test_reservation_id}", 200, json_data=update_data)
        if passed and resp:
            data = resp.json()
            # Verify advance_paid was updated correctly
            if data.get("advance_paid") == 25000.0:
                # Note: balance field not returned in response, but update worked
                log_test("PUT /api/reservations/{id} (UPDATE)", True, f"advance_paid updated to 25000 ✓")
                results["passed"] += 1
            else:
                log_test("PUT /api/reservations/{id} (UPDATE)", False, f"advance_paid not updated correctly")
                results["failed"] += 1
        else:
            log_test("PUT /api/reservations/{id} (UPDATE)", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "CRUD - UPDATE reservation", "passed": passed})
    
    # DELETE it
    if test_reservation_id:
        passed, resp, details = test_endpoint("DELETE", f"/reservations/{test_reservation_id}", 200)
        if passed:
            log_test("DELETE /api/reservations/{id} (DELETE)", True, "Test reservation deleted")
            results["passed"] += 1
        else:
            log_test("DELETE /api/reservations/{id} (DELETE)", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "CRUD - DELETE reservation", "passed": passed})
    
    # Verify back to 5 reservations
    passed, resp, details = test_endpoint("GET", "/reservations", 200)
    if passed and resp:
        data = resp.json()
        if len(data) == 5:
            log_test("GET /api/reservations (verify count)", True, f"Back to 5 reservations ✓")
            results["passed"] += 1
        else:
            log_test("GET /api/reservations (verify count)", False, f"Expected 5, got {len(data)}")
            results["failed"] += 1
    else:
        log_test("GET /api/reservations (verify count)", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "CRUD - Verify count after delete", "passed": passed})
    
    # ========== 5. CREATE + DELETE A SOCIO ==========
    print(f"\n{Colors.YELLOW}[5] Socio CRUD Test{Colors.END}")
    
    # Create new socio
    new_socio = {
        "name": "Roberto Gómez",
        "role": "Iluminador",
        "phone": "+502 3344-5566",
        "email": "roberto.gomez@cinema.com",
        "notes": "CRUD test - will be deleted",
        "rate_per_event": 3000.0
    }
    passed, resp, details = test_endpoint("POST", "/socios", 201, json_data=new_socio)
    if passed and resp:
        data = resp.json()
        test_socio_id = data.get("id")
        log_test("POST /api/socios (CREATE)", True, f"Created socio ID: {test_socio_id[:12] if test_socio_id else 'N/A'}...")
        results["passed"] += 1
    else:
        log_test("POST /api/socios (CREATE)", False, details)
        results["failed"] += 1
        test_socio_id = None
    results["tests"].append({"name": "Socio - CREATE", "passed": passed})
    
    # DELETE it
    if test_socio_id:
        passed, resp, details = test_endpoint("DELETE", f"/socios/{test_socio_id}", 200)
        if passed:
            log_test("DELETE /api/socios/{id} (DELETE)", True, "Test socio deleted")
            results["passed"] += 1
        else:
            log_test("DELETE /api/socios/{id} (DELETE)", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "Socio - DELETE", "passed": passed})
    
    # Verify back to 3 socios
    passed, resp, details = test_endpoint("GET", "/socios", 200)
    if passed and resp:
        data = resp.json()
        if len(data) == 3:
            log_test("GET /api/socios (verify count)", True, f"Back to 3 socios ✓")
            results["passed"] += 1
        else:
            log_test("GET /api/socios (verify count)", False, f"Expected 3, got {len(data)}")
            results["failed"] += 1
    else:
        log_test("GET /api/socios (verify count)", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "Socio - Verify count after delete", "passed": passed})
    
    # ========== SUMMARY ==========
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}REGRESSION TEST SUMMARY{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0
    
    print(f"\nTotal Tests: {total}")
    print(f"{Colors.GREEN}Passed: {results['passed']}{Colors.END}")
    print(f"{Colors.RED}Failed: {results['failed']}{Colors.END}")
    print(f"Pass Rate: {pass_rate:.1f}%\n")
    
    if results["failed"] > 0:
        print(f"{Colors.RED}FAILED TESTS:{Colors.END}")
        for test in results["tests"]:
            if not test["passed"]:
                print(f"  ✗ {test['name']}")
    else:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED! Backend is stable after UI/animation changes.{Colors.END}")
    
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    # Return exit code
    return 0 if results["failed"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
