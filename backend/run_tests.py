#!/usr/bin/env python
"""
Test runner script for AI Life Assistant Backend

Usage:
    python run_tests.py                    # Run all tests with verbose output
    python run_tests.py --coverage         # Run with coverage report
    python run_tests.py --specific test_command_schema.py
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Run tests for AI Life Assistant')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--specific', type=str, help='Run specific test file')
    parser.add_argument('--quick', action='store_true', help='Run only quick tests (skip integration tests)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output (default: True)')
    
    args = parser.parse_args()
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent.absolute()
    os.chdir(backend_dir)
    
    print(f"Running tests from: {backend_dir}")
    print(f"Python version: {sys.version}")
    print(f"Test directory: {backend_dir}/tests")
    print("-" * 80)
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    if args.specific:
        cmd.append(f"tests/{args.specific}")
    else:
        cmd.append("tests/")
    
    # Add flags
    if args.verbose or not args.specific:
        cmd.append("-v")  # verbose
        cmd.append("-s")  # show print statements
    
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    if args.quick:
        cmd.append("-m")
        cmd.append("not integration")
    
    # Color output
    cmd.append("--color=yes")
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run tests
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("-" * 80)
        print("✅ All tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("-" * 80)
        print("❌ Some tests failed")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
