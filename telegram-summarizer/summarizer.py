"""
Telegram Group Summarizer
=========================

Monitors specified Telegram groups and generates daily AI-powered summaries
of market discussions, shared links, and YouTube videos.

Features:
- Fetches messages from multiple groups
- Extracts and summarizes shared links
- Fetches YouTube video transcripts for context
- Uses GPT-4 for intelligent summarization
- Scheduled daily summary at 11:55 PM IST
- Sends summary to your personal chat/channel

Setup:
1. Get API credentials from https://my.telegram.org
2. Create .env file from .env.example
3. Run once to authenticate: python summarizer.py --auth
4. Run daily: python summarizer.py
"""

import asyncio
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pytz
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import Message

# Load environment
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# CLOUD STORAGE SESSION DOWNLOAD (for Cloud Run)
# ═══════════════════════════════════════════════════════════════════════════════

def download_session_from_gcs():
    """Download session file from Cloud Storage if running in Cloud Run."""
    session_file = "telegram_summarizer.session"
    gcs_bucket = os.getenv("GCS_SESSION_BUCKET")
    
    if gcs_bucket and not os.path.exists(session_file):
        print(f"📥 Downloading session from gs://{gcs_bucket}/{session_file}...")
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(gcs_bucket)
            blob = bucket.blob(session_file)
            blob.download_to_filename(session_file)
            print(f"✅ Session file downloaded successfully")
        except Exception as e:
            print(f"❌ Failed to download session: {e}")
            raise

# Download session if in Cloud Run
if os.getenv("GCS_SESSION_BUCKET"):
    download_session_from_gcs()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUMMARY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Cloud Run uses TELEGRAM_CHAT_ID
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUPS_STR = os.getenv("TELEGRAM_GROUPS", "")
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES_PER_GROUP", "500"))

IST = pytz.timezone("Asia/Kolkata")

# Parse groups
GROUPS = [g.strip() for g in GROUPS_STR.split(",") if g.strip()]

# TradingView Ideas URLs - scrape both new and recently updated ideas
TRADINGVIEW_IDEAS_URL = "https://in.tradingview.com/markets/stocks-india/ideas/"
TRADINGVIEW_IDEAS_UPDATED_URL = "https://in.tradingview.com/markets/stocks-india/ideas/?sort=recent_updates"


# ═══════════════════════════════════════════════════════════════════════════════
# TRADINGVIEW IDEAS SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_tradingview_ideas(today_date: datetime) -> List[Dict]:
    """
    Scrape TradingView ideas from India stocks page.
    Returns ideas CREATED OR UPDATED in the last 24 hours.
    Scrapes both default (new) and recently updated listings.
    """
    ideas = []
    seen_urls = set()
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        
        print("   🌐 Starting browser...")
        
        # Setup headless Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        try:
            # Scrape BOTH new ideas AND recently updated ideas
            urls_to_scrape = [
                (TRADINGVIEW_IDEAS_URL, "new ideas"),
                (TRADINGVIEW_IDEAS_UPDATED_URL, "updated ideas"),
            ]
            
            idea_urls = []
            
            for page_url, page_type in urls_to_scrape:
                print(f"   📄 Fetching {page_type}...")
                driver.get(page_url)
                
                # Wait for ideas to load
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/chart/']"))
                    )
                except:
                    print(f"   ⚠️ No ideas found on {page_type} page")
                    continue
                
                # Give extra time for dynamic content
                import time
                time.sleep(3)
                
                # Find all idea links
                idea_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/chart/']")
                print(f"   📊 Found {len(idea_links)} links on {page_type} page")
                
                # Extract unique URLs
                for link in idea_links[:30]:  # Limit to 30 per page
                    href = link.get_attribute("href")
                    if href and "/chart/" in href and href not in seen_urls:
                        seen_urls.add(href)
                        idea_urls.append(href)
            
            print(f"   🔗 Total unique ideas: {len(idea_urls)}")
            
            # Fetch each idea's details
            for url in idea_urls[:20]:  # Limit to 20 ideas for speed
                idea = fetch_single_idea(url, today_date)
                if idea:
                    ideas.append(idea)
            
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"   ❌ TradingView scrape error: {e}")
    
    return ideas


