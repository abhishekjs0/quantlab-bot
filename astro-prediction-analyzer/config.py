"""
Configuration for YouTube Video Analyzer
Focus: Economics, Finance, Geopolitics, World Events, Stock Markets
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# API Keys
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")

# YouTube Configuration
YOUTUBE_CONFIG = {
    "max_results_per_search": 50,
    "search_region": "US",  # Global focus
    "search_language": "en",
    "video_duration": "medium",  # medium, long, short
}

# OpenAI Configuration
OPENAI_CONFIG = {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000,  # Increased to capture detailed predictions with specific numbers, sectors, countries, timeframes
    "timeout": 30,
}

# Translation Configuration
TRANSLATION_CONFIG = {
    "source_language": "auto",  # Auto-detect
    "target_language": "en",
}

# Summarization prompts
SUMMARIZATION_PROMPT = """You are an expert financial analyst and geopolitical strategist. Analyze the following video transcript about finance, economics, world events, or stock markets.

Extract DETAILED predictions and insights:

1. **Key Predictions**: Specific predictions about markets, economies, or events
   - Be VERY DETAILED - include specific numbers, timeframes, and conditions
   - Include sector/company mentions where relevant
   - Note confidence level (high/medium/low)

2. **Economic Indicators**: Mention of inflation, GDP, interest rates, commodities
   
3. **Market Implications**: Impact on stocks, currencies, bonds, commodities
   
4. **Geopolitical Factors**: Global events, trade, political risks
   
5. **Timeline**: When are these events/changes expected?
   
6. **Key Risks**: What could go wrong?

Format your response as JSON with these fields:
{
  "predictions": [
    {
      "prediction": "Detailed specific prediction",
      "category": "stocks|crypto|forex|commodities|economics|geopolitics",
      "affected_sectors": ["sector1", "sector2"],
      "affected_countries": ["country1", "country2"],
      "confidence": 0.0-1.0,
      "timeframe": "when this occurs",
      "specific_details": "detailed numbers, percentages, specific assets",
      "risks": ["risk1", "risk2"]
    }
  ],
  "key_themes": ["theme1", "theme2"],
  "speaker_expertise": "assessment of speaker's expertise (1-10)",
  "speaker_track_record": "any mention of past predictions accuracy"
}

Be extremely detailed and specific. Include numbers, percentages, stock symbols where mentioned."""

# Common predictions analyzer config
ANALYZER_CONFIG = {
    "min_confidence_threshold": 0.5,  # Lower threshold for predictions
    "similarity_threshold": 0.35,  # Lower for keyword-based grouping across similar themes
    "min_occurrences": 1,  # Even single mentions are valuable in finance
}

# Cache settings
CACHE_CONFIG = {
    "cache_transcripts": True,
    "cache_summaries": True,
    "cache_dir": DATA_DIR / "cache",
}

# Batch processing
BATCH_CONFIG = {
    "batch_size": 5,
    "delay_between_requests": 1.0,  # seconds
}

# Validation
VALIDATION_CONFIG = {
    "min_transcript_length": 100,  # characters
    "max_transcript_length": 100000,
}

# Report generation
REPORT_CONFIG = {
    "include_raw_data": True,
    "include_individual_summaries": True,
    "min_confidence_for_report": 0.65,
}

# Ensure cache directory exists
if CACHE_CONFIG["cache_dir"]:
    CACHE_CONFIG["cache_dir"].mkdir(exist_ok=True, parents=True)
