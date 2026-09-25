"""
script/run_tests.py — chạy toàn bộ test suite chỉ bằng 1 lệnh:
    python script/run_tests.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    print("=" * 60)
    print("  Chạy pytest — Lan's Test Suite (CP4 + Bonus B3)")
    print("=" * 60)

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--no-header",
        ],
        cwd=PROJECT_DIR,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
