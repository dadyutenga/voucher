"""
Test script to verify Wi-Fi Voucher System functionality.
This script tests various components and endpoints to ensure everything works correctly.
"""

import os
import sys
import asyncio
import json
import smtplib
from pathlib import Path
from email.mime.text import MIMEText

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

import requests
from sqlalchemy import create_engine, text
from datetime import datetime

class SystemTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_email = "test@example.com"
        self.results = []

    def log_test(self, test_name, success, message="", details=None):
        """Log test results."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")

    def test_database_connection(self):
        """Test database connectivity."""
        try:
            from app.core.config import settings
            engine = create_engine(settings.DATABASE_URL)

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                if result and result[0] == 1:
                    self.log_test("Database Connection", True, "Successfully connected to database")
                    return True
                else:
                    self.log_test("Database Connection", False, "Unexpected result from database")
                    return False

        except Exception as e:
            self.log_test("Database Connection", False, f"Failed to connect: {str(e)}")
            return False

    def test_database_tables(self):
        """Test that all required tables exist."""
        try:
            from app.core.config import settings
            engine = create_engine(settings.DATABASE_URL)

            required_tables = ['accounts', 'vouchers', 'transactions']

            with engine.connect() as conn:
                for table in required_tables:
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = '{table}'
                        )
                    """)).fetchone()

                    if not result[0]:
                        self.log_test("Database Tables", False, f"Missing table: {table}")
                        return False

                self.log_test("Database Tables", True, "All required tables exist")
                return True

        except Exception as e:
            self.log_test("Database Tables", False, f"Error checking tables: {str(e)}")
            return False

    def test_api_health(self):
        """Test API health endpoint."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("API Health", True, "Health endpoint responding correctly")
                    return True
                else:
                    self.log_test("API Health", False, f"Unhealthy status: {data}")
                    return False
            else:
                self.log_test("API Health", False, f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.log_test("API Health", False, f"Failed to reach health endpoint: {str(e)}")
            return False

    def test_api_docs(self):
        """Test API documentation endpoints."""
        try:
            # Test Swagger UI
            response = requests.get(f"{self.base_url}/docs", timeout=10)
            if response.status_code != 200:
                self.log_test("API Documentation", False, f"Swagger UI not accessible: HTTP {response.status_code}")
                return False

            # Test OpenAPI JSON
            response = requests.get(f"{self.base_url}/openapi.json", timeout=10)
            if response.status_code == 200:
                try:
                    json.loads(response.text)  # Validate JSON
                    self.log_test("API Documentation", True, "API docs and OpenAPI spec accessible")
                    return True
                except json.JSONDecodeError:
                    self.log_test("API Documentation", False, "Invalid OpenAPI JSON")
                    return False
            else:
                self.log_test("API Documentation", False, f"OpenAPI spec not accessible: HTTP {response.status_code}")
                return False

        except Exception as e:
            self.log_test("API Documentation", False, f"Failed to test API docs: {str(e)}")
            return False

    def test_splash_page(self):
        """Test splash page accessibility."""
        try:
            response = requests.get(f"{self.base_url}/splash", timeout=10)
            if response.status_code == 200:
                content = response.text
                # Check for key elements
                if "Wi-Fi Access" in content and "voucher" in content.lower():
                    self.log_test("Splash Page", True, "Splash page loads correctly")
                    return True
                else:
                    self.log_test("Splash Page", False, "Splash page missing expected content")
                    return False
            else:
                self.log_test("Splash Page", False, f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.log_test("Splash Page", False, f"Failed to load splash page: {str(e)}")
            return False

    def test_voucher_plans(self):
        """Test voucher plans endpoint."""
        try:
            response = requests.get(f"{self.base_url}/payment/plans", timeout=10)
            if response.status_code == 200:
                data = response.json()
                plans = data.get("plans", [])
                if plans and len(plans) > 0:
                    # Check plan structure
                    demo_plan = next((p for p in plans if p.get("id") == "demo"), None)
                    if demo_plan:
                        self.log_test("Voucher Plans", True, f"Found {len(plans)} voucher plans including demo")
                        return True
                    else:
                        self.log_test("Voucher Plans", False, "Demo plan not found in plans")
                        return False
                else:
                    self.log_test("Voucher Plans", False, "No voucher plans returned")
                    return False
            else:
                self.log_test("Voucher Plans", False, f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.log_test("Voucher Plans", False, f"Failed to get voucher plans: {str(e)}")
            return False

    def test_demo_voucher_creation(self):
        """Test demo voucher creation."""
        try:
            response = requests.post(
                f"{self.base_url}/payment/create-demo-voucher",
                params={"email": self.test_email},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "voucher_code" in data and data.get("duration") == 10:
                    voucher_code = data["voucher_code"]
                    self.log_test("Demo Voucher Creation", True, f"Created demo voucher: {voucher_code}")
                    return voucher_code
                else:
                    self.log_test("Demo Voucher Creation", False, f"Invalid response: {data}")
                    return None
            else:
                self.log_test("Demo Voucher Creation", False, f"HTTP {response.status_code}: {response.text}")
                return None

        except Exception as e:
            self.log_test("Demo Voucher Creation", False, f"Failed to create demo voucher: {str(e)}")
            return None

    def test_voucher_validation(self, voucher_code):
        """Test voucher validation endpoint."""
        if not voucher_code:
            self.log_test("Voucher Validation", False, "No voucher code provided")
            return False

        try:
            response = requests.post(
                f"{self.base_url}/auth/validate",
                json={
                    "email": self.test_email,
                    "voucher_code": voucher_code
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("valid") is True:
                    self.log_test("Voucher Validation", True, f"Voucher {voucher_code} is valid")
                    return True
                else:
                    self.log_test("Voucher Validation", False, f"Voucher invalid: {data.get('message')}")
                    return False
            else:
                self.log_test("Voucher Validation", False, f"HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            self.log_test("Voucher Validation", False, f"Failed to validate voucher: {str(e)}")
            return False

    def test_email_configuration(self):
        """Test email configuration (without sending)."""
        try:
            from app.core.config import settings

            required_settings = [
                'SMTP_SERVER',
                'SMTP_PORT',
                'SMTP_USERNAME',
                'SMTP_PASSWORD',
                'SENDER_EMAIL'
            ]

            missing = []
            for setting in required_settings:
                if not hasattr(settings, setting) or not getattr(settings, setting):
                    missing.append(setting)

            if missing:
                self.log_test("Email Configuration", False, f"Missing settings: {', '.join(missing)}")
                return False
            else:
                # Try to connect to SMTP server (without authentication)
                try:
                    import socket
                    sock = socket.create_connection((settings.SMTP_SERVER, settings.SMTP_PORT), timeout=5)
                    sock.close()
                    self.log_test("Email Configuration", True, "SMTP server reachable and settings configured")
                    return True
                except socket.error:
                    self.log_test("Email Configuration", False, "SMTP server unreachable")
                    return False

        except Exception as e:
            self.log_test("Email Configuration", False, f"Error checking email config: {str(e)}")
            return False

    def test_stripe_configuration(self):
        """Test Stripe configuration."""
        try:
            from app.core.config import settings
            import stripe

            if not settings.STRIPE_API_KEY:
                self.log_test("Stripe Configuration", False, "STRIPE_API_KEY not set")
                return False

            stripe.api_key = settings.STRIPE_API_KEY

            # Test API key by retrieving account info
            try:
                account = stripe.Account.retrieve()
                self.log_test("Stripe Configuration", True, f"Stripe connected: {account.get('email', 'N/A')}")
                return True
            except stripe.error.AuthenticationError:
                self.log_test("Stripe Configuration", False, "Invalid Stripe API key")
                return False
            except Exception as e:
                self.log_test("Stripe Configuration", False, f"Stripe API error: {str(e)}")
                return False

        except Exception as e:
            self.log_test("Stripe Configuration", False, f"Error testing Stripe: {str(e)}")
            return False

    def test_admin_endpoints(self):
        """Test admin endpoints accessibility."""
        endpoints = [
            "/admin/vouchers",
            "/admin/accounts",
            "/admin/transactions",
            "/admin/stats"
        ]

        success_count = 0
        for endpoint in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    success_count += 1

            except Exception:
                pass

        if success_count == len(endpoints):
            self.log_test("Admin Endpoints", True, f"All {len(endpoints)} admin endpoints accessible")
            return True
        else:
            self.log_test("Admin Endpoints", False, f"Only {success_count}/{len(endpoints)} admin endpoints accessible")
            return False

    def run_all_tests(self):
        """Run all system tests."""
        print("🧪 Wi-Fi Voucher System - Running Tests")
        print("=" * 50)

        # Core infrastructure tests
        self.test_database_connection()
        self.test_database_tables()
        self.test_email_configuration()
        self.test_stripe_configuration()

        # API tests
        self.test_api_health()
        self.test_api_docs()
        self.test_splash_page()
        self.test_voucher_plans()
        self.test_admin_endpoints()

        # Functional tests
        voucher_code = self.test_demo_voucher_creation()
        if voucher_code:
            self.test_voucher_validation(voucher_code)

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate test report."""
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)

        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r["success"]])
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print(f"\n🔍 FAILED TESTS:")
            for result in self.results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")

        print(f"\n💾 Saving detailed results to test_results.json")
        with open("test_results.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)

        print("\n🎯 RECOMMENDATIONS:")
        if failed_tests == 0:
            print("   ✅ All tests passed! Your system is ready for use.")
        else:
            print("   🔧 Fix the failed tests before deploying to production.")
            print("   📚 Check the README.md for troubleshooting information.")

        return failed_tests == 0

def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Wi-Fi Voucher System Tester")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--email",
        default="test@example.com",
        help="Test email address (default: test@example.com)"
    )

    args = parser.parse_args()

    tester = SystemTester(base_url=args.url)
    tester.test_email = args.email

    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
