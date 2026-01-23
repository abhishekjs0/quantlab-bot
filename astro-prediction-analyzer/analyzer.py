"""
Common prediction extraction and confidence scoring module
"""
import json
import logging
from typing import List, Dict, Optional, Set
from pathlib import Path
from collections import Counter
import re

from config import DATA_DIR, ANALYZER_CONFIG

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PredictionAnalyzer:
    """Extracts common predictions and calculates confidence scores"""

    def __init__(self):
        self.min_confidence = ANALYZER_CONFIG["min_confidence_threshold"]
        self.similarity_threshold = ANALYZER_CONFIG["similarity_threshold"]
        self.min_occurrences = ANALYZER_CONFIG["min_occurrences"]

    def extract_predictions(self, summaries: List[Dict]) -> List[Dict]:
        """
        Extract all predictions from summaries
        
        Args:
            summaries: List of summary dicts
            
        Returns:
            Flat list of all predictions with metadata
        """
        all_predictions = []
        
        for summary in summaries:
            if "error" in summary:
                logger.warning(f"Skipping summary with error: {summary.get('video_id')}")
                continue
            
            video_id = summary.get("video_id")
            title = summary.get("title")
            channel = summary.get("channel")
            
            summary_data = summary.get("summary", {})
            if not isinstance(summary_data, dict):
                continue
            
            # Handle both successfully parsed JSON and fallback raw_summary
            predictions = summary_data.get("predictions", [])
            
            # If no predictions found and there's raw_summary, try to extract from raw text
            if not predictions and "raw_summary" in summary_data:
                raw_text = summary_data.get("raw_summary", "")
                # Try to extract JSON from raw text if it's partially parsed
                try:
                    # Look for JSON-like patterns in raw text
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if json_match:
                        partial_json = json_match.group()
                        parsed = json.loads(partial_json)
                        predictions = parsed.get("predictions", [])
                except Exception as e:
                    logger.debug(f"Could not extract JSON from raw summary: {e}")
            
            for pred in predictions:
                # Ensure prediction has required fields
                if not isinstance(pred, dict):
                    continue
                    
                # Add source information
                pred["source_video_id"] = video_id
                pred["source_title"] = title
                pred["source_channel"] = channel
                all_predictions.append(pred)
        
        logger.info(f"Extracted {len(all_predictions)} total predictions from {len(summaries)} summaries")
        return all_predictions

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r"[^\w\s]", "", text)
        # Remove extra whitespace
        text = " ".join(text.split())
        return text

    def extract_keywords(self, text: str) -> Set[str]:
        """Extract key financial/market terms from text"""
        keywords = set()
        
        # Financial terms to track
        terms = {
            'gold': ['gold', 'prix', 'preciou metal', 'bullion'],
            'silver': ['silver', 'ag'],
            'stock': ['stock', 'market', 'sensex', 'nifty', 'share', 'equity'],
            'sector': ['sector', 'industry', 'fmcg', 'it', 'pharma', 'health', 'defense', 'bank', 'finance'],
            'crypto': ['bitcoin', 'crypto', 'blockchain', 'eth', 'btc'],
            'rbi': ['rbi', 'rate', 'interest', 'monetary', 'inflation', 'reserve'],
            'geopolitical': ['war', 'conflict', 'tension', 'geo', 'political', 'trade'],
            'growth': ['grow', 'rise', 'increase', 'bull', 'surge', 'boom', 'upside'],
            'decline': ['fall', 'drop', 'decline', 'bear', 'crash', 'volatile'],
            'india': ['india', 'indian', 'rupee', 'inr', 'sensex', 'nifty', 'bse', 'nse'],
        }
        
        text_lower = text.lower()
        for category, variations in terms.items():
            for variation in variations:
                if variation in text_lower:
                    keywords.add(category)
                    break
        
        return keywords

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using keyword overlap + Jaccard
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        # Extract keywords
        keywords1 = self.extract_keywords(text1)
        keywords2 = self.extract_keywords(text2)
        
        # Keyword overlap
        if keywords1 and keywords2:
            intersection = keywords1.intersection(keywords2)
            union = keywords1.union(keywords2)
            keyword_similarity = len(intersection) / len(union) if union else 0.0
        else:
            keyword_similarity = 0.0
        
        # Word-based overlap (for multi-word phrases)
        words1 = set(self.normalize_text(text1).split())
        words2 = set(self.normalize_text(text2).split())
        
        if not words1 or not words2:
            return keyword_similarity * 0.5  # Reduce weight if no words match
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        word_similarity = len(intersection) / len(union)
        
        # Combined: keywords more important for financial predictions
        combined = (keyword_similarity * 0.6) + (word_similarity * 0.4)
        return combined

    def group_similar_predictions(self, predictions: List[Dict]) -> List[List[Dict]]:
        """
        Group similar predictions together across all videos
        Uses improved text similarity and multi-pass grouping
        
        Args:
            predictions: List of prediction dicts
            
        Returns:
            List of groups, each containing similar predictions from different sources
        """
        if not predictions:
            return []
        
        groups = []
        used = set()
        
        for idx, pred in enumerate(predictions):
            if idx in used:
                continue
            
            group = [pred]
            pred_text = str(pred.get("prediction", ""))
            
            # Find all similar predictions
            for jdx, other_pred in enumerate(predictions):
                if jdx <= idx or jdx in used:
                    continue
                
                other_text = str(other_pred.get("prediction", ""))
                similarity = self.calculate_similarity(pred_text, other_text)
                
                # Lower threshold to catch more similar predictions
                if similarity >= self.similarity_threshold:
                    group.append(other_pred)
                    used.add(jdx)
            
            groups.append(group)
            used.add(idx)
        
        # Filter out single-item groups and log multi-source predictions
        multi_source_groups = [g for g in groups if len(set(p.get("source_video_id") for p in g)) > 1]
        single_source_groups = [g for g in groups if len(set(p.get("source_video_id") for p in g)) == 1]
        
        logger.info(f"Grouped {len(predictions)} predictions into {len(groups)} groups")
        logger.info(f"  - Multi-source predictions: {len(multi_source_groups)} ({sum(len(g) for g in multi_source_groups)} mentions)")
        logger.info(f"  - Single-source predictions: {len(single_source_groups)}")
        
        return groups

    def calculate_confidence(self, group: List[Dict]) -> float:
        """
        Calculate confidence score for a prediction group
        
        Args:
            group: List of similar predictions
            
        Returns:
            Confidence score (0-1)
        """
        # Base: number of sources mentioning this
        num_sources = len(set(p.get("source_video_id") for p in group))
        
        # Average credibility of sources
        credibilities = [p.get("source_credibility", 5) for p in group]
        avg_credibility = sum(credibilities) / len(credibilities) if credibilities else 5
        credibility_factor = avg_credibility / 10.0
        
        # Individual confidence levels
        confidences = [p.get("confidence", 0.5) for p in group]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Combine factors
        overall_confidence = (
            (num_sources / max(len([p["source_video_id"] for p in group]), 1)) * 0.4 +
            credibility_factor * 0.3 +
            avg_confidence * 0.3
        )
        
        return min(overall_confidence, 1.0)

    def consolidate_predictions(self, prediction_groups: List[List[Dict]]) -> List[Dict]:
        """
        Consolidate grouped predictions into high-level predictions
        Focus on multi-source themes
        
        Args:
            prediction_groups: List of groups from group_similar_predictions
            
        Returns:
            List of consolidated predictions with confidence scores
        """
        consolidated = []
        
        for group in prediction_groups:
            # Get unique source videos
            source_videos = list(set(p.get("source_video_id") for p in group))
            num_sources = len(source_videos)
            
            if num_sources < self.min_occurrences:
                continue
            
            # Calculate metrics
            confidence = self.calculate_confidence(group)
            
            if confidence < self.min_confidence:
                continue
            
            # Extract common aspects
            areas = []
            zodiac_signs = []
            timeframes = []
            
            for pred in group:
                if "area" in pred:
                    areas.append(pred["area"])
                if "zodiac_signs" in pred:
                    if isinstance(pred["zodiac_signs"], list):
                        zodiac_signs.extend(pred["zodiac_signs"])
                    else:
                        zodiac_signs.append(pred["zodiac_signs"])
                if "timeframe" in pred:
                    timeframes.append(pred["timeframe"])
            
            # Build consolidated prediction
            consolidated_pred = {
                "prediction": group[0].get("prediction", ""),
                "confidence": round(confidence, 2),
                "num_sources": num_sources,
                "mention_count": len(group),  # Total mentions across sources
                "areas_mentioned": list(set(areas)) if areas else [],
                "zodiac_signs": list(set(zodiac_signs)) if zodiac_signs else [],
                "timeframes": list(set(timeframes)) if timeframes else [],
                "average_credibility": round(
                    sum(p.get("source_credibility", 5) for p in group) / len(group), 1
                ),
                "source_videos": [
                    {
                        "video_id": p.get("source_video_id"),
                        "title": p.get("source_title"),
                        "channel": p.get("source_channel"),
                    }
                    for p in group
                ],
            }
            
            consolidated.append(consolidated_pred)
        
        # Sort by: multi-source first, then confidence descending
        consolidated.sort(key=lambda x: (-x["num_sources"], -x["confidence"]))
        
        logger.info(f"Consolidated into {len(consolidated)} high-confidence predictions")
        return consolidated

    def extract_common_themes(self, consolidated_predictions: List[Dict]) -> Dict:
        """
        Extract common themes from consolidated predictions
        
        Args:
            consolidated_predictions: List of consolidated predictions
            
        Returns:
            Dict with theme analysis
        """
        areas_counter = Counter()
        zodiac_counter = Counter()
        
        for pred in consolidated_predictions:
            for area in pred.get("areas_mentioned", []):
                areas_counter[area] += 1
            for sign in pred.get("zodiac_signs", []):
                zodiac_counter[sign] += 1
        
        themes = {
            "top_areas": areas_counter.most_common(5),
            "top_zodiac_signs": zodiac_counter.most_common(6),
            "total_predictions": len(consolidated_predictions),
            "average_confidence": round(
                sum(p["confidence"] for p in consolidated_predictions) / len(consolidated_predictions), 2
            ) if consolidated_predictions else 0,
        }
        
        return themes

    def generate_report(
        self,
        consolidated_predictions: List[Dict],
        themes: Dict,
        filename: str = "analysis_report.json",
    ) -> Path:
        """
        Generate and save analysis report
        
        Args:
            consolidated_predictions: Consolidated predictions
            themes: Theme analysis
            filename: Output filename
            
        Returns:
            Path to saved report
        """
        report = {
            "generated_at": json.dumps({}),  # Will be set to timestamp
            "high_confidence_predictions": consolidated_predictions,
            "common_themes": themes,
            "summary": {
                "total_predictions": len(consolidated_predictions),
                "average_confidence": themes.get("average_confidence", 0),
                "primary_focus_areas": [area for area, _ in themes.get("top_areas", [])],
                "most_affected_zodiac_signs": [sign for sign, _ in themes.get("top_zodiac_signs", [])],
            },
        }
        
        output_path = DATA_DIR / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Report saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Could not save report: {e}")
            return None

    def analyze(self, summaries: List[Dict]) -> Dict:
        """
        Run complete analysis pipeline
        
        Args:
            summaries: List of summary dicts
            
        Returns:
            Dict with analysis results
        """
        logger.info("Starting prediction analysis pipeline")
        
        # Extract predictions
        predictions = self.extract_predictions(summaries)
        if not predictions:
            logger.warning("No predictions found to analyze")
            return {}
        
        # Group similar predictions
        groups = self.group_similar_predictions(predictions)
        
        # Consolidate and score
        consolidated = self.consolidate_predictions(groups)
        
        # Extract themes
        themes = self.extract_common_themes(consolidated)
        
        # Generate report
        self.generate_report(consolidated, themes)
        
        return {
            "predictions": consolidated,
            "themes": themes,
            "total_sources": len(summaries),
            "total_predictions_analyzed": len(predictions),
        }


if __name__ == "__main__":
    analyzer = PredictionAnalyzer()
    
    # Example: analyze sample summaries
    sample_summaries = [
        {
            "video_id": "vid1",
            "title": "2026 Astro Predictions",
            "channel": "Astro Channel",
            "summary": {
                "predictions": [
                    {
                        "prediction": "Financial gains for Sagittarius",
                        "area": "finance",
                        "zodiac_signs": ["Sagittarius"],
                        "confidence": 0.8,
                        "source_credibility": 8,
                    }
                ]
            },
        }
    ]
    
    result = analyzer.analyze(sample_summaries)
    print(json.dumps(result, indent=2, ensure_ascii=False))
