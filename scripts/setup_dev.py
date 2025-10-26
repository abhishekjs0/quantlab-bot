#!/usr/bin/env python3
"""
Development setup script for QuantLab
Installs development dependencies and sets up pre-commit hooks
"""

import subprocess
import sys


def run_command(cmd: str, description: str = "") -> bool:
    """Run a shell command and return success status"""
    if description:
        print(f"📦 {description}")

    try:
        subprocess.run(cmd.split(), check=True, capture_output=True, text=True)
        print(f"✅ {description or cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or cmd} failed:")
        print(f"   {e.stderr}")
        return False


def main():
    """Main setup function"""
    print("🚀 Setting up QuantLab development environment...")

    # Check if we're in a virtual environment
    if not hasattr(sys, "real_prefix") and not (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print("⚠️  Warning: Not in a virtual environment!")
        print("   Consider running: python -m venv .venv && source .venv/bin/activate")

    # Install development dependencies
    if not run_command("pip install -e .[dev]", "Installing development dependencies"):
        return False

    # Install pre-commit hooks
    if not run_command("pre-commit install", "Installing pre-commit hooks"):
        print("ℹ️  Pre-commit hooks not installed (optional)")

    # Run initial format and lint
    print("\n🧹 Running initial code formatting...")
    run_command("black .", "Formatting code with black")
    run_command("isort .", "Sorting imports")
    run_command("ruff check --fix .", "Running ruff linter")

    print("\n✨ Development environment setup complete!")
    print("\n📝 Next steps:")
    print("   - Run tests: make test")
    print("   - Run linting: make lint")
    print("   - Run backtest: make demo")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
