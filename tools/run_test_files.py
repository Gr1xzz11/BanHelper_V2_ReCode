from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    test_files = sorted(Path("tests").glob("test_*.py"))
    if not test_files:
        print("No test files found", file=sys.stderr)
        return 2

    failures: list[str] = []
    for test_file in test_files:
        print(f"\n===== {test_file} =====", flush=True)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(test_file),
            "--timeout=60",
            "--durations=10",
        ]
        try:
            completed = subprocess.run(command, timeout=180, check=False)
        except subprocess.TimeoutExpired:
            failures.append(f"{test_file}: process timeout after 180 seconds")
            print(failures[-1], file=sys.stderr, flush=True)
            continue
        if completed.returncode != 0:
            failures.append(f"{test_file}: exit code {completed.returncode}")

    if failures:
        print("\nFailed test files:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"\nAll {len(test_files)} test files passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
