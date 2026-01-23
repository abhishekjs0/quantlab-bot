"""
AI-powered transcript summarization module
"""
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    OPENAI_API_KEY,
    OPENAI_CONFIG,
    SUMMARIZATION_PROMPT,
    DATA_DIR,
    BATCH_CONFIG,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TranscriptSummarizer:
    """Summarizes transcripts using OpenAI API"""

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_CONFIG["model"]
        self.summaries_cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cached summaries if available"""
        cache_file = DATA_DIR / "summaries_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {}

    def _save_cache(self):
        """Save summaries cache"""
        cache_file = DATA_DIR / "summaries_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.summaries_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save cache: {e}")

    def _detect_language(self, text: str) -> str:
        """
        Detect if text is in Hindi or English
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code: 'hi' or 'en'
        """
        # Simple check: count Devanagari script characters (Hindi)
        devanagari_count = sum(1 for char in text if '\u0900' <= char <= '\u097F')
        total_chars = len([c for c in text if ord(c) > 127])  # non-ASCII
        
        if total_chars > 0 and devanagari_count / total_chars > 0.5:
            return 'hi'
        return 'en'

    def _translate_hindi_to_english(self, text: str) -> str:
        """
        Translate Hindi text to English using OpenAI
        
        Args:
            text: Hindi text to translate
            
        Returns:
            Translated English text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate the following Hindi text to English. Preserve all factual information, numbers, and names.",
                    },
                    {
                        "role": "user",
                        "content": f"Translate this Hindi text to English:\n\n{text}",
                    },
                ],
                temperature=0.3,  # Lower temperature for more accurate translation
                max_tokens=4000,
                timeout=OPENAI_CONFIG["timeout"],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Translation failed: {e}. Using original text.")
            return text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openai(self, prompt: str) -> str:
        """
        Call OpenAI API with retry logic (v1.0+ compatible)
        
        Args:
            prompt: The prompt to send to API
            
        Returns:
            API response text
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst and geopolitical strategist specializing in market insights and economic predictions.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=OPENAI_CONFIG["temperature"],
            max_tokens=OPENAI_CONFIG["max_tokens"],
            timeout=OPENAI_CONFIG["timeout"],
        )
        
        return response.choices[0].message.content

    def summarize_transcript(
        self,
        video_id: str,
        transcript: str,
        title: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Dict:
        """
        Summarize a single transcript
        
        Args:
            video_id: YouTube video ID
            transcript: Full transcript text
            title: Video title (for context)
            channel: Channel name (for context)
            
        Returns:
            Dict with original and summarized data
        """
        # Check cache first
        if video_id in self.summaries_cache:
            logger.info(f"Using cached summary for {video_id}")
            return self.summaries_cache[video_id]
        
        try:
            logger.info(f"Summarizing transcript for {video_id}")
            
            # Detect language and translate if needed
            detected_lang = self._detect_language(transcript)
            if detected_lang == 'hi':
                logger.info(f"Hindi text detected for {video_id}, translating to English...")
                transcript = self._translate_hindi_to_english(transcript)
            
            # Build prompt with context
            context = f"Video: {title}\nChannel: {channel}\n\n" if title else ""
            full_prompt = f"{context}Transcript:\n{transcript}\n\n{SUMMARIZATION_PROMPT}"
            
            # Call API
            summary_text = self._call_openai(full_prompt)
            
            # Parse JSON from response
            try:
                summary_data = json.loads(summary_text)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON from response, using raw text")
                summary_data = {
                    "raw_summary": summary_text,
                    "parse_error": True,
                }
            
            # Build result
            result = {
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "summary": summary_data,
                "tokens_used": len(transcript.split()) + len(summary_text.split()),
            }
            
            # Cache it
            self.summaries_cache[video_id] = result
            self._save_cache()
            
            return result
            
        except Exception as e:
            logger.error(f"Error summarizing {video_id}: {e}")
            return {
                "video_id": video_id,
                "error": str(e),
                "title": title,
                "channel": channel,
            }

    def batch_summarize(
        self,
        transcripts: List[Dict],
        delay: Optional[float] = None,
    ) -> List[Dict]:
        """
        Summarize multiple transcripts with rate limiting
        
        Args:
            transcripts: List of transcript dicts
            delay: Delay between requests (seconds)
            
        Returns:
            List of summarized dicts
        """
        import time
        
        delay = delay or BATCH_CONFIG["delay_between_requests"]
        results = []
        
        for idx, item in enumerate(transcripts):
            logger.info(f"Summarizing {idx + 1}/{len(transcripts)}")
            
            result = self.summarize_transcript(
                video_id=item.get("video_id"),
                transcript=item.get("transcript", ""),
                title=item.get("title"),
                channel=item.get("channel"),
            )
            
            results.append(result)
            
            # Rate limiting (except for last item)
            if idx < len(transcripts) - 1:
                time.sleep(delay)
        
        logger.info(f"Completed summarizing {len(results)} transcripts")
        return results

    def save_summaries(
        self,
        summaries: List[Dict],
        filename: str = "summaries.json",
    ):
        """Save summaries to file"""
        output_path = DATA_DIR / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(summaries, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved summaries to {output_path}")
        except Exception as e:
            logger.error(f"Could not save: {e}")

    def extract_predictions_from_summary(self, summary: Dict) -> List[Dict]:
        """
        Extract structured predictions from a summary
        
        Args:
            summary: Summary dict with parsed JSON
            
        Returns:
            List of prediction objects
        """
        predictions = []
        
        try:
            summary_data = summary.get("summary", {})
            if isinstance(summary_data, dict):
                predictions = summary_data.get("predictions", [])
        except Exception as e:
            logger.warning(f"Could not extract predictions: {e}")
        
        return predictions


if __name__ == "__main__":
    summarizer = TranscriptSummarizer()
    
    # Example: summarize a sample transcript
    sample_transcript = """
    In 2026, we will see significant changes in the financial sector...
    People born under Sagittarius will experience great opportunities...
    The year starts with Mercury retrograde affecting communication...
    """
    
    result = summarizer.summarize_transcript(
        video_id="sample_video",
        transcript=sample_transcript,
        title="2026 Predictions",
        channel="Astro Channel",
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