def fetch_single_idea(url: str, today_date: datetime) -> Optional[Dict]:
    """Fetch a single TradingView idea page and extract details.
    
    Includes ideas that were CREATED or UPDATED in the last 24 hours.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        
        if not resp.ok:
            return None
        
        html = resp.text
        
        # Extract symbol from URL
        # URL format: /chart/SYMBOL/ID-title/
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p and p != 'chart']
        symbol = parts[0].upper() if parts else ""
        
        # Extract title from URL slug
        title_slug = parts[1] if len(parts) > 1 else ""
        # Remove ID prefix and convert to readable title
        if '-' in title_slug:
            title_parts = title_slug.split('-')
            if title_parts and re.match(r'^[a-zA-Z0-9]{6,}$', title_parts[0]):
                title_parts = title_parts[1:]
            title = ' '.join(title_parts)
        else:
            title = title_slug
        
        # Extract description from JSON in page
        desc_match = re.search(r'"description":"([^"]*)"', html)
        description = desc_match.group(1) if desc_match else ""
        # Unescape newlines
        description = description.replace('\\n', '\n')
        
        # Check BOTH created_at AND updated_at dates
        # Include idea if EITHER is within last 24 hours
        is_recent = False
        idea_date_str = ""
        
        # Check created_at date
        created_match = re.search(r'"created_at":"([^"]*)"', html)
        if created_match:
            try:
                created_str = created_match.group(1)
                created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                created_ist = created_date.astimezone(IST)
                
                # Check if created in last 24 hours
                if created_ist.date() == today_date.date():
                    is_recent = True
                    idea_date_str = f"Created: {created_ist.strftime('%Y-%m-%d %H:%M')}"
            except:
                pass
        
        # Check updated_at date (even if created_at is old)
        updated_match = re.search(r'"updated_at":"([^"]*)"', html)
        if updated_match and not is_recent:
            try:
                updated_str = updated_match.group(1)
                updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                updated_ist = updated_date.astimezone(IST)
                
                # Check if updated in last 24 hours
                if updated_ist.date() == today_date.date():
                    is_recent = True
                    idea_date_str = f"Updated: {updated_ist.strftime('%Y-%m-%d %H:%M')}"
            except:
                pass
        
        # Fallback: check published_time / datePublished
        if not is_recent:
            date_match = re.search(r'"published_time":"([^"]*)"', html)
            if not date_match:
                date_match = re.search(r'"datePublished":"([^"]*)"', html)
            
            if date_match:
                try:
                    pub_date_str = date_match.group(1)
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    pub_date_ist = pub_date.astimezone(IST)
                    
                    if pub_date_ist.date() == today_date.date():
                        is_recent = True
                        idea_date_str = f"Published: {pub_date_ist.strftime('%Y-%m-%d %H:%M')}"
                except:
                    pass
        
        # Skip if not created/updated/published recently
        if not is_recent:
            return None
        
        # Extract author - look for user object with is_broker:false
        # Pattern: "user":{"username":"siripireddyvenu",...,"is_broker":false}
        author_matches = re.findall(r'"user":\s*\{"username":"([^"]+)"[^}]*"is_broker":false', html)
        author = author_matches[0] if author_matches else ""
        
        # Fallback: try to find any non-system username
        if not author:
            all_usernames = re.findall(r'"username":"([^"]+)"', html)
            for uname in all_usernames:
                if uname not in ["Guest", "IBKR", "TradingView", ""]:
                    author = uname
                    break
        
        return {
            "symbol": symbol,
            "title": title[:150],
            "description": description[:1500],  # More context for detailed analysis
            "author": author,
            "url": url,
        }
        
    except Exception as e:
        return None


def summarize_tradingview_ideas(ideas: List[Dict]) -> str:
    """Generate AI summary of TradingView ideas."""
    if not ideas:
        return "• No new ideas posted today"
    
    if not OPENAI_API_KEY:
        return "❌ OpenAI API key not configured"
    
    # Strip whitespace from API key
    api_key = OPENAI_API_KEY.strip()
    client = OpenAI(api_key=api_key)
    
    # Build context with URLs
    context_parts = []
    for idea in ideas:
        idea_text = f"SYMBOL: {idea['symbol']}\n"
        idea_text += f"TITLE: {idea['title']}\n"
        idea_text += f"AUTHOR: {idea['author']}\n"
        idea_text += f"URL: {idea['url']}\n"
        idea_text += f"DESCRIPTION: {idea['description']}\n"
        context_parts.append(idea_text)
    
    context = "\n---\n".join(context_parts)
    
    prompt = f"""Extract DETAILED trading ideas from TradingView. Include ALL price levels and numbers mentioned.

