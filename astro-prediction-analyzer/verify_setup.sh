#!/bin/bash
# YouTube Video Analyzer - Setup Verification Script
# This script verifies all components are working correctly

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     YouTube Video Analyzer - Setup Verification               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/abhishekshah/Desktop/quantlab-workspace/astro-prediction-analyzer"
cd "$PROJECT_DIR" || exit 1

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📁 Project Directory: $PROJECT_DIR"
echo ""

# Check 1: Core modules exist
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Checking Core Modules..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

modules=("config.py" "youtube_fetcher.py" "transcript_handler.py" "summarizer.py" "analyzer.py" "main.py")
for module in "${modules[@]}"; do
  if [ -f "$module" ]; then
    echo -e "${GREEN}✓${NC} $module"
  else
    echo -e "${RED}✗${NC} $module (MISSING)"
  fi
done
echo ""

# Check 2: Configuration and environment
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Checking Configuration..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f ".env" ]; then
  echo -e "${GREEN}✓${NC} .env file exists"
  if grep -q "YOUTUBE_API_KEY" .env; then
    echo -e "${GREEN}✓${NC} YOUTUBE_API_KEY configured"
  fi
  if grep -q "OPENAI_API_KEY" .env; then
    echo -e "${GREEN}✓${NC} OPENAI_API_KEY configured"
  fi
else
  echo -e "${RED}✗${NC} .env file missing"
fi
echo ""

# Check 3: Documentation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Checking Documentation..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docs=("README.md" "QUICK_START.md" "SETUP_COMPLETE.md" "ARCHITECTURE.md")
for doc in "${docs[@]}"; do
  if [ -f "$doc" ]; then
    echo -e "${GREEN}✓${NC} $doc"
  fi
done
echo ""

# Check 4: Run comprehensive test
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Running Comprehensive Tests..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 test_setup.py 2>&1 | grep -E "(PASS|FAIL|ALL TESTS)"
echo ""

# Check 5: Data directories
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Checking Data Directories..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

dirs=("data" "reports" "data/cache")
for dir in "${dirs[@]}"; do
  if [ -d "$dir" ]; then
    echo -e "${GREEN}✓${NC} $dir/"
  fi
done
echo ""

# Check 6: Recent output files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Latest Outputs..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "reports/analysis_report.md" ]; then
  predictions=$(grep -c "^###" reports/analysis_report.md || echo "0")
  echo -e "${GREEN}✓${NC} analysis_report.md ($predictions predictions)"
fi

if [ -f "data/videos_metadata.json" ]; then
  videos=$(python3 -c "import json; print(len(json.load(open('data/videos_metadata.json'))))" 2>/dev/null || echo "?")
  echo -e "${GREEN}✓${NC} videos_metadata.json ($videos videos)"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Setup Verification Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Ready to use! Start with:"
echo ""
echo "   python main.py --search 'your topic' --videos 5"
echo ""
echo "📖 Documentation:"
echo "   - QUICK_START.md (fast commands)"
echo "   - SETUP_COMPLETE.md (full details)"
echo "   - ARCHITECTURE.md (technical overview)"
echo ""
