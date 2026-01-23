#!/usr/bin/env python3
"""
Main orchestration script for YouTube Video Analyzer
Analyzes videos on economics, finance, geopolitics, world events, stock markets
"""
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from youtube_fetcher import YouTubeFetcher
from transcript_handler import TranscriptHandler
from summarizer import TranscriptSummarizer
from analyzer import PredictionAnalyzer
from config import DATA_DIR, REPORTS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def generate_markdown_report(
    consolidated_predictions: list,
    themes: dict,
    original_videos: list,
) -> str:
    """Generate markdown formatted report"""
    
    report = f"""# Video Analysis Report - Finance & Economics Insights

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

- **Total Videos Analyzed**: {len(original_videos)}
- **Total Insights Extracted**: {themes.get('total_predictions', 0)}
- **High-Confidence Insights**: {len(consolidated_predictions)}
- **Average Confidence Score**: {themes.get('average_confidence', 0):.2f}

---

## Top Focus Areas

"""
    
    for area, count in themes.get("top_areas", []):
        report += f"- **{area.title()}**: {count} mentions\n"
    
    report += "\n## Most Affected Countries/Sectors\n\n"
    for region, count in themes.get("top_zodiac_signs", [])[:10]:  # Repurposed field
        report += f"- **{region}**: {count} mentions\n"
    
    report += "\n---\n\n## Key Predictions & Insights\n\n"
    
    for idx, pred in enumerate(consolidated_predictions, 1):
        report += f"### {idx}. {pred['prediction']}\n\n"
        report += f"**Confidence**: {pred['confidence']:.0%}\n"
        report += f"**Sources**: {pred['num_sources']} video(s)\n"
        
        if pred.get("areas_mentioned"):
            report += f"**Categories**: {', '.join(pred['areas_mentioned'])}\n"
        
        if pred.get("zodiac_signs"):  # Repurposed for sectors/countries
            report += f"**Affected**: {', '.join(pred['zodiac_signs'])}\n"
        
        if pred.get("timeframes"):
            report += f"**Timeframe**: {', '.join(pred['timeframes'])}\n"
        
        report += f"**Average Source Credibility**: {pred['average_credibility']}/10\n"
        
        if pred.get("source_videos"):
            report += "\n**Mentioned in**:\n"
            for source in pred["source_videos"]:
                report += f"- [{source['title']}](https://youtube.com/watch?v={source['video_id']}) by {source['channel']}\n"
        
        report += "\n"
    
    return report


def run_full_pipeline(
    search_query: str,
    num_videos: int = 20,
    min_confidence: float = 0.5,
    region: str = "US",
    published_after: Optional[str] = None,
    published_before: Optional[str] = None,
    min_subscribers: int = 0,
) -> dict:
    """
    Run complete analysis pipeline
    
    Args:
        search_query: YouTube search query
        num_videos: Number of videos to fetch
        min_confidence: Minimum confidence threshold
        
    Returns:
        Analysis results dict
    """
    logger.info("=" * 80)
    logger.info("YOUTUBE VIDEO ANALYZER - FULL PIPELINE")
    logger.info("=" * 80)
    
    # Step 1: Search YouTube
    logger.info("\n[1/5] Searching YouTube...")
    fetcher = YouTubeFetcher()
    videos = fetcher.search(
        search_query,
        max_results=num_videos,
        region=region,
        published_after=published_after,
        published_before=published_before,
        min_subscribers=min_subscribers,
    )
    
    if not videos:
        logger.error("No videos found")
        return {}
    
    logger.info(f"Found {len(videos)} videos")
    fetcher.save_videos_metadata(videos)
    
    # Step 2: Extract transcripts
    logger.info("\n[2/5] Extracting transcripts...")
    transcripts = fetcher.get_transcripts(videos)
    
    if not transcripts:
        logger.error("No transcripts extracted")
        return {}
    
    logger.info(f"Extracted {len(transcripts)} transcripts")
    fetcher.save_transcripts(transcripts)
    
    # Step 3: Process transcripts (clean, translate)
    logger.info("\n[3/5] Processing transcripts (clean, translate)...")
    handler = TranscriptHandler()
    processed = handler.process_batch(transcripts)
    handler.save_processed_transcripts(processed)
    
    # Step 4: Summarize transcripts
    logger.info("\n[4/5] Summarizing transcripts with AI...")
    summarizer = TranscriptSummarizer()
    summaries = summarizer.batch_summarize(processed)
    summarizer.save_summaries(summaries)
    
    # Step 5: Analyze and consolidate
    logger.info("\n[5/5] Analyzing insights and consolidating...")
    analyzer = PredictionAnalyzer()
    analysis_result = analyzer.analyze(summaries)
    
    # Generate reports
    logger.info("\nGenerating reports...")
    
    consolidated = analysis_result.get("predictions", [])
    themes = analysis_result.get("themes", {})
    
    # Save JSON report
    report_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "search_query": search_query,
            "num_videos_analyzed": len(videos),
            "num_transcripts": len(transcripts),
            "num_summaries": len(summaries),
        },
        "analysis": {
            "predictions": consolidated,
            "themes": themes,
        },
    }
    
    report_path = REPORTS_DIR / "analysis_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON report: {report_path}")
    
    # Save Markdown report
    md_report = generate_markdown_report(consolidated, themes, videos)
    md_path = REPORTS_DIR / "analysis_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    logger.info(f"Saved Markdown report: {md_path}")
    
    logger.info("\n" + "=" * 80)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 80)
    
    return analysis_result
    
    # Step 1: Search YouTube
    logger.info("\n[1/5] Searching YouTube...")
    fetcher = YouTubeFetcher()
    videos = fetcher.search(search_query, max_results=num_videos)
    
    if not videos:
        logger.error("No videos found")
        return {}
    
    logger.info(f"Found {len(videos)} videos")
    fetcher.save_videos_metadata(videos)
    
    # Step 2: Extract transcripts
    logger.info("\n[2/5] Extracting transcripts...")
    transcripts = fetcher.get_transcripts(videos)
    
    if not transcripts:
        logger.error("No transcripts extracted")
        return {}
    
    logger.info(f"Extracted {len(transcripts)} transcripts")
    fetcher.save_transcripts(transcripts)
    
    # Step 3: Process transcripts (clean, translate)
    logger.info("\n[3/5] Processing transcripts (clean, translate)...")
    handler = TranscriptHandler()
    processed = handler.process_batch(transcripts)
    handler.save_processed_transcripts(processed)
    
    # Step 4: Summarize transcripts
    logger.info("\n[4/5] Summarizing transcripts with AI...")
    summarizer = TranscriptSummarizer()
    summaries = summarizer.batch_summarize(processed)
    summarizer.save_summaries(summaries)
    
    # Step 5: Analyze and consolidate
    logger.info("\n[5/5] Analyzing predictions and consolidating...")
    analyzer = PredictionAnalyzer()
    analysis_result = analyzer.analyze(summaries)
    
    # Generate reports
    logger.info("\nGenerating reports...")
    
    consolidated = analysis_result.get("predictions", [])
    themes = analysis_result.get("themes", {})
    
    # Save JSON report
    report_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "search_query": search_query,
            "num_videos_analyzed": len(videos),
            "num_transcripts": len(transcripts),
            "num_summaries": len(summaries),
        },
        "analysis": {
            "predictions": consolidated,
            "themes": themes,
        },
    }
    
    report_path = REPORTS_DIR / "analysis_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON report: {report_path}")
    
    # Save Markdown report
    md_report = generate_markdown_report(consolidated, themes, videos)
    md_path = REPORTS_DIR / "analysis_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    logger.info(f"Saved Markdown report: {md_path}")
    
    logger.info("\n" + "=" * 80)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 80)
    
    return analysis_result


