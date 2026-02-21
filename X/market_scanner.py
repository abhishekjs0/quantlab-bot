#!/usr/bin/env python3
"""
X Market Scanner - Lean Edition
Scrapes & Analyzes astrology posts from 6 accounts → AI Summary → Tweet Thread

Usage:
    python3 market_scanner.py                        # Fetch and analyze
    python3 market_scanner.py --model gpt-5.2        # Use different model
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


# ============================================================================
# CONFIGURATION
# ============================================================================

env_path = Path(__file__).parent.parent / "youtube-processor" / ".env"
load_dotenv(env_path)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "twitter-api45.p.rapidapi.com"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")  # Default: gpt-5.2 (toggleable with --model flag)

ASTROLOGY_ACCOUNTS = [
    "AstroSharmistha",
    "lunarastro108", 
    "GANNTRADER2",
    "Astrotherapist1",
    "Bjybnf",
    "sonisunil59",
    "sanjiv_bhasin",
    "Darshanj101",
    "kates_9999",
    "AtulAtuld",
    "brahmesh",
    "sharadjhun",
    "Mark_Astrology",
    "NIFTY_Astrology",
    "Gannhidden",
    "Piscesastro12",
    "thewooofwallst",
    "AstroCryptoGuru",
    "astrosumitbajaj",
    "ManishB79013135",
    "BujokMr",
    "justshailendra",
    "PredictionStock"
]

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# IST Timezone
IST = timezone(timedelta(hours=5, minutes=30))


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)

def get_date_range_ist():
    """Get last 1 day in IST (from 00:00 today to now)"""
    now = get_ist_now()
    today = now.date()
    
    # Return today's date as both start and end (will filter by time range when fetching)
    return today, today

def format_date_range():
    """Format date range for display"""
    start, end = get_date_range_ist()
    return f"{start.strftime('%b %d, %Y')} (IST) - Last 24 hours"


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_user_posts(username, count=50):
    """Fetch posts from a single user via RapidAPI"""
    url = f"https://{RAPIDAPI_HOST}/timeline.php"
    
    params = {
        "screenname": username,
        "count": str(count)
    }
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    try:
        for attempt in range(3):
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 429:
                wait = 10 * (attempt + 1)  # 10s, 20s, 30s
                print(f"   ⏳ Rate limited, waiting {wait}s...", end=" ")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            return data.get("timeline", [])
        print(f"   ❌ Failed after 3 attempts (rate limit)")
        return []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def filter_by_date_range(posts, start_date, end_date):
    """Filter posts to only include those within date range (IST)"""
    filtered = []
    
    for post in posts:
        try:
            # Handle different date formats from Twitter API
            created_at_str = post.get("created_at", "")
            if not created_at_str:
                continue
            
            # Twitter timeline format: "Wed Feb 14 12:34:56 +0000 2026"
            try:
                dt = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            except:
                # Fallback to ISO format
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                except:
                    continue
            
            # Convert to IST
            dt_ist = dt.astimezone(IST) if dt.tzinfo else dt.replace(tzinfo=IST)
            post_date = dt_ist.date()
            
            # Include if within date range
            if start_date <= post_date <= end_date:
                filtered.append(post)
        except:
            pass
    
    return filtered

def extract_post_data(post, username):
    """Extract relevant fields from a post"""
    return {
        "username": username,
        "text": post.get("text", ""),
        "created_at": post.get("created_at"),
        "likes": post.get("likes", 0),
        "retweets": post.get("retweets", 0),
        "url": f"https://twitter.com/{username}/status/{post.get('tweet_id', '')}"
    }


# ============================================================================
# SCRAPER CLASS
# ============================================================================

class MarketScanner:
    """Lean market astrology scanner"""
    
    def __init__(self):
        self.posts = []
        self.summary = None
        self.tweets = None
    
    def scrape(self):
        """Fetch posts from all accounts for last Monday to today"""
        start_date, end_date = get_date_range_ist()
        
        print(f"\n{'='*60}")
        print(f"📡 SCRAPING ASTROLOGY ACCOUNTS")
        print(f"{'='*60}")
        print(f"📅 Date Range: {format_date_range()}\n")
        
        for account in ASTROLOGY_ACCOUNTS:
            print(f"Fetching @{account}...", end=" ")
            posts = fetch_user_posts(account, count=50)
            filtered_posts = filter_by_date_range(posts, start_date, end_date)
            
            for post in filtered_posts:
                self.posts.append(extract_post_data(post, account))
            
            print(f"✓ {len(filtered_posts)} posts")
            time.sleep(1)  # 1s delay between accounts to avoid rate limiting
        
        # Summary stats
        print(f"\n{'─'*60}")
        print(f"📊 Total posts collected: {len(self.posts)}")
        print(f"{'─'*60}\n")
        
        return self.posts
    
    def summarize(self):
        """Summarize posts using OpenAI"""
        if not self.posts:
            print("❌ No posts to summarize")
            return None
        
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        print(f"{'='*60}")
        print(f"🤖 SUMMARIZING WITH {OPENAI_MODEL.upper()}")
        print(f"{'='*60}\n")
        
        # Prepare posts text
        posts_text = ""
        for post in self.posts:
            posts_text += f"@{post['username']}: {post['text']}\n\n"
        
        # Truncate if too long
        if len(posts_text) > 150000:
            posts_text = posts_text[:150000] + "\n... (truncated)"
        
        prompt = f"""Analyze these {len(self.posts)} astrology-based market commentary posts. Your job is to extract what the authors say and how much agreement exists.

