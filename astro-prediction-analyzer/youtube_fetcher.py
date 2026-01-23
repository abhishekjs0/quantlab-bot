"""
YouTube video search and transcript extraction module
"""
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from tqdm import tqdm

from config import (
    YOUTUBE_API_KEY,
    YOUTUBE_CONFIG,
    DATA_DIR,
    BATCH_CONFIG,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class YouTubeFetcher:
    """Fetches YouTube videos and their transcripts"""

    def __init__(self):
        self.api_key = YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY not set in environment")
        
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        self.transcript_cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cached transcripts if available"""
        cache_file = DATA_DIR / "transcripts_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {}

    def _save_cache(self):
        """Save transcript cache"""
        cache_file = DATA_DIR / "transcripts_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.transcript_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save cache: {e}")

    def search(
        self,
        query: str,
        max_results: int = 20,
        region: Optional[str] = None,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        min_subscribers: int = 0,
    ) -> List[Dict]:
        """
        Search YouTube for videos matching query
        
        Args:
            query: Search query (e.g., "stock market analysis")
            max_results: Maximum number of results to return
            region: Region code (defaults to US)
            published_after: ISO format date (e.g., "2025-01-22")
            published_before: ISO format date (e.g., "2026-01-22")
            min_subscribers: Minimum channel subscribers (filters after search)
            
        Returns:
            List of video metadata dicts
        """
        logger.info(f"Searching YouTube for: {query}")
        
        region = region or YOUTUBE_CONFIG["search_region"]
        
        # Format dates for YouTube API (ISO 8601 with Z)
        if published_after and not published_after.endswith('Z'):
            published_after = published_after + "T00:00:00Z"
        if published_before and not published_before.endswith('Z'):
            published_before = published_before + "T23:59:59Z"
        
        try:
            request = self.youtube.search().list(
                q=query,
                type="video",
                part="snippet",
                maxResults=min(max_results, 50),
                regionCode=region,
                publishedAfter=published_after,
                publishedBefore=published_before,
                relevanceLanguage=YOUTUBE_CONFIG["search_language"],
                videoDuration=YOUTUBE_CONFIG["video_duration"],
                order="relevance",
            )
            
            response = request.execute()
            
            videos = []
            for item in response.get("items", []):
                # If min_subscribers filter is set, fetch channel stats
                if min_subscribers > 0:
                    try:
                        channel_id = item["snippet"]["channelId"]
                        channel_request = self.youtube.channels().list(
                            id=channel_id,
                            part="statistics"
                        ).execute()
                        channel_stats = channel_request.get("items", [{}])[0]
                        subscriber_count = int(channel_stats.get("statistics", {}).get("subscriberCount", 0))
                        
                        # Skip if below minimum subscriber threshold
                        if subscriber_count < min_subscribers:
                            logger.debug(f"Skipping {item['snippet']['title']} - {subscriber_count} subscribers < {min_subscribers}")
                            continue
                    except Exception as e:
                        logger.debug(f"Could not fetch channel stats: {e}")
                
                video_data = {
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "channel_id": item["snippet"]["channelId"],
                    "published_at": item["snippet"]["publishedAt"],
                    "description": item["snippet"]["description"],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                }
                videos.append(video_data)
            
            logger.info(f"Found {len(videos)} videos")
            return videos
            
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return []

    def get_transcript(self, video_id: str) -> Optional[str]:
        """
        Extract transcript from a single video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Full transcript text or None if unavailable
        """
        # Check cache first
        if video_id in self.transcript_cache:
            logger.debug(f"Using cached transcript for {video_id}")
            return self.transcript_cache[video_id]
        
        try:
            logger.info(f"Fetching transcript for {video_id}")
            # Use fetch method - create instance and call fetch
            api = YouTubeTranscriptApi()
            # Try English first, then Hindi
            transcript_data = api.fetch(video_id, languages=['en', 'hi'])
            
            # transcript_data is a FetchedTranscript with snippets attribute
            if hasattr(transcript_data, 'snippets'):
                transcript_text = " ".join([snippet.text for snippet in transcript_data.snippets])
            else:
                # Fallback if structure is different
                transcript_text = " ".join([entry.get("text", "") if hasattr(entry, 'get') else entry.text for entry in transcript_data])
            
            # Cache it
            self.transcript_cache[video_id] = transcript_text
            self._save_cache()
            
            return transcript_text
            
        except Exception as e:
            logger.warning(f"Could not get transcript for {video_id}: {e}")
            return None

    def get_transcripts(self, videos: List[Dict], include_metadata: bool = True) -> List[Dict]:
        """
        Extract transcripts for multiple videos
        
        Args:
            videos: List of video metadata dicts
            include_metadata: Include video metadata in output
            
        Returns:
            List of dicts with transcript and metadata
        """
        results = []
        
        for video in tqdm(videos, desc="Extracting transcripts"):
            video_id = video["video_id"]
            transcript = self.get_transcript(video_id)
            
            if transcript:
                result = {
                    "video_id": video_id,
                    "transcript": transcript,
                    "transcript_length": len(transcript),
                }
                
                if include_metadata:
                    result.update({
                        "title": video["title"],
                        "channel": video["channel"],
                        "published_at": video["published_at"],
                        "description": video["description"],
                    })
                
                results.append(result)
        
        logger.info(f"Successfully extracted {len(results)}/{len(videos)} transcripts")
        return results

    def save_videos_metadata(self, videos: List[Dict], filename: str = "videos_metadata.json"):
        """Save video metadata to file"""
        output_path = DATA_DIR / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(videos, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved metadata to {output_path}")
        except Exception as e:
            logger.error(f"Could not save metadata: {e}")

    def save_transcripts(self, transcripts: List[Dict], filename: str = "transcripts.json"):
        """Save transcripts to file"""
        output_path = DATA_DIR / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(transcripts, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved transcripts to {output_path}")
        except Exception as e:
            logger.error(f"Could not save transcripts: {e}")


if __name__ == "__main__":
    fetcher = YouTubeFetcher()
    
    # Search for videos
    query = "2026 astrological predictions hindi"
    videos = fetcher.search(query, max_results=5)
    
    # Get transcripts
    if videos:
        transcripts = fetcher.get_transcripts(videos)
        fetcher.save_transcripts(transcripts)
        print(f"Extracted {len(transcripts)} transcripts")
