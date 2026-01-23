# Astro Prediction Analyzer 2026

A tool to search, analyze, and consolidate 2026 astrological predictions from YouTube videos.

## Features

- 🎥 YouTube video search for 2026 astrological predictions
- 🎤 Automatic transcript extraction
- 🌐 Hindi to English translation support
- 🤖 AI-powered transcript summarization
- 📊 Common prediction extraction and confidence scoring
- 📈 Consolidated reports with prediction trends

## Project Structure

```
astro-prediction-analyzer/
├── config.py                  # Configuration and API keys
├── youtube_fetcher.py         # YouTube search & transcript extraction
├── transcript_handler.py       # Transcript processing and translation
├── summarizer.py              # AI-powered summarization
├── analyzer.py                # Common points extraction & analysis
├── main.py                    # Main orchestration script
├── requirements.txt           # Python dependencies
├── data/                      # Cache and raw data
├── reports/                   # Generated analysis reports
└── README.md                  # This file
```

## Requirements

### API Keys Needed

1. **YouTube Data API** - Get from [Google Cloud Console](https://console.cloud.google.com/)
2. **OpenAI API** - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
3. **Translation API** (Optional) - Google Translate API or alternatives

### Python Dependencies

- `youtube-transcript-api` - Extract video transcripts
- `google-auth-oauthlib` - YouTube API authentication
- `google-api-python-client` - YouTube search
- `openai` - LLM for summarization
- `google-cloud-translate` - Hindi to English translation
- `pandas` - Data processing
- `python-dotenv` - Environment variable management

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file with API keys:
```env
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
GOOGLE_TRANSLATE_API_KEY=your_translate_key
```

3. Run the pipeline:
```bash
python main.py --search-term "2026 astrological predictions" --num-videos 20
```

## Usage

### Search and Extract Transcripts
```python
from youtube_fetcher import YouTubeFetcher

fetcher = YouTubeFetcher()
videos = fetcher.search("2026 astrology predictions", max_results=10)
transcripts = fetcher.get_transcripts(videos)
```

### Summarize Transcripts
```python
from summarizer import TranscriptSummarizer

summarizer = TranscriptSummarizer()
summaries = summarizer.batch_summarize(transcripts)
```

### Extract Common Predictions
```python
from analyzer import PredictionAnalyzer

analyzer = PredictionAnalyzer()
common_predictions = analyzer.extract_common_points(summaries, min_confidence=0.6)
```

## Output

- `reports/predictions_raw.json` - All extracted predictions
- `reports/predictions_summary.md` - Formatted summary
- `reports/confidence_matrix.json` - Prediction confidence scores
- `reports/common_themes.md` - Consolidated high-confidence predictions

## Command Line Usage

```bash
# Full pipeline
python main.py --search "2026 predictions" --videos 20 --min-confidence 0.6

# Only extract transcripts
python main.py --fetch-only --search "2026 predictions" --videos 10

# Only summarize existing transcripts
python main.py --summarize-only

# Analyze existing summaries
python main.py --analyze-only --min-confidence 0.7
```

## Supported Languages

- English (native)
- Hindi (auto-translated to English)
- Other Indian languages via Google Translate

## Notes

- Transcripts are cached to avoid repeated API calls
- Large summaries are split into chunks for processing
- Confidence scores based on agreement across multiple videos
- Reports are generated in JSON and Markdown formats