For each market topic (Nifty, BankNifty, Gold, Silver, Crude, US markets, Crypto, key dates), report:
- **CONSENSUS** (3+ authors agreeing): Label clearly. Note the shared view.
- **MAJORITY** (2 authors agreeing): Note who agrees and on what.
- **SINGLE VIEW** (only 1 author mentions it): Flag as single-author only.
- **CONFLICT** (authors disagree): State both sides clearly.

Also extract:
- Key astrological events/transits mentioned (planet names, conjunctions, eclipses) and which market moves they are linked to
- Specific price levels — only note them if at least 2 authors mention a similar range
- Key dates highlighted (note how many authors flag each date)
- Overall sentiment: bullish / bearish / mixed / volatile

Do NOT add your own market opinion. Only summarize what the posts say.

Posts to analyze:
{posts_text}

Provide a structured summary."""

        try:
            # Support both max_tokens (legacy) and max_completion_tokens (gpt-5.2+)
            params = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a neutral research analyst. Your job is to read astrology-based market commentary posts and extract what the authors say — tracking consensus, majority views, single-author views, and conflicts. You do not add your own opinion. You do not fabricate data. You report faithfully."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
            }
            
            # Use appropriate token parameter based on model
            if "gpt-5" in OPENAI_MODEL.lower():
                params["max_completion_tokens"] = 10000
            else:
                params["max_tokens"] = 2000
            
            response = openai_client.chat.completions.create(**params)
            
            self.summary = response.choices[0].message.content
            print(f"✅ Summary generated:\n")
            print(f"{self.summary}\n")
            return self.summary
            
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            return None
    
    def generate_tweet_thread(self):
        """Generate tweet thread from summary"""
        if not self.summary:
            print("❌ No summary available")
            return None
        
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        print(f"{'='*60}")
        print(f"🐦 GENERATING TWEET THREAD")
        print(f"{'='*60}\n")
        
        prompt = f"""You are writing a Twitter thread as AstroChick — a calm, professional market observer who reads planetary cycles alongside price action.

Date context: {format_date_range()}

Source analysis (contains what astrology authors are saying, with consensus flags):
{self.summary}

---

**CONFIDENCE RULES — follow these strictly based on the source analysis**:

- CONSENSUS (3+ authors agree) → Use BULLISH / BEARISH / SIDEWAYS in caps. State the view clearly. Can mention a price range if multiple authors cite a similar one.
- MAJORITY (2 authors agree) → Use "looks likely", "leaning", "seems to favour". Can mention levels if both authors cite them.
- SINGLE VIEW (1 author only) → Use "one read suggests", "could be worth watching", "might". No specific price levels.
- CONFLICTING VIEWS → Present both sides. Use "mixed signals on...", "not a clean read", "torn between...".

**VOICE**:
Professional and calm. Narrative, not robotic. Not hype. Not a data dump.
You are sharing your read of the patterns — these are observations, not financial advice.

**ASTROLOGICAL FLAVOUR**:
Add light, plain-English astrological context where relevant — e.g., "with Mercury turning direct mid-week" or "the lunar energy around [date] tends to amplify volatility".
Keep it brief (half a sentence max). Skip it if the source data doesn't mention specific transits. Do NOT use heavy jargon.

**WRITING STYLE**:
Each tweet = 1–2 flowing sentences. Weave assets, dates, and reasoning together.
Use connectives: "while", "before", "as", "heading into", "which sets up".
NO period-separated fragments. NO comma-separated lists.

**FORMATTING**:
- 1 contextual emoji per tweet — placed naturally, not forced
- Em dash (—) for rhythm or a pivot in the sentence
- No hashtags. No @mentions.
- 150–260 chars per tweet (hard max 280)

