"""Audit all tests in the repository and generate a structured status report."""
import os
import sys
import subprocess
import json
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    tests_dir = root / "tests"
    
    # Collect all test_*.py files in tests directory recursively
    test_files = sorted([p for p in tests_dir.rglob("test_*.py") if "__pycache__" not in str(p)])
    
    results = {}
    summary = {
        "total_files": len(test_files),
        "passed_files": 0,
        "failed_files": 0,
        "error_files": 0,
        "total_passed_tests": 0,
        "total_failed_tests": 0,
        "total_skipped_tests": 0,
    }
    
    print(f"Discovered {len(test_files)} test files to audit.")
    
    for idx, test_file in enumerate(test_files, 1):
        rel_path = test_file.relative_to(root).as_posix()
        cmd = [
            sys.executable,
            "-m", "pytest",
            "-p", "no:ddtrace",
            "-p", "no:langsmith",
            "-p", "no:playwright",
            "--tb=short",
            "-q",
            str(test_file)
        ]
        
        try:
            res = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=30)
            output = (res.stdout + "\n" + res.stderr).strip()
            
            # parse line for passed, failed, skipped
            status = "PASSED" if res.returncode == 0 else "FAILED"
            results[rel_path] = {
                "exit_code": res.returncode,
                "status": status,
                "output": output
            }
            if res.returncode == 0:
                summary["passed_files"] += 1
                print(f"[{idx}/{len(test_files)}] [PASS] {rel_path}")
            else:
                summary["failed_files"] += 1
                print(f"[{idx}/{len(test_files)}] [FAIL] {rel_path}")
        except subprocess.TimeoutExpired:
            results[rel_path] = {
                "exit_code": -1,
                "status": "TIMEOUT",
                "output": "Execution timed out after 30s"
            }
            summary["failed_files"] += 1
            print(f"[{idx}/{len(test_files)}] [TIMEOUT] {rel_path}")
        except Exception as e:
            results[rel_path] = {
                "exit_code": -2,
                "status": "ERROR",
                "output": str(e)
            }
            summary["error_files"] += 1
            print(f"[{idx}/{len(test_files)}] [ERROR] {rel_path}: {e}")

    report_path = root / "artifacts" / "test_audit_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
        
    print("\n--- TEST AUDIT SUMMARY ---")
    print(f"Total Test Files: {summary['total_files']}")
    print(f"Passed: {summary['passed_files']}")
    print(f"Failed / Timeout: {summary['failed_files']}")
    print(f"Report written to: {report_path}")

if __name__ == "__main__":
    main()
