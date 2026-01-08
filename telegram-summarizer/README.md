# Telegram Group Summarizer

Daily AI-powered summaries of Telegram trading/investment groups.

## Features

- 📱 Monitors multiple Telegram groups
- 📎 Extracts and summarizes shared links
- 🎬 Fetches YouTube video transcripts
- 🤖 GPT-4 powered intelligent summarization
- ⏰ Scheduled daily at 11:59 PM IST
- 📤 Sends summary to your Telegram

## Setup

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Note down `api_id` and `api_hash`

### 2. Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key

### 3. Configure Environment

```bash
cd telegram-summarizer
cp .env.example .env
```

Edit `.env`:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef
TELEGRAM_BOT_TOKEN=8208173603:AAGG2mx34E9qfaBnTyswlIOIOTT0Zsi4L0k
TELEGRAM_SUMMARY_CHAT_ID=5055508551
OPENAI_API_KEY=sk-...
TELEGRAM_GROUPS=@stockmarket_india,@trading_signals,-1001234567890
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Authenticate (First Time Only)

```bash
python summarizer.py --auth
```

This will:
1. Send an OTP to your Telegram app
2. You enter the OTP
3. Session is saved locally (you won't need to do this again)

### 6. Run

**Manual run:**
```bash
python summarizer.py
```

**Scheduled (runs at 11:59 PM IST):**
```bash
python summarizer.py --schedule
```

## Group Format

Groups can be specified as:
- Username: `@stockmarket_india`
- Username without @: `trading_signals`
- Group ID: `-1001234567890`

To find a group's ID, forward a message from the group to @userinfobot

## Output Example

```
📊 DAILY MARKET INTELLIGENCE
📅 08 Jan 2026
──────────────────────────────

📱 Trading Signals India (156 msgs)
─────────────────────────

**Market Sentiment:** Cautiously bullish

**Key Discussions:**
• NIFTY expected to test 22,800 resistance
• Banking stocks showing strength
• IT sector under pressure due to US recession fears

**Notable Calls:**
• RELIANCE buy above 2950 target 3050
• HDFC Bank accumulate on dips
• Avoid INFY short term

**Shared Resources:**
• MoneyControl article on RBI policy
• YouTube analysis on market breadth

**Actionable Insights:**
• Focus on banking and auto sectors
• Book profits in IT names
• Watch for NIFTY breakout above 22,800

**Tomorrow's Focus:**
• RBI credit policy announcement
• Quarterly results begin
```

## Notes

- You must be a member of the groups you want to monitor
- The bot can only read messages from groups you've joined
- YouTube transcripts may not be available for all videos
- API rate limits apply (max 500 messages per group per day)