def main():
    parser = argparse.ArgumentParser(
        description="Analyze YouTube videos on finance, economics, geopolitics",
    )
    
    parser.add_argument(
        "--search",
        type=str,
        default="stock market predictions 2026",
        help="YouTube search query",
    )
    
    parser.add_argument(
        "--videos",
        type=int,
        default=20,
        help="Number of videos to fetch",
    )
    
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence threshold for predictions",
    )
    
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch transcripts, don't summarize/analyze",
    )
    
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Only summarize existing transcripts",
    )
    
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze existing summaries",
    )
    
    parser.add_argument(
        "--region",
        type=str,
        default="US",
        help="Search region (US, GB, IN, CA, AU, etc.)",
    )
    
    parser.add_argument(
        "--after",
        type=str,
        default=None,
        help="Published after date (YYYY-MM-DD format)",
    )
    
    parser.add_argument(
        "--before",
        type=str,
        default=None,
        help="Published before date (YYYY-MM-DD format)",
    )
    
    parser.add_argument(
        "--min-subscribers",
        type=int,
        default=0,
        help="Minimum channel subscribers filter",
    )
    
    args = parser.parse_args()
    
    # Run appropriate pipeline
    if args.fetch_only:
        logger.info("Running fetch-only mode...")
        fetcher = YouTubeFetcher()
        videos = fetcher.search(args.search, max_results=args.videos)
        transcripts = fetcher.get_transcripts(videos)
        fetcher.save_videos_metadata(videos)
        fetcher.save_transcripts(transcripts)
        logger.info(f"Extracted {len(transcripts)} transcripts")
        
    elif args.summarize_only:
        logger.info("Running summarize-only mode...")
        transcripts_file = DATA_DIR / "processed_transcripts.json"
        if not transcripts_file.exists():
            logger.error("No processed transcripts found")
            return
        
        with open(transcripts_file) as f:
            transcripts = json.load(f)
        
        summarizer = TranscriptSummarizer()
        summaries = summarizer.batch_summarize(transcripts)
        summarizer.save_summaries(summaries)
        logger.info(f"Summarized {len(summaries)} transcripts")
        
    elif args.analyze_only:
        logger.info("Running analyze-only mode...")
        summaries_file = DATA_DIR / "summaries.json"
        if not summaries_file.exists():
            logger.error("No summaries found")
            return
        
        with open(summaries_file) as f:
            summaries = json.load(f)
        
        analyzer = PredictionAnalyzer()
        result = analyzer.analyze(summaries)
        logger.info(f"Analyzed {len(result.get('predictions', []))} high-confidence predictions")
    
    else:
        # Full pipeline
        run_full_pipeline(
            search_query=args.search,
            num_videos=args.videos,
            min_confidence=args.min_confidence,
            region=args.region,
            published_after=args.after,
            published_before=args.before,
            min_subscribers=args.min_subscribers,
        )


if __name__ == "__main__":
    main()
