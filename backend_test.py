#!/usr/bin/env python3
"""
Backend Testing for Cinema Productions - Advanced Security Endpoints
Tests new security features + regression check
"""

import requests
import time
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://4c46c59f-58b0-4e2f-a739-f1c96f46602f.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_test(name, passed, expected=None, actual=None, details=None):
    """Log test result with color coding"""
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{status} | {name}")
    if not passed:
        if expected is not None:
            print(f"  Expected: {expected}")
        if actual is not None:
            print(f"  Actual: {actual}")
        if details:
            print(f"  Details: {details}")
    return passed

def test_extended_security_status():
    """Test 1: Extended GET /api/security/status with all new fields"""
    print(f"\n{Colors.BLUE}=== TEST 1: Extended GET /api/security/status ==={Colors.RESET}")
    
    try:
        r = requests.get(f"{BASE_URL}/security/status", timeout=10)
        
        if not log_test("Status code 200", r.status_code == 200, 200, r.status_code):
            return False
        
        data = r.json()
        required_fields = [
            "password_enabled", "hint", "protection_enabled",
            "auto_lock_enabled", "auto_lock_minutes", "max_attempts",
            "lockout_seconds", "protected_sections", "failed_attempts", "locked_until"
        ]
        
        all_present = True
        for field in required_fields:
            if field not in data:
                log_test(f"Field '{field}' present", False, "present", "missing")
                all_present = False
        
        if all_present:
            log_test("All required fields present", True)
            print(f"  Fields: {list(data.keys())}")
            
            # Verify types
            log_test("password_enabled is bool", isinstance(data["password_enabled"], bool))
            log_test("hint is str", isinstance(data["hint"], str))
            log_test("protection_enabled is bool", isinstance(data["protection_enabled"], bool))
            log_test("auto_lock_enabled is bool", isinstance(data["auto_lock_enabled"], bool))
            log_test("auto_lock_minutes is int", isinstance(data["auto_lock_minutes"], int))
            log_test("max_attempts is int", isinstance(data["max_attempts"], int))
            log_test("lockout_seconds is int", isinstance(data["lockout_seconds"], int))
            log_test("protected_sections is list", isinstance(data["protected_sections"], list))
            log_test("failed_attempts is int", isinstance(data["failed_attempts"], int))
            log_test("locked_until is str", isinstance(data["locked_until"], str))
        
        return all_present
    except Exception as e:
        log_test("GET /api/security/status", False, details=str(e))
        return False

def test_advanced_config_valid():
    """Test 2: PUT /api/security/advanced-config with valid config"""
    print(f"\n{Colors.BLUE}=== TEST 2: PUT /api/security/advanced-config (valid) ==={Colors.RESET}")
    
    try:
        payload = {
            "auto_lock_enabled": True,
            "auto_lock_minutes": 5,
            "max_attempts": 5,
            "lockout_seconds": 30,
            "protected_sections": ["/base-de-datos", "/ajustes"]
        }
        
        r = requests.put(f"{BASE_URL}/security/advanced-config", json=payload, timeout=10)
        
        if not log_test("Status code 200", r.status_code == 200, 200, r.status_code):
            return False
        
        data = r.json()
        if not log_test("Response has 'success' key", "success" in data):
            return False
        
        if not log_test("success is True", data.get("success") == True, True, data.get("success")):
            return False
        
        # Verify changes reflected in GET
        r2 = requests.get(f"{BASE_URL}/security/status", timeout=10)
        status = r2.json()
        
        log_test("auto_lock_enabled = True", status.get("auto_lock_enabled") == True)
        log_test("auto_lock_minutes = 5", status.get("auto_lock_minutes") == 5)
        log_test("max_attempts = 5", status.get("max_attempts") == 5)
        log_test("lockout_seconds = 30", status.get("lockout_seconds") == 30)
        log_test("protected_sections correct", 
                 set(status.get("protected_sections", [])) == {"/base-de-datos", "/ajustes"})
        
        return True
    except Exception as e:
        log_test("PUT /api/security/advanced-config (valid)", False, details=str(e))
        return False

