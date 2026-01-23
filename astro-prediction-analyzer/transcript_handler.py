"""
Transcript processing and translation module
"""
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

import langdetect

from config import (
    DATA_DIR,
    TRANSLATION_CONFIG,
    VALIDATION_CONFIG,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TranscriptHandler:
    """Handles transcript processing, cleaning, and translation"""

    def __init__(self):
        self.translator = None
        try:
            # Optional: Initialize Google Translate if credentials available
            from google.cloud import translate_v3
            self.translator = translate_v3.TranslationServiceClient()
            logger.info("Google Translate initialized")
        except Exception:
            logger.warning("Google Translate not available, will use alternative method")
            self.translator = None

    def detect_language(self, text: str) -> str:
        """
        Detect language of text
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (e.g., 'hi', 'en')
        """
        try:
            lang = langdetect.detect(text)
            return lang
        except Exception as e:
            logger.warning(f"Could not detect language: {e}")
            return "unknown"

    def clean_transcript(self, transcript: str) -> str:
        """
        Clean and normalize transcript text
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Cleaned transcript
        """
        # Remove extra whitespace
        text = " ".join(transcript.split())
        
        # Remove common artifacts
        artifacts = [
            "[Music]",
            "[Applause]",
            "[Laughter]",
            "[Silence]",
            "[Background noise]",
            "♪",
        ]
        
        for artifact in artifacts:
            text = text.replace(artifact, "")
        
        # Clean up spacing again
        text = " ".join(text.split())
        
        return text

    def translate_to_english(self, text: str, source_lang: Optional[str] = None) -> Dict:
        """
        Translate text to English if needed
        
        Args:
            text: Text to translate
            source_lang: Source language code (auto-detect if None)
            
        Returns:
            Dict with original text, detected language, translated text
        """
        # Detect language
        detected_lang = source_lang or self.detect_language(text)
        
        result = {
            "detected_language": detected_lang,
            "original_text": text,
            "translated_text": text,
            "translation_needed": detected_lang not in ["en", "unknown"],
        }
        
        # If already English or unknown, return as is
        if detected_lang in ["en", "unknown"]:
            return result
        
        # Try translation
        try:
            if self.translator:
                # Use simple approach: if not English, attempt translation via OpenAI
                try:
                    from openai import OpenAI
                    from config import OPENAI_API_KEY
                    
                    client = OpenAI(api_key=OPENAI_API_KEY)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": f"Translate the following {detected_lang} text to English. Return ONLY the translation.",
                            },
                            {"role": "user", "content": text[:2000]}  # Limit to 2000 chars
                        ],
                        temperature=0.3,
                        max_tokens=len(text.split()) + 100,
                        timeout=10,
                    )
                    result["translated_text"] = response.choices[0].message.content
                    result["translation_method"] = "openai"
                except Exception as e:
                    logger.warning(f"Translation via OpenAI failed: {e}")
                    result["translation_method"] = "skipped"
            else:
                logger.warning(f"Translation unavailable for {detected_lang}")
                result["translation_method"] = "skipped"
                
        except Exception as e:
            logger.warning(f"Translation error: {e}")
            result["translation_error"] = str(e)
        
        return result

    def validate_transcript(self, transcript: str) -> bool:
        """
        Validate transcript meets minimum quality standards
        
        Args:
            transcript: Transcript to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not transcript or len(transcript) < VALIDATION_CONFIG["min_transcript_length"]:
            logger.warning(f"Transcript too short: {len(transcript)} chars")
            return False
        
        if len(transcript) > VALIDATION_CONFIG["max_transcript_length"]:
            logger.warning(f"Transcript too long: {len(transcript)} chars")
            return False
        
        # Check for minimum number of words
        words = transcript.split()
        if len(words) < 20:
            logger.warning("Transcript has too few words")
            return False
        
        return True

    def process_batch(
        self,
        transcripts: List[Dict],
        clean: bool = True,
        translate: bool = True,
        validate: bool = True,
    ) -> List[Dict]:
        """
        Process a batch of transcripts
        
        Args:
            transcripts: List of transcript dicts with 'transcript' field
            clean: Clean transcripts
            translate: Translate to English if needed
            validate: Validate transcripts
            
        Returns:
            List of processed transcripts
        """
        processed = []
        
        for idx, item in enumerate(transcripts):
            logger.info(f"Processing transcript {idx + 1}/{len(transcripts)}")
            
            transcript = item.get("transcript", "")
            
            # Validate
            if validate and not self.validate_transcript(transcript):
                logger.warning(f"Skipping invalid transcript: {item.get('title', 'Unknown')}")
                continue
            
            # Clean
            if clean:
                transcript = self.clean_transcript(transcript)
            
            # Translate
            translation_info = None
            if translate:
                translation_info = self.translate_to_english(transcript)
                transcript = translation_info["translated_text"]
            
            # Build processed item
            processed_item = {
                **item,
                "transcript": transcript,
                "transcript_length": len(transcript),
                "word_count": len(transcript.split()),
            }
            
            if translation_info:
                processed_item["translation"] = translation_info
            
            processed.append(processed_item)
        
        logger.info(f"Processed {len(processed)}/{len(transcripts)} transcripts")
        return processed

    def chunk_transcript(self, transcript: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split long transcript into overlapping chunks
        
        Args:
            transcript: Full transcript text
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of transcript chunks
        """
        chunks = []
        start = 0
        
        while start < len(transcript):
            end = start + chunk_size
            chunk = transcript[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks

    def save_processed_transcripts(
        self,
        transcripts: List[Dict],
        filename: str = "processed_transcripts.json",
    ):
        """Save processed transcripts to file"""
        output_path = DATA_DIR / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(transcripts, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved processed transcripts to {output_path}")
        except Exception as e:
            logger.error(f"Could not save: {e}")


if __name__ == "__main__":
    handler = TranscriptHandler()
    
    # Example usage
    sample_text = "यह एक नमूना हिंदी टेक्स्ट है"
    result = handler.translate_to_english(sample_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
