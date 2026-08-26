import os
import sys
import subprocess
from pathlib import Path

def run_test_script(script_path: Path) -> bool:
    print(f"\n==================================================")
    print(f"RUNNING TEST STEP: {script_path.name}")
    print(f"==================================================")
    
    # Run test using the same Python interpreter
    result = subprocess.run([sys.executable, str(script_path)], capture_output=False)
    
    if result.returncode == 0:
        print(f"\n[PASS] {script_path.name} PASSED")
        return True
    else:
        print(f"\n[FAIL] {script_path.name} FAILED (Exit Code: {result.returncode})", file=sys.stderr)
        return False

def main():
    tests_dir = Path(__file__).parent
    test_files = sorted([
        tests_dir / f"test_step{i}.py" for i in range(1, 6)
    ])
    
    # Check that all test files exist
    for tf in test_files:
        if not tf.exists():
            print(f"Error: Test file {tf} does not exist!", file=sys.stderr)
            sys.exit(1)
            
    # Run tests in order
    all_passed = True
    for tf in test_files:
        if not run_test_script(tf):
            all_passed = False
            break  # Stop early if a step fails
            
    if all_passed:
        print(f"\n==================================================")
        print(f"SUCCESS: All test steps passed successfully!")
        print(f"==================================================")
        sys.exit(0)
    else:
        print(f"\n==================================================")
        print(f"FAILURE: One or more test steps failed.")
        print(f"==================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