def test_advanced_config_invalid_ranges():
    """Test 3: PUT /api/security/advanced-config with invalid ranges"""
    print(f"\n{Colors.BLUE}=== TEST 3: PUT /api/security/advanced-config (invalid ranges) ==={Colors.RESET}")
    
    test_cases = [
        ({"auto_lock_minutes": 0}, "auto_lock_minutes=0 (min=1)"),
        ({"auto_lock_minutes": 200}, "auto_lock_minutes=200 (max=120)"),
        ({"max_attempts": 1}, "max_attempts=1 (min=3)"),
        ({"max_attempts": 25}, "max_attempts=25 (max=20)"),
        ({"lockout_seconds": 5}, "lockout_seconds=5 (min=10)"),
        ({"lockout_seconds": 4000}, "lockout_seconds=4000 (max=3600)"),
    ]
    
    all_passed = True
    for payload, description in test_cases:
        try:
            r = requests.put(f"{BASE_URL}/security/advanced-config", json=payload, timeout=10)
            passed = log_test(f"400 for {description}", r.status_code == 400, 400, r.status_code)
            if not passed:
                all_passed = False
        except Exception as e:
            log_test(f"400 for {description}", False, details=str(e))
            all_passed = False
    
    return all_passed

def test_advanced_config_invalid_sections():
    """Test 4: Invalid protected_sections paths should be filtered"""
    print(f"\n{Colors.BLUE}=== TEST 4: Invalid protected_sections filtering ==={Colors.RESET}")
    
    try:
        payload = {
            "protected_sections": ["/base-de-datos", "/hackerpath", "/ajustes", "/invalid"]
        }
        
        r = requests.put(f"{BASE_URL}/security/advanced-config", json=payload, timeout=10)
        
        if not log_test("Status code 200 (not error)", r.status_code == 200, 200, r.status_code):
            return False
        
        # Check that only valid paths are saved
        r2 = requests.get(f"{BASE_URL}/security/status", timeout=10)
        status = r2.json()
        sections = status.get("protected_sections", [])
        
        valid_only = "/hackerpath" not in sections and "/invalid" not in sections
        has_valid = "/base-de-datos" in sections and "/ajustes" in sections
        
        log_test("Invalid paths filtered out", valid_only, 
                 "no /hackerpath or /invalid", sections)
        log_test("Valid paths preserved", has_valid,
                 "/base-de-datos and /ajustes present", sections)
        
        return valid_only and has_valid
    except Exception as e:
        log_test("Invalid sections filtering", False, details=str(e))
        return False

def test_partial_update():
    """Test 5: Partial update (only one field)"""
    print(f"\n{Colors.BLUE}=== TEST 5: Partial update (auto_lock_enabled only) ==={Colors.RESET}")
    
    try:
        # Get current state
        r1 = requests.get(f"{BASE_URL}/security/status", timeout=10)
        before = r1.json()
        
        # Update only auto_lock_enabled
        payload = {"auto_lock_enabled": False}
        r2 = requests.put(f"{BASE_URL}/security/advanced-config", json=payload, timeout=10)
        
        if not log_test("Status code 200", r2.status_code == 200, 200, r2.status_code):
            return False
        
        # Verify only that field changed
        r3 = requests.get(f"{BASE_URL}/security/status", timeout=10)
        after = r3.json()
        
        log_test("auto_lock_enabled changed to False", after["auto_lock_enabled"] == False)
        log_test("max_attempts unchanged", after["max_attempts"] == before["max_attempts"])
        log_test("lockout_seconds unchanged", after["lockout_seconds"] == before["lockout_seconds"])
        
        return True
    except Exception as e:
        log_test("Partial update", False, details=str(e))
        return False

