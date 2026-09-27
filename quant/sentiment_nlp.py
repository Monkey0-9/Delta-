"""
Financial sentiment analysis and catalyst extraction
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    sentiment_score: float  # -1.0 to 1.0
    sentiment_label: str  # "bullish", "bearish", "neutral"
    confidence: float  # 0.0 to 1.0
    key_phrases: List[str]
    catalysts: List[str]


@dataclass
class Catalyst:
    """Financial catalyst extracted from news"""
    type: str  # "earnings", "sec_filing", "executive", "regulatory", "m&a", "guidance"
    description: str
    impact: str  # "positive", "negative", "neutral"
    confidence: float


class SentimentAnalyzer:
    """Financial sentiment analysis with catalyst extraction"""
    
    def __init__(self):
        # Financial sentiment lexicons
        self.bullish_keywords = [
            'beat', 'surge', 'rally', 'gain', 'growth', 'profit', 'rise', 'jump',
            'strong', 'bullish', 'upgrade', 'buy', 'outperform', 'success', 'expand',
            'increase', 'record', 'high', 'momentum', 'breakout', 'recovery',
            'optimistic', 'positive', 'exceed', 'accelerate', 'improve', 'boost'
        ]
        
        self.bearish_keywords = [
            'fall', 'drop', 'decline', 'loss', 'miss', 'weak', 'bearish', 'downgrade',
            'sell', 'underperform', 'fail', 'cut', 'layoff', 'concern', 'risk',
            'decrease', 'low', 'slump', 'recession', 'pessimistic', 'negative',
            'below', 'slow', 'worsen', 'drag', 'pressure', 'struggle'
        ]
        
        # Catalyst patterns
        self.catalyst_patterns = {
            'earnings': [
                r'earnings?(?:\s+per\s+share|',
                r'eps',
                r'revenue',
                r'quarterly\s+results',
                r'q[1-4]\s+earnings'
            ],
            'sec_filing': [
                r'10-[kq]',
                r'8-k',
                r'sec\s+filing',
                r'regulatory\s+filing'
            ],
            'executive': [
                r'ceo',
                r'cfo',
                r'executive',
                r'director',
                r'appointed',
                r'resigned',
                r'departed',
                r'leadership'
            ],
            'regulatory': [
                r'fda',
                r'sec',
                r'approval',
                r'regulation',
                r'compliance',
                r'investigation',
                r'settlement'
            ],
            'm_a': [
                r'acquisition',
                r'merger',
                r'takeover',
                r'buyout',
                r'deal',
                r'agreement'
            ],
            'guidance': [
                r'guidance',
                r'outlook',
                r'forecast',
                r'expectation',
                r'projection'
            ]
        }
    
    def analyze_sentiment(self, text: str) -> SentimentResult:
        """Analyze sentiment of financial text"""
        text_lower = text.lower()
        
        # Count bullish and bearish keywords
        bullish_count = sum(1 for word in self.bullish_keywords if word in text_lower)
        bearish_count = sum(1 for word in self.bearish_keywords if word in text_lower)
        
        # Calculate sentiment score
        total_count = bullish_count + bearish_count
        if total_count == 0:
            sentiment_score = 0.0
            sentiment_label = "neutral"
            confidence = 0.0
        else:
            sentiment_score = (bullish_count - bearish_count) / total_count
            confidence = min(total_count / 10.0, 1.0)  # Cap at 1.0
            
            if sentiment_score > 0.2:
                sentiment_label = "bullish"
            elif sentiment_score < -0.2:
                sentiment_label = "bearish"
            else:
                sentiment_label = "neutral"
        
        # Extract key phrases
        key_phrases = self._extract_key_phrases(text)
        
        # Extract catalysts
        catalysts = self._extract_catalysts(text)
        
        return SentimentResult(
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            confidence=confidence,
            key_phrases=key_phrases,
            catalysts=[c.description for c in catalysts]
        )
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key financial phrases from text"""
        key_phrases = []
        
        # Look for numbers with context
        number_patterns = [
            r'\$\d+(?:\.\d+)?\s*(?:billion|million|thousand)',
            r'\d+%\s*(?:increase|decrease|growth|decline)',
            r'\d+\.\d+\s*(?:per\s+share|eps)',
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            key_phrases.extend(matches)
        
        return key_phrases
    
    def _extract_catalysts(self, text: str) -> List[Catalyst]:
        """Extract financial catalysts from text"""
        catalysts = []
        text_lower = text.lower()
        
        for catalyst_type, patterns in self.catalyst_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Determine impact based on sentiment
                    sentiment = self.analyze_sentiment(text)
                    if sentiment.sentiment_label == "bullish":
                        impact = "positive"
                    elif sentiment.sentiment_label == "bearish":
                        impact = "negative"
                    else:
                        impact = "neutral"
                    
                    catalyst = Catalyst(
                        type=catalyst_type,
                        description=f"{catalyst_type.replace('_', ' ').title()} related event",
                        impact=impact,
                        confidence=sentiment.confidence
                    )
                    catalysts.append(catalyst)
                    break  # Only add one catalyst per type
        
        return catalysts
    
    def analyze_news_batch(self, news_items: List[Dict[str, any]]) -> Dict[str, any]:
        """Analyze sentiment for a batch of news items"""
        results = []
        sentiment_scores = []
        
        for item in news_items:
            title = item.get('title', '')
            if title:
                sentiment = self.analyze_sentiment(title)
                results.append({
                    'title': title,
                    'sentiment': sentiment
                })
                sentiment_scores.append(sentiment.sentiment_score)
        
        # Calculate aggregate sentiment
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        else:
            avg_sentiment = 0.0
        
        return {
            'individual_results': results,
            'average_sentiment': avg_sentiment,
            'total_items': len(results)
        }
    
    def deduplicate_news(self, news_items: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Remove duplicate news items based on title similarity"""
        seen_hashes = set()
        unique_items = []
        
        for item in news_items:
            title = item.get('title', '')
            title_hash = hash(title.lower().strip())
            
            if title_hash not in seen_hashes:
                seen_hashes.add(title_hash)
                unique_items.append(item)
        
        return unique_items
    
    def filter_clickbait(self, news_items: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Filter out clickbait headlines"""
        clickbait_patterns = [
            r'should\s+(?:you|i)\s+(?:buy|sell)',
            r'is\s+(?:a\s+)?(?:buy|sell)',
            r'top\s+\d+\s+(?:stocks|picks)',
            r'crash\s+coming',
            r'moon\s+soon',
            r'will\s+(?:skyrocket|plummet)',
            r'guaranteed\s+returns'
        ]
        
        filtered_items = []
        for item in news_items:
            title = item.get('title', '')
            is_clickbait = any(re.search(pattern, title, re.IGNORECASE) 
                             for pattern in clickbait_patterns)
            
            if not is_clickbait:
                filtered_items.append(item)
        
        return filtered_items
    
    def get_sentiment_summary(self, sentiment_results: List[SentimentResult]) -> Dict[str, any]:
        """Get summary statistics for sentiment analysis"""
        if not sentiment_results:
            return {
                "total": 0,
                "bullish": 0,
                "bearish": 0,
                "neutral": 0,
                "average_score": 0.0,
                "average_confidence": 0.0
            }
        
        bullish_count = sum(1 for s in sentiment_results if s.sentiment_label == "bullish")
        bearish_count = sum(1 for s in sentiment_results if s.sentiment_label == "bearish")
        neutral_count = sum(1 for s in sentiment_results if s.sentiment_label == "neutral")
        
        avg_score = sum(s.sentiment_score for s in sentiment_results) / len(sentiment_results)
        avg_confidence = sum(s.confidence for s in sentiment_results) / len(sentiment_results)
        
        return {
            "total": len(sentiment_results),
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": neutral_count,
            "average_score": avg_score,
            "average_confidence": avg_confidence
        }
