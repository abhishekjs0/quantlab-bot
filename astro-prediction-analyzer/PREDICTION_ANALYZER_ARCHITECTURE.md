# Prediction Analyzer - Architecture & Implementation

**Consolidated from**: ARCHITECTURE.md, OVERVIEW.md

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Pipeline Stages](#pipeline-stages)
3. [Data Flow](#data-flow)
4. [Key Components](#key-components)
5. [Confidence Scoring](#confidence-scoring-algorithm)
6. [Extension Points](#extension-points)

---

## System Architecture

### High-Level Design
```
┌─────────────────────────────────────────────────────────────┐
│                   Prediction Analyzer                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │   YouTube    │   │ Transcript   │   │   AI        │     │
│  │   Search     │→→→│ Extraction   │→→→│ Summarizer  │     │
│  └──────────────┘   └──────────────┘   └──────────────┘     │
│         ↓                  ↓                   ↓               │
│    [15 videos]      [14 transcripts]   [14 summaries]        │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │         Consolidation Engine                          │  │
│  │  - Extract predictions (69 total)                     │  │
│  │  - Group by similarity (keyword-based)                │  │
│  │  - Consolidate themes (17 unique)                     │  │
│  │  - Calculate confidence scores                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                           ↓                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │       Report Generation                              │    │
│  │  - analysis_report.md (human-readable)               │    │
│  │  - analysis_report.json (structured)                 │    │
│  │  - Grouped by consensus strength                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages

### Stage 1: YouTube Search
**File**: `youtube_fetcher.py`

**Functionality**:
- Search YouTube for videos matching query
- Apply filters (region, date range, subscribers)
- Fetch channel statistics
- Validate subscriber count (50K+ minimum)
- Cache metadata

**Output**:
```json
{
  "video_id": "abc123",
  "title": "Video Title",
  "channel": "Channel Name",
  "published_at": "2026-01-22T10:30:00Z",
  "subscriber_count": 500000
}
```

**Key Parameters**:
- `region`: Country code (IN, US, etc.)
- `published_after`: ISO 8601 date
- `published_before`: ISO 8601 date
- `min_subscribers`: Minimum channel size

### Stage 2: Transcript Extraction
**File**: `youtube_fetcher.py`

**Functionality**:
- Download transcripts from YouTube
- Support English + Hindi (auto-detected)
- Handle missing transcripts gracefully
- Cache transcripts to avoid re-fetches

**Output**:
```json
{
  "video_id": "abc123",
  "transcript": "Full text of video content...",
  "language": "en",
  "length_minutes": 15
}
```

**Language Support**:
- English: Direct extraction
- Hindi: Auto-translated to English
- Others: Fallback to available options

### Stage 3: Transcript Cleaning
**File**: `transcript_handler.py`

**Functionality**:
- Remove timestamps and metadata
- Normalize whitespace
- Fix encoding issues
- Detect language

**Output**:
```json
{
  "video_id": "abc123",
  "transcript": "Cleaned full transcript...",
  "language": "en",
  "word_count": 2500
}
```

### Stage 4: AI Summarization
**File**: `summarizer.py`

**Functionality**:
- Call OpenAI GPT to extract predictions
- Request structured JSON output
- Parse financial predictions
- Handle fallback if JSON parsing fails
- Cache summaries

**Prompt Structure**:
```
Extract key predictions in JSON format:
{
  "predictions": [
    {
      "prediction": "Text of prediction",
      "confidence": 0.75,
      "timeframe": "2026",
      "area": "Stock Market"
    }
  ]
}
```

**Output**:
```json
{
  "predictions": [
    {"prediction": "...", "confidence": 0.8, "timeframe": "2026"}
  ],
  "parse_error": false
}
```

### Stage 5: Prediction Extraction
**File**: `analyzer.py`

**Functionality**:
- Flatten predictions from summaries
- Add source metadata
- Normalize prediction text
- Create unified prediction list

**Output**:
```
69 predictions extracted from 14 videos
Each with source, confidence, timeframe
```

### Stage 6: Consolidation
**File**: `analyzer.py`

**Functionality**:
- Extract financial keywords from each prediction
- Calculate similarity using:
  - Keyword overlap (60% weight)
  - Word-level Jaccard similarity (40% weight)
- Group predictions above 0.35 threshold
- Consolidate to unique themes

**Output**:
```
17 consolidated themes
9 multi-source themes (3+ videos)
8 single-source themes
```

### Stage 7: Confidence Calculation
**File**: `analyzer.py`

**Scoring Formula**:
```
Confidence = (Diversity × 0.4) + (Credibility × 0.3) + (AI × 0.3)

Where:
- Diversity = num_sources / total_videos
- Credibility = avg(channel_subscribers) / 10M  (capped at 1.0)
- AI = average OpenAI confidence in theme
```

**Example**:
```
Defense Sector Growth (11 videos):
- Diversity: 11/15 = 0.73
- Credibility: 2M avg / 10M = 0.20
- AI: 0.82 (high predictions)
- Total: (0.73×0.4) + (0.20×0.3) + (0.82×0.3) = 0.65 (65%)
```

### Stage 8: Report Generation
**File**: `main.py`

**Output Files**:
- `reports/analysis_report.md` - Markdown format
- `reports/analysis_report.json` - JSON format
- Both include full source attribution

---

## Data Flow

### Information Flow Diagram
```
Raw YouTube Videos
    ↓
Search & Filter (region, date, subscribers)
    ↓
[15 videos] → Extract transcripts
    ↓
[14 transcripts] → Detect language → Translate if needed
    ↓
[14 cleaned] → AI summarization → Extract predictions
    ↓
[69 raw predictions] → Extract keywords
    ↓
Similarity matching (Keyword 60% + Words 40%)
    ↓
[17 groups] → Calculate confidence
    ↓
[17 consolidated] → Generate reports
    ↓
Reports & JSON output
```

### Caching Strategy
```
Caches (prevent re-fetches):
├─ transcripts_cache.json (1MB) → Transcript extraction
├─ summaries_cache.json (81KB) → AI summarization
└─ videos_metadata.json (7.5KB) → Video search

Cleared when:
- User explicitly runs with --no-cache
- Modifying analyzer parameters
- Update to promptTemplates
```

---

## Key Components

### YouTubeFetcher
**Responsibility**: Video search and transcript extraction

**Key Methods**:
- `search()`: Find videos matching query + filters
- `get_transcript()`: Extract transcript text
- `_detect_language()`: Identify text language
- `_translate_hindi_to_english()`: Translation

**Dependencies**: youtube-transcript-api, google-api-client

### TranscriptSummarizer
**Responsibility**: AI-powered analysis and summarization

**Key Methods**:
- `summarize_transcript()`: Call OpenAI for extraction
- `batch_summarize()`: Process multiple transcripts
- `_call_openai()`: Make API call with retry logic
- `_translate_hindi_to_english()`: For unsummarized Hindi

**Dependencies**: openai, tenacity

### PredictionAnalyzer
**Responsibility**: Extract, group, and consolidate predictions

**Key Methods**:
- `extract_predictions()`: Flatten predictions from summaries
- `extract_keywords()`: Identify financial terms
- `calculate_similarity()`: Compare predictions
- `group_similar_predictions()`: Create groups
- `consolidate_predictions()`: Final aggregation
- `calculate_confidence()`: Score each theme

**Key Parameters**:
```python
ANALYZER_CONFIG = {
    "min_confidence_threshold": 0.5,
    "similarity_threshold": 0.35,  # Keyword-based
    "min_occurrences": 1,
}
```

### TranscriptHandler
**Responsibility**: Text preprocessing

**Key Methods**:
- `clean_transcript()`: Remove artifacts
- `detect_language()`: Identify language
- `normalize_text()`: Standardize format

---

## Confidence Scoring Algorithm

### Multi-Factor Model
```
Total Confidence = 
    (Diversity Factor × 0.40) +
    (Credibility Factor × 0.30) +
    (AI Confidence × 0.30)
```

### Factor 1: Diversity (40%)
Measures how many different videos mention theme
```
Diversity = (Number of Source Videos) / (Total Videos Analyzed)

Example: 
- 11 videos mention defense sector
- 15 videos analyzed
- Diversity = 11/15 = 0.73
```

### Factor 2: Credibility (30%)
Based on average channel subscriber count
```
Credibility = avg(subscriber_counts) / 10,000,000 (capped at 1.0)

Example:
- Channels: CNBC (2.5M), ABP (14M), AstroKapoor (85K)
- Average: (2.5M + 14M + 85K) / 3 = 5.5M
- Credibility = 5.5M / 10M = 0.55
```

### Factor 3: AI Confidence (30%)
Average OpenAI confidence from predictions
```
AI Confidence = average of all confidence scores in group

Example:
- Predictions: 0.82, 0.78, 0.80, 0.85
- Average: (0.82 + 0.78 + 0.80 + 0.85) / 4 = 0.81
```

### Consolidation Multiplier
Multi-source predictions get weighted bonus:
```
If num_sources >= 3:
    final_confidence *= 1.0  (no penalty)
Else:
    final_confidence *= 0.85 (single-source discount)
```

---

## Extension Points

### Adding New Data Sources
1. Create new fetcher class
2. Implement same interface as YouTubeFetcher
3. Add to main.py pipeline

### Adding New Summarization Provider
1. Replace OpenAI with alternative
2. Update `summarizer.py`
3. Adjust prompt template if needed

### Customizing Similarity Matching
1. Modify `extract_keywords()` for domain
2. Adjust `similarity_threshold` in config
3. Update keyword categories

### Custom Report Formats
1. Modify report generation in `analyzer.py`
2. Add new export format
3. Update main.py to call new formatter

---

## Performance Characteristics

| Stage | Time | API Calls |
|-------|------|-----------|
| YouTube Search | 1s | 1 |
| Fetch Transcripts (14) | 20s | 14 |
| Translate (14) | 45s | ~8 (cached) |
| Summarize (14) | 120s | 14 |
| Analyze | 2s | 0 |
| Generate Reports | 1s | 0 |
| **Total** | **~3min** | **~37** |

### Resource Usage
- Memory: ~500MB (moderate)
- Disk: 10MB for data (minimal)
- Network: 5-10 MB (mostly transcripts)

---

## Related Resources
- [Quick Start Guide](PREDICTION_ANALYZER_QUICKSTART.md) - Getting started
- [Usage Guide](PREDICTION_ANALYZER_USAGE_GUIDE.md) - Parameter reference
- [Main README](../../astro-prediction-analyzer/README.md) - Module overview