IDEAS ({len(ideas)} total):
{context}

OUTPUT FORMAT:
🎯 TRADINGVIEW IDEAS

• SYMBOL - [LONG/SHORT/NEUTRAL] by @AuthorName
  [Complete trade reasoning with ALL numbers mentioned]
  Entry: ₹X | TP: ₹X | SL: ₹X | Support: ₹X | Resistance: ₹X
  [Link to idea]

EXAMPLE OUTPUT:
• NAUKRI - NEUTRAL by @TradingMaster
  Price consolidating in tight range ₹7200-7450. Lower highs from top, higher lows from bottom. Wait for breakout above ₹7450 for long or below ₹7200 for short.
  Support: ₹7200 | Resistance: ₹7450 | Breakout target: ₹7800
  https://in.tradingview.com/chart/...

• RELIANCE - LONG by @ChartAnalyst  
  Bullish flag pattern forming. Entry on breakout above ₹2650 with volume.
  Entry: ₹2650 | TP1: ₹2750 | TP2: ₹2850 | SL: ₹2580
  https://in.tradingview.com/chart/...

RULES:
- Extract EVERY price level mentioned (Entry, TP, SL, Support, Resistance, Wait for price, Breakout level)
- Use ₹ symbol for all Indian stock prices
- Include the full reasoning/analysis from description
- Each idea should be 3-4 lines with complete trade setup
- Include @AuthorName and idea URL for each
- If no specific levels mentioned, describe the pattern/setup in detail
- No AI commentary - only extract what author wrote"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a detailed trading idea extractor. Extract ALL price levels and complete trade setups from TradingView ideas. Be thorough - include every number mentioned."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=3000,
                temperature=0.2,
                timeout=60,
            )
            return response.choices[0].message.content
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ OpenAI attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return f"❌ AI summarization failed after {max_retries} attempts: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT EXTRACTORS
# ═══════════════════════════════════════════════════════════════════════════════

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    if not text:
        return []
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)


def is_youtube_url(url: str) -> bool:
    """Check if URL is YouTube."""
    return any(x in url for x in ["youtube.com", "youtu.be"])


def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_youtube_info(video_id: str) -> Dict:
    """Get YouTube video title and full transcript."""
    result = {"title": "", "transcript": "", "channel": "", "url": f"https://youtube.com/watch?v={video_id}"}
    
    try:
        # Get title and channel via oEmbed (no API key needed)
        oembed_url = f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(oembed_url, timeout=10)
        if resp.ok:
            data = resp.json()
            result["title"] = data.get("title", "")
            result["channel"] = data.get("author_name", "")
    except Exception:
        pass
    
    try:
        # Get FULL transcript for detailed analysis
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'hi', 'en-IN'])
        # Get more of the transcript for better summarization
        text = " ".join([t["text"] for t in transcript_list[:300]])  # More segments for full context
        result["transcript"] = text[:8000]  # Higher limit for detailed summary
    except Exception:
        pass
    
    return result