**CONTENT RULES**:
- Price levels only when 2+ authors cite a similar range
- No "astrologers say" or external attribution — this is your own read
- No trader advice (buy / sell / invest)
- Dates only when the source data flags them specifically

**THREAD STRUCTURE** (7 tweets):

TWEET 1: Big picture — open with the overall market tone for the period, weaving the key assets together
TWEET 2: Key dates — narrate how the period likely unfolds (use only dates flagged in the source data)
TWEET 3: Nifty / BankNifty — direction, key level (if consensus supports it), what might shift it
TWEET 4: Gold — the dominant read with price context (only if supported by multiple authors)
TWEET 5: Silver — setup narrative (flush? breakout? range?) with whatever context the data gives
TWEET 6: Crude + US markets (SPY, Bitcoin if mentioned) — one woven take
TWEET 7: Close the thread with the week’s character in one crisp, memorable sentence

Generate the 7 tweets now:\n"""

        try:
            # Support both max_tokens (legacy) and max_completion_tokens (gpt-5.2+)
            params = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are AstroChick — a professional market observer who combines planetary cycle analysis with market pattern reading. You write for a financially literate audience. Your tone is calm, sharp, and narrative. You calibrate your confidence to the evidence: strong when multiple sources agree, hedged when only one does, balanced when sources conflict. You never give financial advice. You never fabricate specific numbers not in your source data."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
            }
            
            # Use appropriate token parameter based on model
            # gpt-5.2 max_completion_tokens = total budget (input + output)
            # summary embeds in prompt so budget needs to cover both
            if "gpt-5" in OPENAI_MODEL.lower():
                params["max_completion_tokens"] = 6000
            else:
                params["max_tokens"] = 1500
            
            response = openai_client.chat.completions.create(**params)
            
            thread_text = response.choices[0].message.content.strip()
            
            # Parse into individual tweets
            tweets = []
            for line in thread_text.split('\n'):
                line = line.strip()
                if line.startswith('TWEET'):
                    tweet_content = line.split(':', 1)[1].strip() if ':' in line else line
                    if tweet_content:
                        tweets.append(tweet_content)
            
            # If no quotes with TWEET X: format, try splitting by double newlines
            if not tweets and thread_text:
                potential_tweets = [t.strip() for t in thread_text.split('\n\n') if t.strip() and len(t.strip()) > 20]
                tweets = potential_tweets[:7]  # Take first 7
            
            self.tweets = tweets
            print(f"✅ Tweet thread generated ({len(tweets)} tweets):\n")
            for i, tweet in enumerate(tweets, 1):
                print(f"📌 Tweet {i} ({len(tweet)} chars):")
                print(f"   {tweet}\n")
            
            return tweets
            
        except Exception as e:
            print(f"❌ Error generating thread: {e}")
            return None
    
    def save_report(self):
        """Save results to JSON"""
        report = {
            "generated_at_ist": get_ist_now().isoformat(),
            "date_range": format_date_range(),
            "posts_analyzed": len(self.posts),
            "accounts": ASTROLOGY_ACCOUNTS,
            "model_used": OPENAI_MODEL,
            "summary": self.summary,
            "tweet_thread": self.tweets,
            "posts": self.posts
        }
        
        timestamp = get_ist_now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = OUTPUT_DIR / f"market_report_{timestamp}.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"{'='*60}")
        print(f"💾 Report saved: {output_file}")
        print(f"{'='*60}\n")
        
        return output_file


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="X Market Scanner - Astrology Analysis")
    default_model = os.getenv("OPENAI_MODEL", "gpt-5.2")
    parser.add_argument("--model", default=default_model, help=f"OpenAI model to use (default: {default_model}, can use gpt-4o-mini, gpt-5.2, etc.)")
    args = parser.parse_args()
    
    # Override model if specified
    global OPENAI_MODEL
    OPENAI_MODEL = args.model
    
    try:
        scanner = MarketScanner()
        
        # Run pipeline
        posts = scanner.scrape()
        if posts:
            summary = scanner.summarize()
            if summary:
                tweets = scanner.generate_tweet_thread()
                scanner.save_report()
        
        print(f"{'='*60}")
        print(f"✅ COMPLETE!")
        print(f"{'='*60}")
        print(f"📊 Posts: {len(scanner.posts)}")
        print(f"📝 Summary: {'✓' if scanner.summary else '✗'}")
        print(f"🐦 Tweets: {len(scanner.tweets) if scanner.tweets else 0}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
