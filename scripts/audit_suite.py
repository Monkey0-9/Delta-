"""Fast and comprehensive test auditor running suites by domain/folder."""
import sys
import os
import subprocess
import json
from pathlib import Path

def run_pytest(target_paths, name):
    print(f"\n=======================================================", flush=True)
    print(f"RUNNING SUITE: {name}", flush=True)
    print(f"TARGETS: {target_paths}", flush=True)
    print(f"=======================================================", flush=True)
    
    cmd = [
        sys.executable,
        "-m", "pytest",
        "-p", "no:ddtrace",
        "-p", "no:langsmith",
        "-p", "no:playwright",
        "--tb=short",
        "-q",
    ] + target_paths
    
    try:
        res = subprocess.run(cmd, cwd=str(Path.cwd()), capture_output=True, text=True, timeout=120)
        output = (res.stdout + "\n" + res.stderr).strip()
        print(output, flush=True)
        return {
            "name": name,
            "returncode": res.returncode,
            "passed": res.returncode == 0,
            "output": output
        }
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] Suite {name} timed out after 120s", flush=True)
        return {
            "name": name,
            "returncode": -1,
            "passed": False,
            "output": "Timed out after 120s"
        }
    except Exception as e:
        print(f"[ERROR] Suite {name}: {e}", flush=True)
        return {
            "name": name,
            "returncode": -2,
            "passed": False,
            "output": str(e)
        }

def main():
    root = Path.cwd()
    tests_root = root / "tests"
    
    # 1. Root test files
    root_files = [p.as_posix() for p in tests_root.glob("test_*.py")]
    
    # Define suite groups
    suites = [
        ("Root Wave & System Tests", root_files),
        ("Institutional Suite", ["tests/institutional"]),
        ("Security Suite", ["tests/security"]),
        ("Integration Suite", ["tests/integration"]),
        ("E2E Suite", ["tests/e2e"]),
        ("Risk & Execution Suite", ["tests/risk", "tests/execution", "tests/perf", "tests/replay"]),
        ("Chaos & Property Suite", ["tests/chaos", "tests/property", "tests/finalization"]),
        ("W46-59 Waves", ["tests/w46_52", "tests/w53_59"]),
        ("Unit Suite", ["tests/unit"])
    ]
    
    all_results = []
    for name, targets in suites:
        res = run_pytest(targets, name)
        all_results.append(res)
        
    out_file = root / "artifacts" / "suite_audit_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
        
    print("\n\n================ FINAL SUITE SUMMARY ================", flush=True)
    for r in all_results:
        status_str = "PASS [OK]" if r["passed"] else "FAIL / ISSUES"
        print(f"{r['name']:<35} : {status_str}", flush=True)

if __name__ == "__main__":
    main()
