# Prediction Analyzer - Quick Start

**Consolidated from**: GETTING_STARTED.md, START_HERE.md, QUICK_START.md, QUICKSTART.md

---

## ⚡ 5-Minute Quick Start

### 1. Setup
```bash
cd astro-prediction-analyzer
pip install -r requirements.txt
export YOUTUBE_API_KEY="your-key-here"
export OPENAI_API_KEY="your-openai-key-here"
```

### 2. Run Analysis
```bash
python main.py --search "stock market predictions 2026" --videos 10
```

### 3. View Results
```bash
cat reports/analysis_report.md
```

**That's it!** You now have:
- 10 videos analyzed
- Predictions extracted and consolidated
- Common themes identified
- Confidence scores calculated

---

## 📋 What You Get

### Analysis Output

**reports/analysis_report.md**
- Consolidated themes from multiple videos
- Confidence percentages
- Source attribution
- Timeframe information

**reports/analysis_report.json**
- Machine-readable format
- All metadata
- Easy for further processing

**data/videos_metadata.json**
- Video details (title, channel, date)
- Subscriber counts
- Description summaries

---

## 🎯 Common Workflows

### Workflow 1: Basic Search
```bash
python main.py --search "gold prices 2026"
```
**Use When**: Quick analysis of a topic

### Workflow 2: Filtered Search
```bash
python main.py \
  --search "stock market astrology 2026" \
  --region IN \
  --videos 20 \
  --min-subscribers 50000 \
  --after 2025-01-22 \
  --before 2026-01-22
```
**Use When**: Need high-quality, recent, region-specific analysis

### Workflow 3: Deep Analysis
```bash
python main.py --search "your topic" --videos 50
```
**Use When**: Comprehensive coverage needed
**Note**: Takes 10-15 minutes

---

## 🔧 Configuration

### YouTube Search Options

| Option | Default | Example |
|--------|---------|---------|
| `--search` | Required | "market predictions" |
| `--videos` | 10 | 20 |
| `--region` | US | IN (India) |
| `--after` | 1 year ago | 2025-01-22 |
| `--before` | Today | 2026-01-22 |
| `--min-subscribers` | 0 | 50000 |

### Output Formats

Both markdown and JSON reports generated automatically:
- **Markdown**: Human-readable, includes links
- **JSON**: Structured data, programmatic access

---

## 📊 Understanding Results

### Confidence Scores
Calculated as: **(Diversity 40%) + (Credibility 30%) + (AI Confidence 30%)**

- **80%+**: Highly confident (theme appears in multiple videos)
- **70-80%**: Confident (good consensus)
- **60-70%**: Moderate (consider alternatives)
- **<60%**: Low confidence (outlier or speculation)

### Multi-Source Predictions
Themes appearing in **3+ videos** = strong consensus
```
Example:
- Defense Sector Growth: 11 videos (high consensus)
- Gold Price Rally: 9 videos (strong consensus)  
- Bitcoin Prediction: 1 video (outlier)
```

### Timeframe Aggregation
When multiple videos mention different timeframes, all are shown:
```
Timeframe: "Q1 2026, March 2026, By end of Q1, Throughout 2026"
```

---

## 🎬 Video Sources

### Channel Quality
- **Verified channels** included (50K+ subscribers)
- **Credibility score** based on:
  - Channel size
  - Engagement metrics
  - Topic expertise

### Example Quality Sources
- Major broadcasters (CNBC, ABP NEWS, ET NOW)
- Established analyst channels (100K+ subscribers)
- Verified experts in domain

---

## 🚀 Advanced Features

### Hindi Language Support
Automatically detects and translates:
```
- Fetches Hindi transcripts
- Auto-translates to English
- Processes in summarizer
```

### Automatic Consolidation
Groups similar predictions even with different wording:
```
"Gold prices will reach ₹100,000" 
+ "Gold expected to surge in 2026"
+ "Bullish on gold throughout 2026"
= 1 consolidated theme (9 videos)
```

### Keyword Recognition
Financial terms automatically matched:
- Commodities: gold, silver, crude, copper
- Markets: stock, sensex, nifty, index
- Sectors: IT, pharma, banking, defense
- Crypto: bitcoin, ethereum, blockchain

---

## ❓ FAQ

**Q: How long does analysis take?**
A: ~3-5 minutes for 10 videos, scales to 15 min for 50 videos

**Q: Can I run multiple searches?**
A: Yes, but respect YouTube API rate limits (10,000 units/day)

**Q: What if I don't have API keys?**
A: Get them free:
- [YouTube API](https://console.cloud.google.com)
- [OpenAI API](https://platform.openai.com)

**Q: Can I filter by language?**
A: Currently: English + Hindi (auto-detected)
Spanish/French: Use `--region` as proxy

**Q: How are predictions scored?**
A: AI + Diversity + Credibility (see Confidence Scores section)

**Q: Can I export for further analysis?**
A: Yes - use `reports/analysis_report.json`

---

## 🔗 Related Documentation

- [Architecture Guide](PREDICTION_ANALYZER_ARCHITECTURE.md) - How it works internally
- [Usage Guide](PREDICTION_ANALYZER_USAGE_GUIDE.md) - Detailed parameter reference
- [Main README](../../README.md) - Project overview

---

## 💡 Tips

✓ Use filters for high-quality results  
✓ Check confidence scores for reliability  
✓ Look for multi-source predictions (3+ videos)  
✓ Compare with market data for validation  
✓ Archive reports for tracking accuracy over time  
