#!/usr/bin/env python3
"""
Strategy Import Checker
=======================
Ensures all strategies import indicators from utils.indicators
and don't implement indicator calculations inline.

This script is designed to be run as a pre-commit hook or CI check.

Usage:
    python scripts/check_strategy_imports.py
    python scripts/check_strategy_imports.py strategies/my_strategy.py
    
Exit codes:
    0 - All checks passed
    1 - Violations found
"""

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    file: str
    line: int
    message: str


# Patterns that suggest inline indicator calculation
INLINE_CALCULATION_PATTERNS = [
    (r'\.rolling\s*\(\s*\d+\s*\)\s*\.mean\s*\(', 'Inline SMA calculation - use SMA from utils.indicators'),
    (r'\.rolling\s*\(\s*\d+\s*\)\s*\.std\s*\(', 'Inline standard deviation - use BollingerBands from utils.indicators'),
    (r'(?<![a-zA-Z_])\.ewm\s*\(', 'Inline EMA calculation - use EMA from utils.indicators'),
    (r'\.diff\s*\(\s*\)\s*\.rolling', 'Inline momentum calculation - use Momentum from utils.indicators'),
    (r'100\s*-\s*\(100\s*/\s*\(1\s*\+', 'Inline RSI calculation - use RSI from utils.indicators'),
    (r'(?<![a-zA-Z_\.])ta\.[a-z]', 'Using ta library directly - use utils.indicators instead'),
    (r'(?<![a-zA-Z_\.])talib\.[a-z]', 'Using talib directly - use utils.indicators instead'),
]

# Required import patterns for strategies
REQUIRED_IMPORTS = [
    'from core.strategy import Strategy',
    'from utils.indicators import',
]

# Allowed indicator imports (from utils.indicators)
ALLOWED_INDICATOR_SOURCES = [
    'utils.indicators',
    'utils',  # For backward compatibility re-exports
]


def check_file(filepath: Path) -> list[Violation]:
    """Check a single strategy file for violations."""
    violations = []
    
    try:
        content = filepath.read_text()
        lines = content.split('\n')
    except Exception as e:
        violations.append(Violation(str(filepath), 0, f'Could not read file: {e}'))
        return violations
    
    # Track if we're inside a docstring
    in_docstring = False
    docstring_marker = None
    
    # Check for inline calculation patterns
    for line_num, line in enumerate(lines, 1):
        stripped = line.lstrip()
        
        # Skip comments
        if stripped.startswith('#'):
            continue
        
        # Handle docstrings (triple quotes)
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_marker = stripped[:3]
                # Check if docstring ends on same line
                if stripped.count(docstring_marker) >= 2:
                    continue  # Single-line docstring
                in_docstring = True
                continue
        else:
            # Check if docstring ends
            if docstring_marker in stripped:
                in_docstring = False
                docstring_marker = None
            continue
        
        # Skip lines that are just string literals (like comments in docstrings)
        if stripped.startswith(('"', "'")):
            continue
            
        for pattern, message in INLINE_CALCULATION_PATTERNS:
            if re.search(pattern, line):
                violations.append(Violation(str(filepath), line_num, message))
    
    # Parse AST to check imports
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        violations.append(Violation(str(filepath), e.lineno or 0, f'Syntax error: {e.msg}'))
        return violations
    
    has_strategy_import = False
    has_indicator_import = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            
            # Check for Strategy import
            if module == 'core.strategy':
                for alias in node.names:
                    if alias.name == 'Strategy':
                        has_strategy_import = True
            
            # Check for indicator imports
            if module in ALLOWED_INDICATOR_SOURCES:
                has_indicator_import = True
            
            # Flag direct imports from calculation libraries
            if module in ('pandas_ta', 'talib', 'ta'):
                violations.append(Violation(
                    str(filepath), 
                    node.lineno, 
                    f'Direct import from {module} - use utils.indicators instead'
                ))
    
    # Check if this is a strategy class (has Strategy subclass)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == 'Strategy':
                    # This is a Strategy subclass - must have proper imports
                    if not has_strategy_import:
                        violations.append(Violation(
                            str(filepath),
                            node.lineno,
                            'Strategy class found but missing: from core.strategy import Strategy'
                        ))
                    if not has_indicator_import:
                        violations.append(Violation(
                            str(filepath),
                            node.lineno,
                            'Strategy class found but no indicator imports from utils.indicators'
                        ))
                    break
    
    return violations


def main():
    """Run the strategy import checker."""
    strategies_dir = Path(__file__).parent.parent / 'strategies'
    
    # Get files to check
    if len(sys.argv) > 1:
        # Check specific files
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Check all strategy files
        files = list(strategies_dir.glob('*.py'))
    
    # Filter out __init__.py
    files = [f for f in files if f.name != '__init__.py']
    
    all_violations = []
    
    for filepath in files:
        if not filepath.exists():
            print(f"Warning: File not found: {filepath}")
            continue
        violations = check_file(filepath)
        all_violations.extend(violations)
    
    # Report results
    if all_violations:
        print("❌ Strategy Import Check Failed\n")
        print("=" * 60)
        for v in all_violations:
            print(f"{v.file}:{v.line}: {v.message}")
        print("=" * 60)
        print(f"\nTotal violations: {len(all_violations)}")
        print("\n💡 Tip: Import indicators from utils.indicators instead of calculating inline.")
        print("   Example: from utils.indicators import EMA, RSI, SMA, ATR")
        return 1
    else:
        print(f"✅ Strategy Import Check Passed ({len(files)} files checked)")
        return 0


if __name__ == '__main__':
    sys.exit(main())