def test_failed_attempts_flow():
    """Test 6: CRITICAL - Failed attempts flow with lockout"""
    print(f"\n{Colors.BLUE}=== TEST 6: CRITICAL - Failed attempts flow ==={Colors.RESET}")
    
    try:
        # Step a: Set password
        print(f"{Colors.YELLOW}Step a: Setting password 'test1234'{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/set-password", 
                         json={"password": "test1234", "hint": "test hint"}, timeout=10)
        if not log_test("Set password → 200", r.status_code == 200, 200, r.status_code):
            return False
        
        # Step b: Configure max_attempts=3, lockout_seconds=15
        print(f"{Colors.YELLOW}Step b: Configuring max_attempts=3, lockout_seconds=15{Colors.RESET}")
        r = requests.put(f"{BASE_URL}/security/advanced-config",
                        json={"max_attempts": 3, "lockout_seconds": 15}, timeout=10)
        if not log_test("Configure limits → 200", r.status_code == 200, 200, r.status_code):
            return False
        
        # Step c: First wrong attempt
        print(f"{Colors.YELLOW}Step c: First wrong attempt{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/verify", 
                         json={"password": "wrongpass"}, timeout=10)
        passed_c = log_test("Wrong password #1 → 401", r.status_code == 401, 401, r.status_code)
        if passed_c:
            detail = r.json().get("detail", "")
            log_test("Message contains 'Te quedan 2 intento'", "Te quedan 2 intento" in detail,
                    "contains 'Te quedan 2 intento'", detail)
        
        # Step d: Second wrong attempt
        print(f"{Colors.YELLOW}Step d: Second wrong attempt{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/verify", 
                         json={"password": "wrongpass"}, timeout=10)
        passed_d = log_test("Wrong password #2 → 401", r.status_code == 401, 401, r.status_code)
        if passed_d:
            detail = r.json().get("detail", "")
            log_test("Message contains 'Te quedan 1 intento'", "Te quedan 1 intento" in detail,
                    "contains 'Te quedan 1 intento'", detail)
        
        # Step e: Third wrong attempt (should trigger lockout)
        print(f"{Colors.YELLOW}Step e: Third wrong attempt (trigger lockout){Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/verify", 
                         json={"password": "wrongpass"}, timeout=10)
        passed_e = log_test("Wrong password #3 → 429", r.status_code == 429, 429, r.status_code)
        if passed_e:
            detail = r.json().get("detail", "")
            log_test("Message contains 'Bloqueado' or 'Demasiados'", 
                    "Bloqueado" in detail or "Demasiados" in detail,
                    "contains lockout message", detail)
        
        # Step f: Try correct password while locked
        print(f"{Colors.YELLOW}Step f: Try correct password while locked{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/verify", 
                         json={"password": "test1234"}, timeout=10)
        passed_f = log_test("Correct password while locked → 429", r.status_code == 429, 429, r.status_code)
        if passed_f and "Retry-After" in r.headers:
            log_test("Retry-After header present", True)
            print(f"  Retry-After: {r.headers['Retry-After']} seconds")
        
        # Step g: Verify locked_until is set
        print(f"{Colors.YELLOW}Step g: Verify locked_until in status{Colors.RESET}")
        r = requests.get(f"{BASE_URL}/security/status", timeout=10)
        status = r.json()
        locked_until = status.get("locked_until", "")
        
        if log_test("locked_until is not empty", locked_until != "", "non-empty", locked_until):
            try:
                # Parse ISO timestamp
                locked_dt = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
                now = datetime.now(locked_dt.tzinfo)
                is_future = locked_dt > now
                log_test("locked_until is future timestamp", is_future,
                        "future time", f"locked_until={locked_until}")
            except Exception as e:
                log_test("locked_until is valid ISO timestamp", False, details=str(e))
        
        # Step h: Wait for lockout to expire
        print(f"{Colors.YELLOW}Step h: Waiting ~16 seconds for lockout to expire...{Colors.RESET}")
        time.sleep(16)
        
        # Step i: Try correct password after lockout expires
        print(f"{Colors.YELLOW}Step i: Try correct password after lockout{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/verify", 
                         json={"password": "test1234"}, timeout=10)
        passed_i = log_test("Correct password after lockout → 200", r.status_code == 200, 200, r.status_code)
        if passed_i:
            data = r.json()
            log_test("Response has valid=True", data.get("valid") == True, True, data.get("valid"))
        
        # Step j: Verify failed_attempts reset
        print(f"{Colors.YELLOW}Step j: Verify failed_attempts reset to 0{Colors.RESET}")
        r = requests.get(f"{BASE_URL}/security/status", timeout=10)
        status = r.json()
        log_test("failed_attempts = 0", status.get("failed_attempts") == 0, 0, status.get("failed_attempts"))
        log_test("locked_until is empty", status.get("locked_until") == "", "", status.get("locked_until"))
        
        # Step k: CLEANUP - Remove password
        print(f"{Colors.YELLOW}Step k: CLEANUP - Removing password{Colors.RESET}")
        r = requests.post(f"{BASE_URL}/security/remove-password",
                         json={"current_password": "test1234"}, timeout=10)
        log_test("Remove password → 200", r.status_code == 200, 200, r.status_code)
        
        return True
    except Exception as e:
        log_test("Failed attempts flow", False, details=str(e))
        # Try cleanup even if test failed
        try:
            print(f"{Colors.YELLOW}Attempting cleanup after error...{Colors.RESET}")
            requests.post(f"{BASE_URL}/security/remove-password",
                         json={"current_password": "test1234"}, timeout=10)
        except:
            pass
        return False

