#!/usr/bin/env python3
"""
Entry point for Corruption Flow Pipeline.
Run with: python script/run_corruption_flow.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is in path for imports
script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
src_dir = project_dir / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Direct import to avoid __init__.py issues
import importlib.util
spec = importlib.util.spec_from_file_location("corruption_flow", src_dir / "pipelines" / "corruption_flow.py")
corruption_flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corruption_flow)

if __name__ == "__main__":
    corruption_flow.main()