def summarize_youtube_videos(youtube_info: Dict[str, Dict]) -> Optional[str]:
    """Generate detailed AI summary of YouTube videos with key takeaways.
    
    Args:
        youtube_info: Dict mapping video_id to {title, transcript, channel, url}
    
    Returns:
        Formatted string with detailed summaries, or None if no videos
    """
    if not youtube_info:
        return None
    
    # Filter videos that have transcripts (can't summarize without content)
    videos_with_content = {
        vid_id: info for vid_id, info in youtube_info.items()
        if info.get("transcript") and len(info.get("transcript", "")) > 100
    }
    
    if not videos_with_content:
        return None
    
    if not OPENAI_API_KEY:
        return "❌ OpenAI API key not configured"
    
    api_key = OPENAI_API_KEY.strip()
    client = OpenAI(api_key=api_key)
    
    summaries = []
    
    for vid_id, info in videos_with_content.items():
        title = info.get("title", "Unknown Title")
        channel = info.get("channel", "Unknown Channel")
        url = info.get("url", f"https://youtube.com/watch?v={vid_id}")
        transcript = info.get("transcript", "")
        
        prompt = f"""Analyze this trading/market YouTube video and extract key insights.

VIDEO TITLE: {title}
CHANNEL: {channel}
URL: {url}

TRANSCRIPT:
{transcript}

PROVIDE A DETAILED ANALYSIS WITH:

📺 VIDEO SUMMARY (2-3 sentences on main topic)

🎯 KEY TAKEAWAYS
• [Specific actionable insight with numbers/levels if mentioned]
• [Market view or trend discussed]
• [Specific stocks/sectors highlighted with reasons]
• [Any warnings or risk factors mentioned]

💡 ACTIONABLE POINTS
• [SYMBOL - ACTION - Reason/Level] if any specific trades mentioned
• [Sector/theme to watch] if discussed

📊 DATA & LEVELS (if mentioned in video)
• Any specific price levels, support/resistance
• Percentage moves discussed
• Key dates or events highlighted

RULES:
- Extract ALL specific numbers, prices, percentages mentioned
- Use ₹ for INR prices, $ for USD
- Be concise but comprehensive
- Focus on actionable, trading-relevant information
- If it's educational content, extract the key lessons
- No AI commentary - only what was discussed in the video"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting trading insights from video content. Focus on actionable information, specific levels, and key market views. Be thorough but concise."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
                temperature=0.2,
                timeout=60,
            )
            
            video_summary = f"🎬 <b>{title}</b>\n"
            video_summary += f"📺 Channel: {channel}\n"
            video_summary += f"🔗 {url}\n\n"
            video_summary += response.choices[0].message.content
            summaries.append(video_summary)
            
        except Exception as e:
            print(f"   ⚠️ Failed to summarize video {vid_id}: {e}")
            # Still include video info even if summarization fails
            summaries.append(f"🎬 <b>{title}</b>\n📺 {channel}\n🔗 {url}\n(Transcript available but summarization failed)")
    
    if summaries:
        return "\n\n" + ("─" * 30) + "\n\n".join(summaries)
    return None


def get_webpage_summary(url: str) -> str:
    """Extract main content from webpage."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if not resp.ok:
            return ""
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove scripts, styles
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Get title
        title = soup.title.string if soup.title else ""
        
        # Get meta description
        meta_desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            meta_desc = meta.get("content", "")
        
        # Get main content (first 1000 chars of body text)
        body_text = soup.get_text(separator=" ", strip=True)[:1000]
        
        return f"Title: {title}\n{meta_desc}\n{body_text}"[:1500]
        
    except Exception:
        return ""


def is_tradingview_url(url: str) -> bool:
    """Check if URL is TradingView chart."""
    return "tradingview.com/chart" in url


def extract_tradingview_info(url: str) -> Optional[Dict]:
    """Extract stock info from TradingView chart URL.
    
    Example URL: https://in.tradingview.com/chart/CSBBANK/VlUe5yCd-BUY-TODAY-SELL-TOMORROW-for-5/
    Returns: {symbol: 'CSBBANK', title: 'BUY TODAY SELL TOMORROW for 5', entry: '', tp: '', sl: ''}
    """
    try:
        # Extract from URL path
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p and p != 'chart']
        
        if len(parts) >= 1:
            symbol = parts[0].upper()
            title = parts[1] if len(parts) > 1 else ""
            # Clean up title: VlUe5yCd-BUY-TODAY-SELL-TOMORROW-for-5 -> BUY TODAY SELL TOMORROW for 5
            if '-' in title:
                # Remove ID prefix (alphanumeric before first meaningful word)
                title_parts = title.split('-')
                # Skip first part if it looks like an ID
                if title_parts and re.match(r'^[a-zA-Z0-9]{6,}$', title_parts[0]):
                    title_parts = title_parts[1:]
                title = ' '.join(title_parts).replace('-', ' ')
            
            return {
                "symbol": symbol,
                "title": title,
                "url": url,
            }
        
        return None
    except Exception:
        return None


