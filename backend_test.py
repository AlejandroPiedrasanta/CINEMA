#!/usr/bin/env python3
"""
Backend API Testing for Cinema Productions - GitHub Integration & AI Context
Tests the newly added GitHub Integration and AI Context endpoints.
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL - using localhost since external URL has routing issues
# External URL: https://event-reserve-pro-5.preview.emergentagent.com/api (returns 404)
# Using localhost for testing backend functionality
BASE_URL = "http://localhost:8001/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}


def log_test(name, passed, message="", details=None):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {name}")
    if message:
        print(f"  → {message}")
    if details:
        print(f"  Details: {json.dumps(details, indent=2)}")
    
    if passed:
        test_results["passed"].append(name)
    else:
        test_results["failed"].append({"name": name, "message": message, "details": details})


def test_root_endpoint():
    """Test GET /api/"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "message" in data and "Event Reservation API" in data["message"]:
                log_test("GET /api/", True, f"Response: {data}")
                return True
            else:
                log_test("GET /api/", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("GET /api/", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("GET /api/", False, f"Exception: {str(e)}")
        return False


def test_stats_endpoint():
    """Test GET /api/stats"""
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_keys = ["total_reservations", "upcoming_events", "pending_payment", "real_income"]
            if all(key in data for key in required_keys):
                log_test("GET /api/stats", True, f"Stats retrieved successfully")
                return True
            else:
                log_test("GET /api/stats", False, f"Missing required keys. Got: {list(data.keys())}")
                return False
        else:
            log_test("GET /api/stats", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("GET /api/stats", False, f"Exception: {str(e)}")
        return False


def test_settings_endpoint():
    """Test GET /api/settings"""
    try:
        response = requests.get(f"{BASE_URL}/settings", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/settings", True, f"Settings retrieved successfully")
            return True
        else:
            log_test("GET /api/settings", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("GET /api/settings", False, f"Exception: {str(e)}")
        return False


def test_github_config_get():
    """Test GET /api/github/config"""
    try:
        response = requests.get(f"{BASE_URL}/github/config", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_keys = ["repo_url", "has_token", "last_commit_sha", "last_check_at", "branch"]
            if all(key in data for key in required_keys):
                log_test("GET /api/github/config", True, f"Config retrieved with keys: {list(data.keys())}")
                return True, data
            else:
                log_test("GET /api/github/config", False, f"Missing required keys. Got: {list(data.keys())}")
                return False, None
        else:
            log_test("GET /api/github/config", False, f"Status {response.status_code}: {response.text[:200]}")
            return False, None
    except Exception as e:
        log_test("GET /api/github/config", False, f"Exception: {str(e)}")
        return False, None


def test_github_config_post_valid():
    """Test POST /api/github/config with valid URL"""
    try:
        payload = {
            "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
            "branch": "main"
        }
        response = requests.post(f"{BASE_URL}/github/config", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("repo_url") == payload["repo_url"]:
                log_test("POST /api/github/config (valid URL)", True, f"Config saved successfully")
                return True
            else:
                log_test("POST /api/github/config (valid URL)", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("POST /api/github/config (valid URL)", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("POST /api/github/config (valid URL)", False, f"Exception: {str(e)}")
        return False


def test_github_config_post_invalid():
    """Test POST /api/github/config with invalid URL"""
    try:
        payload = {
            "repo_url": "not-a-url",
            "branch": "main"
        }
        response = requests.post(f"{BASE_URL}/github/config", json=payload, timeout=10)
        if response.status_code == 400:
            log_test("POST /api/github/config (invalid URL)", True, f"Correctly rejected invalid URL with 400")
            return True
        else:
            log_test("POST /api/github/config (invalid URL)", False, f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        log_test("POST /api/github/config (invalid URL)", False, f"Exception: {str(e)}")
        return False


def test_github_config_post_with_token():
    """Test POST /api/github/config with token"""
    try:
        payload = {
            "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
            "token": "test_token_123",
            "branch": "main"
        }
        response = requests.post(f"{BASE_URL}/github/config", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # Now verify GET doesn't expose the token
                get_response = requests.get(f"{BASE_URL}/github/config", timeout=10)
                if get_response.status_code == 200:
                    get_data = get_response.json()
                    if get_data.get("has_token") == True and "token" not in get_data:
                        log_test("POST /api/github/config (with token)", True, f"Token saved and not exposed in GET")
                        return True
                    else:
                        log_test("POST /api/github/config (with token)", False, f"Token handling issue: {get_data}")
                        return False
                else:
                    log_test("POST /api/github/config (with token)", False, f"GET failed after POST")
                    return False
            else:
                log_test("POST /api/github/config (with token)", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("POST /api/github/config (with token)", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("POST /api/github/config (with token)", False, f"Exception: {str(e)}")
        return False


def test_github_check_updates():
    """Test GET /api/github/check-updates"""
    try:
        # First, ensure we have a valid repo configured without a token (public repo)
        config_payload = {
            "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
            "branch": "main",
            "clear_token": True
        }
        requests.post(f"{BASE_URL}/github/config", json=config_payload, timeout=10)
        
        # Now check for updates
        response = requests.get(f"{BASE_URL}/github/check-updates", timeout=15)
        if response.status_code == 200:
            data = response.json()
            required_keys = ["has_updates", "local_sha", "local_sha_short", "remote_sha", 
                           "remote_sha_short", "branch", "commits_ahead", "commits", "repo_url"]
            if all(key in data for key in required_keys):
                log_test("GET /api/github/check-updates", True, 
                        f"Updates checked: has_updates={data['has_updates']}, commits_ahead={data['commits_ahead']}")
                return True
            else:
                log_test("GET /api/github/check-updates", False, f"Missing required keys. Got: {list(data.keys())}")
                return False
        else:
            log_test("GET /api/github/check-updates", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("GET /api/github/check-updates", False, f"Exception: {str(e)}")
        return False


def test_github_check_updates_no_repo():
    """Test GET /api/github/check-updates without repo configured"""
    try:
        # First, clear the repo config
        clear_payload = {"repo_url": "", "branch": "main"}
        requests.post(f"{BASE_URL}/github/config", json=clear_payload, timeout=10)
        
        # Now try to check updates
        response = requests.get(f"{BASE_URL}/github/check-updates", timeout=10)
        if response.status_code == 400:
            log_test("GET /api/github/check-updates (no repo)", True, f"Correctly returned 400 when no repo configured")
            # Restore the repo config
            restore_payload = {
                "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
                "branch": "main"
            }
            requests.post(f"{BASE_URL}/github/config", json=restore_payload, timeout=10)
            return True
        else:
            log_test("GET /api/github/check-updates (no repo)", False, f"Expected 400, got {response.status_code}")
            # Restore the repo config
            restore_payload = {
                "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
                "branch": "main"
            }
            requests.post(f"{BASE_URL}/github/config", json=restore_payload, timeout=10)
            return False
    except Exception as e:
        log_test("GET /api/github/check-updates (no repo)", False, f"Exception: {str(e)}")
        return False


def test_ai_context_get():
    """Test GET /api/ai-context"""
    try:
        response = requests.get(f"{BASE_URL}/ai-context", timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_keys = ["content", "updated_at"]
            if all(key in data for key in required_keys):
                content = data.get("content", "")
                if len(content) >= 3000 and "Cinema Productions" in content:
                    log_test("GET /api/ai-context", True, 
                            f"Context retrieved: {len(content)} chars, contains 'Cinema Productions'")
                    return True, data
                else:
                    log_test("GET /api/ai-context", False, 
                            f"Content too short ({len(content)} chars) or missing 'Cinema Productions'")
                    return False, None
            else:
                log_test("GET /api/ai-context", False, f"Missing required keys. Got: {list(data.keys())}")
                return False, None
        else:
            log_test("GET /api/ai-context", False, f"Status {response.status_code}: {response.text[:200]}")
            return False, None
    except Exception as e:
        log_test("GET /api/ai-context", False, f"Exception: {str(e)}")
        return False, None


def test_ai_context_post():
    """Test POST /api/ai-context"""
    try:
        test_content = "# Test Content Custom\n\nThis is a test context for Cinema Productions."
        payload = {"content": test_content}
        response = requests.post(f"{BASE_URL}/ai-context", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "updated_at" in data:
                # Verify the content was saved
                get_response = requests.get(f"{BASE_URL}/ai-context", timeout=10)
                if get_response.status_code == 200:
                    get_data = get_response.json()
                    if get_data.get("content") == test_content:
                        log_test("POST /api/ai-context", True, f"Content saved and verified")
                        return True
                    else:
                        log_test("POST /api/ai-context", False, f"Content mismatch after save")
                        return False
                else:
                    log_test("POST /api/ai-context", False, f"GET failed after POST")
                    return False
            else:
                log_test("POST /api/ai-context", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("POST /api/ai-context", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("POST /api/ai-context", False, f"Exception: {str(e)}")
        return False


def test_ai_context_reset():
    """Test POST /api/ai-context/reset"""
    try:
        response = requests.post(f"{BASE_URL}/ai-context/reset", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "content" in data:
                # Verify the content was reset to default
                get_response = requests.get(f"{BASE_URL}/ai-context", timeout=10)
                if get_response.status_code == 200:
                    get_data = get_response.json()
                    content = get_data.get("content", "")
                    if len(content) >= 3000 and "Cinema Productions" in content:
                        log_test("POST /api/ai-context/reset", True, 
                                f"Context reset to default: {len(content)} chars")
                        return True
                    else:
                        log_test("POST /api/ai-context/reset", False, 
                                f"Reset content invalid: {len(content)} chars")
                        return False
                else:
                    log_test("POST /api/ai-context/reset", False, f"GET failed after reset")
                    return False
            else:
                log_test("POST /api/ai-context/reset", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("POST /api/ai-context/reset", False, f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("POST /api/ai-context/reset", False, f"Exception: {str(e)}")
        return False


def test_github_apply_update_endpoint_exists():
    """Verify POST /api/github/apply-update endpoint exists (without calling it)"""
    try:
        # We'll test with an empty repo to get a 400 error, proving the endpoint exists
        # First clear the repo
        clear_payload = {"repo_url": "", "branch": "main"}
        requests.post(f"{BASE_URL}/github/config", json=clear_payload, timeout=10)
        
        # Try to apply update (should fail with 400)
        response = requests.post(f"{BASE_URL}/github/apply-update", json={}, timeout=10)
        if response.status_code == 400:
            log_test("POST /api/github/apply-update (endpoint exists)", True, 
                    f"Endpoint exists and returns 400 when no repo configured")
            # Restore the repo config
            restore_payload = {
                "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
                "branch": "main"
            }
            requests.post(f"{BASE_URL}/github/config", json=restore_payload, timeout=10)
            return True
        else:
            log_test("POST /api/github/apply-update (endpoint exists)", False, 
                    f"Unexpected status: {response.status_code}")
            # Restore the repo config
            restore_payload = {
                "repo_url": "https://github.com/alejandropiedrasanta1-ui/CINEMA",
                "branch": "main"
            }
            requests.post(f"{BASE_URL}/github/config", json=restore_payload, timeout=10)
            return False
    except Exception as e:
        log_test("POST /api/github/apply-update (endpoint exists)", False, f"Exception: {str(e)}")
        return False


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\n✅ PASSED: {len(test_results['passed'])} tests")
    for test in test_results['passed']:
        print(f"  • {test}")
    
    if test_results['failed']:
        print(f"\n❌ FAILED: {len(test_results['failed'])} tests")
        for test in test_results['failed']:
            print(f"  • {test['name']}")
            if test['message']:
                print(f"    → {test['message']}")
    
    if test_results['warnings']:
        print(f"\n⚠️  WARNINGS: {len(test_results['warnings'])}")
        for warning in test_results['warnings']:
            print(f"  • {warning}")
    
    print("\n" + "="*80)
    total = len(test_results['passed']) + len(test_results['failed'])
    success_rate = (len(test_results['passed']) / total * 100) if total > 0 else 0
    print(f"SUCCESS RATE: {success_rate:.1f}% ({len(test_results['passed'])}/{total})")
    print("="*80 + "\n")
    
    return len(test_results['failed']) == 0


def main():
    """Run all tests"""
    print("="*80)
    print("BACKEND API TESTING - GitHub Integration & AI Context")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test started at: {datetime.now().isoformat()}")
    print("="*80)
    
    # Test existing endpoints
    print("\n### Testing Existing Endpoints ###")
    test_root_endpoint()
    test_stats_endpoint()
    test_settings_endpoint()
    
    # Test GitHub config endpoints
    print("\n### Testing GitHub Config Endpoints ###")
    test_github_config_get()
    test_github_config_post_valid()
    test_github_config_post_invalid()
    test_github_config_post_with_token()
    
    # Test GitHub check updates
    print("\n### Testing GitHub Check Updates ###")
    test_github_check_updates()
    test_github_check_updates_no_repo()
    
    # Test GitHub apply update endpoint (without actually calling it)
    print("\n### Testing GitHub Apply Update Endpoint ###")
    test_github_apply_update_endpoint_exists()
    
    # Test AI Context endpoints
    print("\n### Testing AI Context Endpoints ###")
    test_ai_context_get()
    test_ai_context_post()
    test_ai_context_reset()
    
    # Print summary
    all_passed = print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
