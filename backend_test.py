#!/usr/bin/env python3
"""
Cinema Productions - Comprehensive Backend Testing
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
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}Cinema Productions - Backend Testing Suite{Colors.END}")
    print(f"{Colors.BLUE}Backend URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Store IDs for later tests
    test_reservation_id = None
    test_socio_id = None
    reservation_ids = []
    socio_ids = []
    
    # ========== BASIC ENDPOINTS ==========
    print(f"\n{Colors.YELLOW}[1] Basic Endpoints{Colors.END}")
    
    passed, resp, details = test_endpoint("GET", "/", 200, description="Root endpoint")
    if log_test("GET /api/", passed, details):
        results["passed"] += 1
        if resp and resp.json().get("message") == "Event Reservation API":
            print(f"      Message: {resp.json().get('message')}")
    else:
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/", "passed": passed})
    
    # ========== RESERVATIONS CRUD ==========
    print(f"\n{Colors.YELLOW}[2] Reservations CRUD{Colors.END}")
    
    # 1. GET /api/reservations - List all (should have 5 seed items)
    passed, resp, details = test_endpoint("GET", "/reservations", 200)
    if passed and resp:
        data = resp.json()
        if isinstance(data, list) and len(data) >= 5:
            reservation_ids = [r.get("id") for r in data if r.get("id")]
            log_test(f"GET /api/reservations", True, f"Found {len(data)} reservations (expected ≥5)")
            results["passed"] += 1
            # Verify required fields
            first = data[0]
            required_fields = ["id", "client_name", "event_type", "event_date", "total_amount", "advance_paid", "status"]
            missing = [f for f in required_fields if f not in first]
            if missing:
                print(f"      {Colors.RED}Missing fields: {missing}{Colors.END}")
            else:
                print(f"      All required fields present: {', '.join(required_fields[:4])}...")
        else:
            log_test("GET /api/reservations", False, f"Expected ≥5 items, got {len(data) if isinstance(data, list) else 'non-list'}")
            results["failed"] += 1
    else:
        log_test("GET /api/reservations", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/reservations", "passed": passed})
    
    # 2. GET /api/reservations/{id} - Get detail
    if reservation_ids:
        test_id = reservation_ids[0]
        passed, resp, details = test_endpoint("GET", f"/reservations/{test_id}", 200)
        if passed and resp:
            data = resp.json()
            log_test(f"GET /api/reservations/{test_id[:8]}...", True, f"Client: {data.get('client_name', 'N/A')}")
            results["passed"] += 1
        else:
            log_test(f"GET /api/reservations/{test_id[:8]}...", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "GET /api/reservations/{id}", "passed": passed})
    
    # 3. PUT /api/reservations/{id} - Update
    if reservation_ids:
        test_id = reservation_ids[0]
        update_data = {"notes": "Updated by comprehensive test"}
        passed, resp, details = test_endpoint("PUT", f"/reservations/{test_id}", 200, json_data=update_data)
        if passed and resp:
            data = resp.json()
            if data.get("notes") == "Updated by comprehensive test":
                log_test(f"PUT /api/reservations/{test_id[:8]}...", True, "Notes updated successfully")
                results["passed"] += 1
            else:
                log_test(f"PUT /api/reservations/{test_id[:8]}...", False, "Update didn't persist")
                results["failed"] += 1
        else:
            log_test(f"PUT /api/reservations/{test_id[:8]}...", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "PUT /api/reservations/{id}", "passed": passed})
    
    # 4. POST /api/reservations - Create new
    new_reservation = {
        "client_name": "Test Cliente Prueba",
        "client_phone": "+502 5555-1234",
        "client_email": "test@cinema.com",
        "event_type": "Boda",
        "event_date": "2026-12-31",
        "event_time": "18:00",
        "venue": "Salón de Pruebas",
        "guests_count": 150,
        "total_amount": 15000.0,
        "advance_paid": 5000.0,
        "status": "Confirmada",
        "package_type": "Completo",
        "notes": "Reserva de prueba - eliminar después"
    }
    passed, resp, details = test_endpoint("POST", "/reservations", 201, json_data=new_reservation)
    if passed and resp:
        data = resp.json()
        test_reservation_id = data.get("id")
        log_test("POST /api/reservations", True, f"Created reservation ID: {test_reservation_id[:8] if test_reservation_id else 'N/A'}...")
        results["passed"] += 1
    else:
        log_test("POST /api/reservations", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "POST /api/reservations", "passed": passed})
    
    # 5. DELETE /api/reservations/{id} - Delete the test reservation
    if test_reservation_id:
        passed, resp, details = test_endpoint("DELETE", f"/reservations/{test_reservation_id}", 200)
        if passed:
            log_test(f"DELETE /api/reservations/{test_reservation_id[:8]}...", True, "Test reservation deleted")
            results["passed"] += 1
        else:
            log_test(f"DELETE /api/reservations/{test_reservation_id[:8]}...", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "DELETE /api/reservations/{id}", "passed": passed})
    
    # ========== SOCIOS CRUD ==========
    print(f"\n{Colors.YELLOW}[3] Socios CRUD{Colors.END}")
    
    # 6. GET /api/socios - List all (should have 3 seed items)
    passed, resp, details = test_endpoint("GET", "/socios", 200)
    if passed and resp:
        data = resp.json()
        if isinstance(data, list) and len(data) >= 3:
            socio_ids = [s.get("id") for s in data if s.get("id")]
            log_test(f"GET /api/socios", True, f"Found {len(data)} socios (expected ≥3)")
            results["passed"] += 1
            print(f"      Socios: {', '.join([s.get('name', 'N/A') for s in data[:3]])}")
        else:
            log_test("GET /api/socios", False, f"Expected ≥3 items, got {len(data) if isinstance(data, list) else 'non-list'}")
            results["failed"] += 1
    else:
        log_test("GET /api/socios", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/socios", "passed": passed})
    
    # 7. PUT /api/socios/{id} - Update
    if socio_ids:
        test_id = socio_ids[0]
        update_data = {"notes": "Updated by test"}
        passed, resp, details = test_endpoint("PUT", f"/socios/{test_id}", 200, json_data=update_data)
        if passed:
            log_test(f"PUT /api/socios/{test_id[:8]}...", True, "Socio updated")
            results["passed"] += 1
        else:
            log_test(f"PUT /api/socios/{test_id[:8]}...", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "PUT /api/socios/{id}", "passed": passed})
    
    # 8. POST /api/socios - Create new
    new_socio = {
        "name": "Test Socio Prueba",
        "role": "Fotógrafo",
        "phone": "+502 5555-9999",
        "email": "testsocio@cinema.com",
        "notes": "Socio de prueba - eliminar",
        "rate_per_event": 2500.0
    }
    passed, resp, details = test_endpoint("POST", "/socios", 201, json_data=new_socio)
    if passed and resp:
        data = resp.json()
        test_socio_id = data.get("id")
        log_test("POST /api/socios", True, f"Created socio ID: {test_socio_id[:8] if test_socio_id else 'N/A'}...")
        results["passed"] += 1
    else:
        log_test("POST /api/socios", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "POST /api/socios", "passed": passed})
    
    # 9. DELETE /api/socios/{id}
    if test_socio_id:
        passed, resp, details = test_endpoint("DELETE", f"/socios/{test_socio_id}", 200)
        if passed:
            log_test(f"DELETE /api/socios/{test_socio_id[:8]}...", True, "Test socio deleted")
            results["passed"] += 1
        else:
            log_test(f"DELETE /api/socios/{test_socio_id[:8]}...", False, details)
            results["failed"] += 1
        results["tests"].append({"name": "DELETE /api/socios/{id}", "passed": passed})
    
    # ========== AGGREGATE ENDPOINTS ==========
    print(f"\n{Colors.YELLOW}[4] Stats & Aggregate Endpoints{Colors.END}")
    
    # 10. GET /api/stats
    passed, resp, details = test_endpoint("GET", "/stats", 200)
    if passed and resp:
        data = resp.json()
        required_keys = ["total_reservations", "upcoming_events", "pending_payment", "real_income"]
        missing = [k for k in required_keys if k not in data]
        if not missing:
            log_test("GET /api/stats", True, f"total_reservations={data.get('total_reservations')}, upcoming={data.get('upcoming_events')}")
            results["passed"] += 1
        else:
            log_test("GET /api/stats", False, f"Missing keys: {missing}")
            results["failed"] += 1
    else:
        log_test("GET /api/stats", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/stats", "passed": passed})
    
    # 11. GET /api/calendar
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
    results["tests"].append({"name": "GET /api/calendar", "passed": passed})
    
    # 12. GET /api/financials
    passed, resp, details = test_endpoint("GET", "/financials", 200)
    if passed and resp:
        data = resp.json()
        log_test("GET /api/financials", True, f"real_income={data.get('real_income', 'N/A')}")
        results["passed"] += 1
    else:
        log_test("GET /api/financials", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/financials", "passed": passed})
    
    # 13. GET /api/export/reservations (CSV)
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
    results["tests"].append({"name": "GET /api/export/reservations", "passed": passed})
    
    # 14. GET /api/settings
    passed, resp, details = test_endpoint("GET", "/settings", 200)
    if passed:
        log_test("GET /api/settings", True, "Settings retrieved")
        results["passed"] += 1
    else:
        log_test("GET /api/settings", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/settings", "passed": passed})
    
    # 15. GET /api/backup/history
    passed, resp, details = test_endpoint("GET", "/backup/history", 200)
    if passed and resp:
        data = resp.json()
        log_test("GET /api/backup/history", True, f"Found {len(data) if isinstance(data, list) else 0} backups")
        results["passed"] += 1
    else:
        log_test("GET /api/backup/history", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/backup/history", "passed": passed})
    
    # 16. GET /api/notifications/pending
    passed, resp, details = test_endpoint("GET", "/notifications/pending", 200)
    if passed:
        log_test("GET /api/notifications/pending", True, "Notifications endpoint working")
        results["passed"] += 1
    else:
        log_test("GET /api/notifications/pending", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/notifications/pending", "passed": passed})
    
    # ========== AI CONTEXT ==========
    print(f"\n{Colors.YELLOW}[5] AI Context (Expanded){Colors.END}")
    
    # 17. GET /api/ai-context - Should be >15k chars
    passed, resp, details = test_endpoint("GET", "/ai-context", 200)
    if passed and resp:
        data = resp.json()
        content = data.get("content", "")
        content_len = len(content)
        if content_len > 15000:
            # Check for specific phrases
            has_cinema = "Cinema Productions" in content
            has_historial = "Historial de Sesiones" in content or "Historial" in content
            has_github = "GitHub Integration" in content or "GitHub" in content
            
            if has_cinema and has_github:
                log_test("GET /api/ai-context", True, f"Content length: {content_len} chars (>15k ✓)")
                print(f"      Contains: Cinema Productions ✓, GitHub Integration ✓")
                results["passed"] += 1
            else:
                log_test("GET /api/ai-context", False, f"Missing expected phrases (Cinema={has_cinema}, GitHub={has_github})")
                results["failed"] += 1
        else:
            log_test("GET /api/ai-context", False, f"Content too short: {content_len} chars (expected >15000)")
            results["failed"] += 1
    else:
        log_test("GET /api/ai-context", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/ai-context (>15k chars)", "passed": passed})
    
    # ========== GITHUB INTEGRATION ==========
    print(f"\n{Colors.YELLOW}[6] GitHub Integration{Colors.END}")
    
    # 18. GET /api/github/config
    passed, resp, details = test_endpoint("GET", "/github/config", 200)
    if passed and resp:
        data = resp.json()
        repo_url = data.get("repo_url", "")
        expected_repo = "https://github.com/alejandropiedrasanta1-ui/CINEMA"
        if repo_url == expected_repo:
            log_test("GET /api/github/config", True, f"Repo: {repo_url}")
            results["passed"] += 1
        else:
            log_test("GET /api/github/config", False, f"Unexpected repo_url: {repo_url} (expected {expected_repo})")
            results["failed"] += 1
    else:
        log_test("GET /api/github/config", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/github/config", "passed": passed})
    
    # 19. GET /api/github/check-updates
    passed, resp, details = test_endpoint("GET", "/github/check-updates", 200)
    if passed and resp:
        data = resp.json()
        required_keys = ["has_updates", "local_sha", "remote_sha", "commits_ahead", "commits", "branch"]
        missing = [k for k in required_keys if k not in data]
        if not missing:
            log_test("GET /api/github/check-updates", True, f"has_updates={data.get('has_updates')}, commits_ahead={data.get('commits_ahead')}")
            results["passed"] += 1
        else:
            log_test("GET /api/github/check-updates", False, f"Missing keys: {missing}")
            results["failed"] += 1
    else:
        log_test("GET /api/github/check-updates", False, details)
        results["failed"] += 1
    results["tests"].append({"name": "GET /api/github/check-updates", "passed": passed})
    
    # ========== VERIFY SEED DATA STILL EXISTS ==========
    print(f"\n{Colors.YELLOW}[7] Verify Seed Data Integrity{Colors.END}")
    
    # Verify 5 reservations still exist
    passed, resp, details = test_endpoint("GET", "/reservations", 200)
    if passed and resp:
        data = resp.json()
        count = len([r for r in data if r.get("id") in reservation_ids])
        if count >= 5:
            log_test("Seed reservations intact", True, f"All {count} seed reservations still exist")
            results["passed"] += 1
        else:
            log_test("Seed reservations intact", False, f"Only {count}/5 seed reservations found")
            results["failed"] += 1
    else:
        log_test("Seed reservations intact", False, "Could not verify")
        results["failed"] += 1
    results["tests"].append({"name": "Seed reservations intact", "passed": passed})
    
    # Verify 3 socios still exist
    passed, resp, details = test_endpoint("GET", "/socios", 200)
    if passed and resp:
        data = resp.json()
        count = len([s for s in data if s.get("id") in socio_ids])
        if count >= 3:
            log_test("Seed socios intact", True, f"All {count} seed socios still exist")
            results["passed"] += 1
        else:
            log_test("Seed socios intact", False, f"Only {count}/3 seed socios found")
            results["failed"] += 1
    else:
        log_test("Seed socios intact", False, "Could not verify")
        results["failed"] += 1
    results["tests"].append({"name": "Seed socios intact", "passed": passed})
    
    # ========== SUMMARY ==========
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}")
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
                print(f"  - {test['name']}")
    
    print(f"\n{Colors.BLUE}{'='*70}{Colors.END}\n")
    
    # Return exit code
    return 0 if results["failed"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