# Group-specific prompts
GROUP_PROMPTS = {
    "kapil": """This is a BTST (Buy Today Sell Tomorrow) focused channel. Extract:
- All TradingView chart links with stock symbol, action type (BTST/Stock Option)
- Entry price, Target Price (TP), Stop Loss (SL) if mentioned
- Format: SYMBOL - BTST/Option - Entry ₹X, TP ₹X, SL ₹X

Focus ONLY on actionable trades, ignore general discussion.""",
    
    "stock gainers": """This is a SEBI registered trading channel. Extract actionable insights:
- INTRA (intraday) trades with entry/support/target
- BTST trades with levels
- SWING trades with support and target views
- Format: SYMBOL | TYPE | CMP ₹X, Support ₹X, Target ₹X-₹X

Capture the complete trade setup with all levels mentioned.""",
    
    "ritvi": """This is a trading channel. Extract actionable insights:
- Stock additions with entry price: "Added SYMBOL @ ₹X"
- Position updates
- Target and stoploss mentions
- Keep it simple: SYMBOL - Action - ₹Price""",
}


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE FETCHER
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_group_messages(
    client: Client,
    group: str,
    since: datetime,
) -> List[Dict]:
    """Fetch messages from a group since given datetime."""
    messages = []
    
    try:
        # Handle both username and ID formats
        chat_id = int(group) if group.lstrip("-").isdigit() else group
        
        # Make since timezone-naive for comparison (Pyrogram returns UTC naive)
        since_utc = since.astimezone(pytz.UTC).replace(tzinfo=None)
        
        async for msg in client.get_chat_history(chat_id, limit=MAX_MESSAGES):
            # Stop if message is older than cutoff
            if msg.date < since_utc:
                break
            
            # Convert to IST for display
            msg_date_ist = pytz.UTC.localize(msg.date).astimezone(IST)
            
            content = {
                "id": msg.id,
                "date": msg_date_ist.strftime("%Y-%m-%d %H:%M"),
                "sender": msg.from_user.first_name if msg.from_user else "Unknown",
                "text": msg.text or msg.caption or "",
                "urls": [],
                "youtube": [],
                "forwards": msg.forward_from_chat.title if msg.forward_from_chat else None,
            }
            
            # Extract URLs
            text = content["text"]
            urls = extract_urls(text)
            
            for url in urls:
                if is_youtube_url(url):
                    vid_id = extract_youtube_id(url)
                    if vid_id:
                        content["youtube"].append({
                            "url": url,
                            "id": vid_id,
                        })
                elif is_tradingview_url(url):
                    tv_info = extract_tradingview_info(url)
                    if tv_info:
                        if "tradingview" not in content:
                            content["tradingview"] = []
                        content["tradingview"].append(tv_info)
                else:
                    content["urls"].append(url)
            
            if content["text"] or content["urls"] or content["youtube"]:
                messages.append(content)
        
        return messages
        
    except Exception as e:
        print(f"   ❌ Error fetching {group}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# AI SUMMARIZER
# ═══════════════════════════════════════════════════════════════════════════════

def get_group_prompt(group_name: str) -> str:
    """Get group-specific prompt based on group name."""
    group_lower = group_name.lower()
    for key, prompt in GROUP_PROMPTS.items():
        if key in group_lower:
            return prompt
    return ""  # Default prompt


def summarize_with_ai(
    messages: List[Dict],
    group_name: str,
    link_summaries: Dict[str, str],
    youtube_info: Dict[str, Dict],
    tradingview_data: List[Dict] = None,
) -> str:
    """Generate AI summary of messages."""
    
    if not OPENAI_API_KEY:
        return "❌ OpenAI API key not configured"
    
    # Strip whitespace from API key
    api_key = OPENAI_API_KEY.strip()
    client = OpenAI(api_key=api_key)
    
    # Build context
    context_parts = []
    
    # Messages
    for msg in messages[:200]:  # Limit messages
        text = msg["text"][:500] if msg["text"] else ""
        if text:
            context_parts.append(f"[{msg['sender']}]: {text}")
    
    # TradingView charts - prioritize for Kapil channel
    if tradingview_data:
        context_parts.append("\n--- TRADINGVIEW CHARTS ---")
        for tv in tradingview_data:
            context_parts.append(f"Chart: {tv['symbol']} - {tv['title']}")
    
    # Link summaries - include full content for AI to analyze
    if link_summaries:
        context_parts.append("\n--- SHARED ARTICLES ---")
        for url, summary in list(link_summaries.items())[:20]:
            if summary:
                domain = urlparse(url).netloc
                context_parts.append(f"Article from {domain}:\n{summary[:1000]}")
    
    # YouTube info - include transcript for AI to analyze
    if youtube_info:
        context_parts.append("\n--- SHARED YOUTUBE VIDEOS ---")
        for vid_id, info in list(youtube_info.items())[:10]:
            if info.get("title"):
                yt_text = f"Video: {info['title']}"
                if info.get("transcript"):
                    yt_text += f"\nContent: {info['transcript'][:1500]}"
                context_parts.append(yt_text)
    
    context = "\n".join(context_parts)[:20000]  # Token limit safety
    
    # Get group-specific instructions
    group_specific = get_group_prompt(group_name)
    
    if group_specific:
        # Simplified prompt for specific groups
        prompt = f"""Extract actionable trading information from this channel.

GROUP: {group_name}

{group_specific}

RAW CONTENT:
{context}

OUTPUT FORMAT:
🎯 ACTIONABLE INSIGHTS
• [Format each trade per the instructions above]

RULES:
- Use bullet points only (•)
- Include ₹ symbol for all prices
- No AI commentary
- Only include actual trades/calls shared
- If no trades found, write "• No trades shared today" """
    else:
        # Default prompt for general groups like ISB
        prompt = f"""Summarize this Telegram trading group discussion. Be a neutral organizer - DO NOT add opinions, commentary, or AI insights. Only structure what was actually discussed.

GROUP: {group_name}
MESSAGES: {len(messages)}

RAW CONTENT:
{context}

OUTPUT FORMAT (use exactly this structure):

📈 DISCUSSIONS
• [Topic/News item with relevant details, prices in ₹ or $, percentages where mentioned]
• [Each point should be sharp, specific, and complete on its own]
• [Include content from shared articles and YouTube videos as discussion points]
• [Mention source if from article/video: "Per [source]: ..."]

🎯 ACTIONABLE INSIGHTS
• [Symbol] - [Action: BUY/SELL/HOLD/ACCUMULATE/TRACK/AVOID] - [Reason/Level if mentioned]
• [Include specific price levels: Entry, Target, Stoploss, Support, Resistance]
• [Format: GOLD - HOLD - INR hedge, retracement at ₹4020]

RULES:
- Use bullet points only (•)
- Include ₹ or $ symbols for all prices
- Include % for all percentages  
- Be MECE (mutually exclusive, collectively exhaustive)
- No markdown headers (no #, ##, etc.)
- No AI commentary or recommendations
- No "Tomorrow's Focus" or similar AI additions
- If no actionable insights were shared, write "• No specific calls shared today"
- Keep each bullet to 1-2 lines max"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a neutral content organizer. Structure trading group discussions without adding any opinions or AI-generated insights. Only organize what was actually said."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.2,
                timeout=60,
            )
            return response.choices[0].message.content
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ OpenAI attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return f"❌ AI summarization failed after {max_retries} attempts: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM SENDER
# ═══════════════════════════════════════════════════════════════════════════════

def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send message via Telegram bot."""
    if not BOT_TOKEN or not SUMMARY_CHAT_ID:
        print("❌ Bot token or chat ID not configured")
        print(f"   BOT_TOKEN present: {bool(BOT_TOKEN)}, CHAT_ID present: {bool(SUMMARY_CHAT_ID)}")
        return False
    
    # Strip any whitespace from env vars
    token = BOT_TOKEN.strip()
    chat_id = SUMMARY_CHAT_ID.strip()
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    print(f"   Using chat_id: {chat_id}, token length: {len(token)}")
    
    # Split long messages
    max_len = 4000
    parts = [text[i:i+max_len] for i in range(0, len(text), max_len)]
    
    for i, part in enumerate(parts):
        try:
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": part,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }, timeout=30)
            
            if not resp.ok:
                # Retry without parse mode
                resp = requests.post(url, json={
                    "chat_id": chat_id,
                    "text": part,
                    "disable_web_page_preview": True,
                }, timeout=30)
            
            if resp.ok:
                print(f"   ✅ Sent part {i+1}/{len(parts)}")
            else:
                print(f"   ❌ Failed: {resp.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Send error: {e}")
            return False
    
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

async def run_daily_summary():
    """Main function to generate and send daily summary."""
    
    print("\n" + "=" * 60)
    print("📊 TELEGRAM GROUP SUMMARIZER")
    print(f"🕐 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST")
    print("=" * 60)
    
    if not API_ID or not API_HASH:
        print("❌ Telegram API credentials not configured")
        print("   Get them from https://my.telegram.org")
        return
    
    if not GROUPS:
        print("❌ No groups configured in TELEGRAM_GROUPS")
        return
    
    # Calculate time window: today 00:00 IST to now
    # This ensures we get ALL of today's content when running at 11:59 PM
    now = datetime.now(IST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = today_start
    
    print(f"\n📅 Fetching messages for {now.strftime('%d %b %Y')} (since 00:00 IST)")
    print(f"📱 Groups: {len(GROUPS)}")
    
    tv_summary = None  # TradingView ideas summary
    telegram_summaries = []  # Telegram group summaries
    all_youtube_videos = {}  # Collect YouTube videos from ALL groups for detailed summary
    
    # ═══════════════════════════════════════════════════════════════════
    # TRADINGVIEW IDEAS (Public)
    # ═══════════════════════════════════════════════════════════════════
    print("\n📊 Fetching TradingView Ideas...")
    try:
        tv_ideas = fetch_tradingview_ideas(now)
        if tv_ideas:
            print(f"   ✅ Found {len(tv_ideas)} ideas from today")
            tv_summary = summarize_tradingview_ideas(tv_ideas)
        else:
            print("   ⚠️ No ideas from today found")
    except Exception as e:
        print(f"   ❌ TradingView error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # TELEGRAM GROUPS
    # ═══════════════════════════════════════════════════════════════════
    
    # Initialize Pyrogram client
    async with Client(
        "telegram_summarizer",
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=os.path.dirname(os.path.abspath(__file__)),
    ) as client:
        
        for group in GROUPS:
            print(f"\n📥 Fetching: {group}")
            
            # Fetch messages
            messages = await fetch_group_messages(client, group, since)
            print(f"   Messages: {len(messages)}")
            
            if not messages:
                continue
            
            # Get group info
            try:
                chat = await client.get_chat(int(group) if group.lstrip("-").isdigit() else group)
                group_name = chat.title or group
            except Exception:
                group_name = group
            
            # Extract and fetch link content
            print("   📎 Processing links...")
            link_summaries = {}
            youtube_info = {}
            tradingview_data = []
            
            all_urls = []
            all_youtube = []
            
            for msg in messages:
                all_urls.extend(msg.get("urls", []))
                all_youtube.extend(msg.get("youtube", []))
                # Collect TradingView data
                for tv in msg.get("tradingview", []):
                    tradingview_data.append(tv)
            
            # Deduplicate
            unique_urls = list(set(all_urls))[:15]  # Limit
            unique_youtube = {yt["id"]: yt["url"] for yt in all_youtube}
            
            # Fetch link summaries
            for url in unique_urls:
                summary = get_webpage_summary(url)
                if summary:
                    link_summaries[url] = summary
            
            print(f"   📎 Links processed: {len(link_summaries)}")
            print(f"   📊 TradingView charts: {len(tradingview_data)}")
            
            # Fetch YouTube info
            for vid_id in list(unique_youtube.keys())[:5]:  # Limit
                info = get_youtube_info(vid_id)
                if info.get("title") or info.get("transcript"):
                    youtube_info[vid_id] = info
                    # Also add to global collection for detailed summary
                    all_youtube_videos[vid_id] = info
            
            print(f"   🎬 Videos processed: {len(youtube_info)}")
            
            # Generate AI summary
            print("   🤖 Generating AI summary...")
            summary = summarize_with_ai(messages, group_name, link_summaries, youtube_info, tradingview_data)
            
            telegram_summaries.append({
                "group": group_name,
                "message_count": len(messages),
                "summary": summary,
            })
    
    # Compile and send reports
    print("\n📝 Compiling final report...")
    
    date_str = now.strftime("%d %b %Y")
    
    # ═══════════════════════════════════════════════════════════════════
    # SEND TRADINGVIEW IDEAS (separate message)
    # ═══════════════════════════════════════════════════════════════════
    if tv_summary:
        print("\n📤 Sending TradingView ideas...")
        # Use HTML for reliable formatting
        tv_report = f"📊 <b>TRADINGVIEW IDEAS</b> | {date_str}\n{'─' * 17}\n\n{tv_summary}"
        send_telegram_message(tv_report, parse_mode="HTML")
    
    # ═══════════════════════════════════════════════════════════════════
    # SEND YOUTUBE VIDEO INSIGHTS (separate detailed message)
    # ═══════════════════════════════════════════════════════════════════
    if all_youtube_videos:
        print(f"\n🎬 Generating detailed YouTube summaries for {len(all_youtube_videos)} videos...")
        yt_detailed_summary = summarize_youtube_videos(all_youtube_videos)
        if yt_detailed_summary:
            print("📤 Sending YouTube video insights...")
            yt_report = f"🎬 <b>YOUTUBE VIDEO INSIGHTS</b> | {date_str}\n{'─' * 20}\n{yt_detailed_summary}"
            send_telegram_message(yt_report, parse_mode="HTML")
    
    # ═══════════════════════════════════════════════════════════════════
    # SEND TELEGRAM SUMMARIES (separate message)
    # ═══════════════════════════════════════════════════════════════════
    if telegram_summaries:
        print("\n📤 Sending Telegram summaries...")
        tg_report_parts = [
            f"📱 <b>TELEGRAM GROUPS</b> | {date_str}",
            f"{'─' * 17}",
        ]
        
        for s in telegram_summaries:
            tg_report_parts.append(f"\n\n📱 <b>{s['group']}</b>")
            tg_report_parts.append(s["summary"])
        
        tg_report = "\n".join(tg_report_parts)
        success = send_telegram_message(tg_report, parse_mode="HTML")
    else:
        success = True
    
    if success:
        print("\n✅ Daily summary sent successfully!")
    else:
        print("\n❌ Failed to send summary")
        # Print to console as fallback
        print("\n" + "=" * 60)
        if tv_summary:
            print(tv_report)
        if telegram_summaries:
            print(tg_report)
        print("=" * 60)


async def authenticate():
    """Run authentication flow for Pyrogram."""
    print("\n🔐 Telegram Authentication")
    print("=" * 40)
    print("This will send an OTP to your Telegram app.")
    print("You only need to do this once.\n")
    
    if not API_ID or not API_HASH:
        print("❌ Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env first")
        print("   Get them from https://my.telegram.org")
        return
    
    async with Client(
        "telegram_summarizer",
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=os.path.dirname(os.path.abspath(__file__)),
    ) as client:
        me = await client.get_me()
        print(f"✅ Authenticated as: {me.first_name} (@{me.username})")
        print("\n📁 Session saved. You can now run the summarizer.")


def main():
    """Entry point."""
    if "--auth" in sys.argv:
        asyncio.run(authenticate())
    elif "--now" in sys.argv or len(sys.argv) == 1:
        asyncio.run(run_daily_summary())
    elif "--schedule" in sys.argv:
        import schedule
        import time as time_module
        
        summary_time = os.getenv("SUMMARY_TIME", "23:59")
        
        print(f"📅 Scheduling daily summary at {summary_time} IST")
        schedule.every().day.at(summary_time).do(
            lambda: asyncio.run(run_daily_summary())
        )
        
        while True:
            schedule.run_pending()
            time_module.sleep(60)
    else:
        print("Usage:")
        print("  python summarizer.py --auth      # First-time authentication")
        print("  python summarizer.py             # Run summary now")
        print("  python summarizer.py --now       # Run summary now")
        print("  python summarizer.py --schedule  # Run as scheduled service")


if __name__ == "__main__":
    main()
