#!/usr/bin/env python3
"""
Test runner script for the Document Processing Microservice.

This script provides convenient commands to run different types of tests
with appropriate configurations and reporting.
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path


class TestRunner:
    """Test runner with various test execution options."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.tests_dir = self.project_root / "tests"

    def run_command(self, command: list, description: str = None):
        """Run a shell command and handle errors."""
        if description:
            print(f"\n🔄 {description}")
            print("-" * 50)

        print(f"Running: {' '.join(command)}")
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                check=True,
                capture_output=False
            )
            duration = time.time() - start_time
            print(f"✅ Completed in {duration:.2f}s")
            return result
        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            print(f"❌ Failed after {duration:.2f}s with exit code {e.returncode}")
            return e

    def install_dependencies(self):
        """Install test dependencies."""
        dependencies = [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "pytest-asyncio>=0.21.1",
            "pytest-timeout>=2.1.0",
            "black>=23.11.0",
            "ruff>=0.1.6",
            "mypy>=1.7.1",
            "safety>=2.3.0",
            "bandit>=1.7.0",
            "psutil>=5.9.0"
        ]

        print("📦 Installing test dependencies...")
        for dep in dependencies:
            result = self.run_command([
                sys.executable, "-m", "pip", "install", dep
            ])
            if isinstance(result, subprocess.CalledProcessError):
                print(f"⚠️  Warning: Failed to install {dep}")

    def run_linting(self):
        """Run code quality checks."""
        print("\n🔍 Running Code Quality Checks")
        print("=" * 50)

        # Black formatting check
        self.run_command([
            "black", "--check", "--diff", "."
        ], "Checking code formatting with Black")

        # Ruff linting
        self.run_command([
            "ruff", "check", "."
        ], "Running linting with Ruff")

        # MyPy type checking
        self.run_command([
            "mypy", "src/", "--ignore-missing-imports"
        ], "Running type checking with MyPy")

    def run_unit_tests(self, coverage=True, verbose=True):
        """Run unit tests."""
        cmd = ["pytest", "tests/unit/"]

        if coverage:
            cmd.extend([
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-report=xml:coverage.xml",
                "--cov-fail-under=80"
            ])

        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--junit-xml=junit-unit.xml",
            "-m", "unit"
        ])

        self.run_command(cmd, "Running Unit Tests")

    def run_integration_tests(self, verbose=True):
        """Run integration tests."""
        cmd = ["pytest", "tests/integration/"]

        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--junit-xml=junit-integration.xml",
            "-m", "integration"
        ])

        self.run_command(cmd, "Running Integration Tests")

    def run_e2e_tests(self, verbose=True):
        """Run end-to-end tests."""
        cmd = ["pytest", "tests/e2e/"]

        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--junit-xml=junit-e2e.xml",
            "--timeout=300",
            "-m", "e2e"
        ])

        self.run_command(cmd, "Running End-to-End Tests")

    def run_performance_tests(self, verbose=True):
        """Run performance tests."""
        cmd = ["pytest", "tests/performance/"]

        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--junit-xml=junit-performance.xml",
            "--timeout=600",
            "-m", "performance"
        ])

        self.run_command(cmd, "Running Performance Tests")

    def run_security_tests(self, verbose=True):
        """Run security tests."""
        cmd = ["pytest", "tests/security/"]

        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--junit-xml=junit-security.xml",
            "-m", "security"
        ])

        self.run_command(cmd, "Running Security Tests")

    def run_security_scans(self):
        """Run security scanning tools."""
        print("\n🔒 Running Security Scans")
        print("=" * 50)

        # Safety check for dependencies
        self.run_command([
            "safety", "check", "--json", "--output", "safety-report.json"
        ], "Checking dependencies for vulnerabilities with Safety")

        # Bandit security linter
        self.run_command([
            "bandit", "-r", "src/", "-f", "json", "-o", "bandit-report.json"
        ], "Running security linting with Bandit")

    def run_all_tests(self):
        """Run all test suites."""
        print("\n🚀 Running Complete Test Suite")
        print("=" * 50)

        # Run in order of dependency
        self.run_linting()
        self.run_unit_tests()
        self.run_integration_tests()
        self.run_e2e_tests()
        self.run_security_tests()
        self.run_security_scans()

        print("\n✅ All tests completed!")

    def run_quick_tests(self):
        """Run quick test suite (unit + integration only)."""
        print("\n⚡ Running Quick Test Suite")
        print("=" * 50)

        self.run_linting()
        self.run_unit_tests()
        self.run_integration_tests()

        print("\n✅ Quick tests completed!")

    def run_ci_tests(self):
        """Run tests suitable for CI environment."""
        print("\n🤖 Running CI Test Suite")
        print("=" * 50)

        # Set CI environment variables
        os.environ["CI"] = "true"
        os.environ["TESTING"] = "true"

        self.run_linting()
        self.run_unit_tests(coverage=True)
        self.run_integration_tests()
        self.run_security_tests()

        print("\n✅ CI tests completed!")

    def generate_reports(self):
        """Generate test reports."""
        print("\n📊 Generating Test Reports")
        print("=" * 50)

        # Coverage report
        if os.path.exists("htmlcov/index.html"):
            print("📈 Coverage report available at: htmlcov/index.html")

        # Test results
        junit_files = [
            "junit-unit.xml",
            "junit-integration.xml",
            "junit-e2e.xml",
            "junit-performance.xml",
            "junit-security.xml"
        ]

        available_reports = [f for f in junit_files if os.path.exists(f)]
        if available_reports:
            print(f"📋 JUnit reports: {', '.join(available_reports)}")

        # Security reports
        security_reports = [
            "safety-report.json",
            "bandit-report.json"
        ]

        available_security = [f for f in security_reports if os.path.exists(f)]
        if available_security:
            print(f"🔒 Security reports: {', '.join(available_security)}")

    def clean_reports(self):
        """Clean up test reports and artifacts."""
        print("\n🧹 Cleaning up test reports")

        artifacts = [
            "htmlcov/",
            "coverage.xml",
            ".coverage",
            "junit-*.xml",
            "*-report.json",
            ".pytest_cache/",
            "__pycache__/",
            "*.pyc"
        ]

        for pattern in artifacts:
            result = subprocess.run(
                ["find", ".", "-name", pattern, "-exec", "rm", "-rf", "{}", "+"],
                capture_output=True
            )

        print("✅ Cleanup completed!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for Document Processing Microservice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --all              # Run all tests
  python run_tests.py --quick            # Run quick tests (unit + integration)
  python run_tests.py --unit --coverage  # Run unit tests with coverage
  python run_tests.py --security         # Run security tests only
  python run_tests.py --ci               # Run CI test suite
  python run_tests.py --clean            # Clean up test artifacts
        """
    )

    # Test type options
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--quick", action="store_true", help="Run quick test suite")
    parser.add_argument("--ci", action="store_true", help="Run CI test suite")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--security", action="store_true", help="Run security tests")

    # Options
    parser.add_argument("--coverage", action="store_true", help="Include coverage reporting")
    parser.add_argument("--lint", action="store_true", help="Run linting only")
    parser.add_argument("--install", action="store_true", help="Install test dependencies")
    parser.add_argument("--clean", action="store_true", help="Clean up test artifacts")
    parser.add_argument("--reports", action="store_true", help="Generate test reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    runner = TestRunner()

    # Handle special commands first
    if args.install:
        runner.install_dependencies()
        return

    if args.clean:
        runner.clean_reports()
        return

    if args.reports:
        runner.generate_reports()
        return

    if args.lint:
        runner.run_linting()
        return

    # Handle test execution
    if args.all:
        runner.run_all_tests()
    elif args.quick:
        runner.run_quick_tests()
    elif args.ci:
        runner.run_ci_tests()
    else:
        # Run individual test suites
        if args.unit:
            runner.run_unit_tests(coverage=args.coverage, verbose=args.verbose)
        if args.integration:
            runner.run_integration_tests(verbose=args.verbose)
        if args.e2e:
            runner.run_e2e_tests(verbose=args.verbose)
        if args.performance:
            runner.run_performance_tests(verbose=args.verbose)
        if args.security:
            runner.run_security_tests(verbose=args.verbose)

        # If no specific tests selected, show help
        if not any([args.unit, args.integration, args.e2e, args.performance, args.security]):
            parser.print_help()
            print("\n💡 Try: python run_tests.py --quick")

    # Generate reports at the end
    runner.generate_reports()


if __name__ == "__main__":
    main()