#!/usr/bin/env python3
"""
Test script to verify all API connections and dependencies
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def test_imports():
    """Test all required imports"""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING IMPORTS")
    logger.info("=" * 80 + "\n")
    
    try:
        logger.info("✓ Importing config...")
        from config import YOUTUBE_API_KEY, OPENAI_API_KEY
        
        logger.info("✓ Importing youtube_fetcher...")
        from youtube_fetcher import YouTubeFetcher
        
        logger.info("✓ Importing transcript_handler...")
        from transcript_handler import TranscriptHandler
        
        logger.info("✓ Importing summarizer...")
        from summarizer import TranscriptSummarizer
        
        logger.info("✓ Importing analyzer...")
        from analyzer import PredictionAnalyzer
        
        logger.info("✓ All imports successful!\n")
        return True
    except Exception as e:
        logger.error(f"✗ Import failed: {e}\n")
        return False

def test_env_vars():
    """Test environment variables"""
    logger.info("=" * 80)
    logger.info("TESTING ENVIRONMENT VARIABLES")
    logger.info("=" * 80 + "\n")
    
    try:
        from config import YOUTUBE_API_KEY, OPENAI_API_KEY
        
        if not YOUTUBE_API_KEY:
            logger.error("✗ YOUTUBE_API_KEY not set")
            return False
        logger.info(f"✓ YOUTUBE_API_KEY: {YOUTUBE_API_KEY[:20]}...")
        
        if not OPENAI_API_KEY:
            logger.error("✗ OPENAI_API_KEY not set")
            return False
        logger.info(f"✓ OPENAI_API_KEY: {OPENAI_API_KEY[:20]}...")
        
        logger.info("✓ All environment variables set!\n")
        return True
    except Exception as e:
        logger.error(f"✗ Environment check failed: {e}\n")
        return False

def test_youtube_connection():
    """Test YouTube API connection"""
    logger.info("=" * 80)
    logger.info("TESTING YOUTUBE API")
    logger.info("=" * 80 + "\n")
    
    try:
        from youtube_fetcher import YouTubeFetcher
        
        logger.info("Initializing YouTubeFetcher...")
        fetcher = YouTubeFetcher()
        
        logger.info("Searching for test videos (finance topic)...")
        videos = fetcher.search("stock market analysis", max_results=3)
        
        if not videos:
            logger.error("✗ No videos found in search")
            return False
        
        logger.info(f"✓ Found {len(videos)} videos")
        for video in videos[:2]:
            logger.info(f"  - {video['title'][:60]}... ({video['channel']})")
        
        logger.info("✓ YouTube API connection successful!\n")
        return True
    except Exception as e:
        logger.error(f"✗ YouTube API test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def test_openai_connection():
    """Test OpenAI API connection"""
    logger.info("=" * 80)
    logger.info("TESTING OPENAI API")
    logger.info("=" * 80 + "\n")
    
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        logger.info("Testing OpenAI connection with simple prompt...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Say 'API works' in one word."}
            ],
            temperature=0.5,
            max_tokens=10,
        )
        
        result = response.choices[0].message.content.strip()
        logger.info(f"✓ OpenAI response: '{result}'")
        logger.info("✓ OpenAI API connection successful!\n")
        return True
    except Exception as e:
        logger.error(f"✗ OpenAI API test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def test_transcript_extraction():
    """Test transcript extraction from a real video"""
    logger.info("=" * 80)
    logger.info("TESTING TRANSCRIPT EXTRACTION")
    logger.info("=" * 80 + "\n")
    
    try:
        from youtube_fetcher import YouTubeFetcher
        
        logger.info("Searching for first test video...")
        fetcher = YouTubeFetcher()
        videos = fetcher.search("stock market", max_results=1)
        
        if not videos:
            logger.error("✗ No videos found")
            return False
        
        video = videos[0]
        logger.info(f"Extracting transcript from: {video['title'][:60]}...")
        
        transcript = fetcher.get_transcript(video['video_id'])
        
        if not transcript:
            logger.error("✗ Could not extract transcript (video may not have one)")
            return False
        
        logger.info(f"✓ Successfully extracted transcript ({len(transcript)} characters)")
        logger.info(f"✓ First 100 chars: {transcript[:100]}...\n")
        return True
    except Exception as e:
        logger.error(f"✗ Transcript extraction failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "YOUTUBE VIDEO ANALYZER - SETUP TEST".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    
    results = {}
    
    # Run tests
    results["imports"] = test_imports()
    results["env_vars"] = test_env_vars()
    results["youtube"] = test_youtube_connection()
    results["openai"] = test_openai_connection()
    results["transcripts"] = test_transcript_extraction()
    
    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80 + "\n")
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✓ ALL TESTS PASSED - SETUP IS READY!")
        logger.info("=" * 80 + "\n")
        logger.info("You can now run:")
        logger.info("  python main.py --search 'topic' --videos 5")
        logger.info("=" * 80 + "\n")
        return 0
    else:
        logger.info("✗ SOME TESTS FAILED - SEE ABOVE FOR DETAILS")
        logger.info("=" * 80 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