def test_regression_endpoints():
    """Test 7: Regression - Existing endpoints still work"""
    print(f"\n{Colors.BLUE}=== TEST 7: Regression - Existing endpoints ==={Colors.RESET}")
    
    tests_passed = []
    
    # GET /api/
    try:
        r = requests.get(f"{BASE_URL}/", timeout=10)
        passed = log_test("GET /api/ → 200", r.status_code == 200, 200, r.status_code)
        if passed:
            data = r.json()
            log_test("Response contains 'Event Reservation API'", 
                    "Event Reservation API" in str(data),
                    "contains message", data)
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/", False, details=str(e))
        tests_passed.append(False)
    
    # GET /api/reservations
    try:
        r = requests.get(f"{BASE_URL}/reservations", timeout=10)
        passed = log_test("GET /api/reservations → 200", r.status_code == 200, 200, r.status_code)
        if passed:
            data = r.json()
            count = len(data)
            # Should be 5 seed items (or 6 if test reservation exists)
            log_test(f"Reservations count = {count} (expected 5 or 6)", 
                    count >= 5 and count <= 6, "5 or 6", count)
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/reservations", False, details=str(e))
        tests_passed.append(False)
    
    # GET /api/socios
    try:
        r = requests.get(f"{BASE_URL}/socios", timeout=10)
        passed = log_test("GET /api/socios → 200", r.status_code == 200, 200, r.status_code)
        if passed:
            data = r.json()
            count = len(data)
            log_test(f"Socios count = {count} (expected 3)", count == 3, 3, count)
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/socios", False, details=str(e))
        tests_passed.append(False)
    
    # GET /api/stats
    try:
        r = requests.get(f"{BASE_URL}/stats", timeout=10)
        passed = log_test("GET /api/stats → 200", r.status_code == 200, 200, r.status_code)
        if passed:
            data = r.json()
            required = ["total_reservations", "upcoming_events", "real_income"]
            all_present = all(k in data for k in required)
            log_test("Stats has required fields", all_present, required, list(data.keys()))
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/stats", False, details=str(e))
        tests_passed.append(False)
    
    # GET /api/github/config
    try:
        r = requests.get(f"{BASE_URL}/github/config", timeout=10)
        passed = log_test("GET /api/github/config → 200", r.status_code == 200, 200, r.status_code)
        if passed:
            data = r.json()
            repo_url = data.get("repo_url", "")
            log_test("repo_url = 'https://github.com/alejandropiedrasanta1-ui/CINEMA'",
                    repo_url == "https://github.com/alejandropiedrasanta1-ui/CINEMA",
                    "correct URL", repo_url)
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/github/config", False, details=str(e))
        tests_passed.append(False)
    
    # GET /api/github/check-updates
    try:
        r = requests.get(f"{BASE_URL}/github/check-updates", timeout=10)
        passed = log_test("GET /api/github/check-updates → 200", r.status_code == 200, 200, r.status_code)
        tests_passed.append(passed)
    except Exception as e:
        log_test("GET /api/github/check-updates", False, details=str(e))
        tests_passed.append(False)
    
    return all(tests_passed)

def test_ai_context_expanded():
    """Test 8: AI Context is > 22,000 chars with required phrases"""
    print(f"\n{Colors.BLUE}=== TEST 8: AI Context expanded (>22k chars) ==={Colors.RESET}")
    
    try:
        r = requests.get(f"{BASE_URL}/ai-context", timeout=10)
        
        if not log_test("GET /api/ai-context → 200", r.status_code == 200, 200, r.status_code):
            return False
        
        data = r.json()
        content = data.get("content", "")
        length = len(content)
        
        log_test(f"Content length > 22,000 chars", length > 22000, ">22000", length)
        
        # Check for required phrases
        required_phrases = [
            "SI AGREGA LAS FUNCIONES DE SEGURIDAD",
            "auto-lock",
            "useAdvancedSecurity",
            "SectionUnlockModal",
            "advanced-config"
        ]
        
        for phrase in required_phrases:
            found = phrase in content
            log_test(f"Contains '{phrase}'", found, "present", "missing" if not found else "present")
        
        return length > 22000
    except Exception as e:
        log_test("GET /api/ai-context", False, details=str(e))
        return False

def main():
    """Run all tests"""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BLUE}Cinema Productions - Backend Testing (Advanced Security){Colors.RESET}")
    print(f"{Colors.BLUE}Backend URL: {BASE_URL}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*70}{Colors.RESET}")
    
    results = []
    
    # Run all tests
    results.append(("Extended security status", test_extended_security_status()))
    results.append(("Advanced config (valid)", test_advanced_config_valid()))
    results.append(("Advanced config (invalid ranges)", test_advanced_config_invalid_ranges()))
    results.append(("Invalid sections filtering", test_advanced_config_invalid_sections()))
    results.append(("Partial update", test_partial_update()))
    results.append(("CRITICAL: Failed attempts flow", test_failed_attempts_flow()))
    results.append(("Regression endpoints", test_regression_endpoints()))
    results.append(("AI Context expanded", test_ai_context_expanded()))
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*70}{Colors.RESET}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if result else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"{status} | {name}")
    
    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed ({passed/total*100:.1f}%){Colors.RESET}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED!{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}❌ SOME TESTS FAILED{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
