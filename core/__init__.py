"""Core backtesting and strategy framework components."""

# ============================================================================
# CRITICAL: Prevent Python bytecode cache (.pyc) files
# This ensures strategy changes take effect immediately without stale cache
# ============================================================================
import os
import sys

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

# Clear any existing __pycache__ directories on import
import shutil
from pathlib import Path

_workspace_root = Path(__file__).parent.parent
for _pycache_dir in _workspace_root.rglob('__pycache__'):
    try:
        shutil.rmtree(_pycache_dir)
    except Exception:
        pass
# ============================================================================
