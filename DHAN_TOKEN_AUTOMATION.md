# Dhan API - Token Automation Guide

## Overview

This guide covers all methods for obtaining and managing Dhan API access tokens with 2FA automation support.

---

## ⏰ Token Status Check

```bash
python scripts/dhan_token_manager.py
```

**Output shows:**
- Token validity status (Valid/Invalid)
- Expiration date and time
- Days remaining until expiry
- Next refresh recommendation

---

## 🔑 Three Methods to Get/Refresh Token

### Method 1: Fully Automated Browser Login ⭐ (RECOMMENDED)

```bash
python scripts/dhan_login_auto_improved.py
```

**What it does:**
1. Opens Chrome browser automatically
2. Navigates to Dhan login page
3. Enters credentials from `.env` (DHAN_USER_ID, DHAN_PASSWORD)
4. Generates OTP from TOTP secret (DHAN_TOTP_SECRET)
5. Submits login form
6. Navigates to API settings page
7. Extracts access token
8. Validates token with API
9. Saves to `.env` file (DHAN_ACCESS_TOKEN)
10. Closes browser and shows success

**Requirements:**
- ✅ Chrome installed (automatic detection for macOS)
- ✅ `.env` file with credentials
- ✅ Internet connection
- ✅ ~30-60 seconds

**Timeline:**
1. Script opens Chrome (5 sec)
2. Browser navigates to login (3 sec)
3. Fills form and submits (5 sec)
4. OTP generated and entered (3 sec)
5. Redirect to API settings (5 sec)
6. Token extraction and validation (5 sec)
7. .env file update (2 sec)
8. Done! ✅

**Error Handling:**
If any step fails, falls back to manual token entry prompt.

---

### Method 2: Semi-Automated with Manual Copy-Paste

```bash
python scripts/dhan_token_refresh.py
```

**What it does:**
1. Shows step-by-step browser instructions
2. You login manually to Dhan web platform
3. You copy token from API settings page
4. You paste token in terminal
5. Script validates token with API
6. Script saves to `.env` file

**Requirements:**
- ✅ Web browser
- ✅ Manual copy-paste token
- ✅ ~2-3 minutes

**When to use:**
- Option 1 fails or has issues
- You want to verify token manually
- Don't trust full automation
- Browser automation blocked

---

### Method 3: Manual Token Entry

```bash
python scripts/dhan_token_refresh.py
```

When prompted for token:
1. Go to https://web.dhan.co/settings/apis
2. Login with your credentials
3. Find "Access Token" section
4. Click "Generate" (if needed)
5. Copy entire token (starts with "eyJ")
6. Paste in terminal prompt
7. Script validates and saves

---

## 📋 .env File Configuration

Required credentials in `.env`:

```env
# Account Credentials
DHAN_USER_ID=9624973000
DHAN_PASSWORD=your_password_here
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM

# Account ID & API Keys
DHAN_CLIENT_ID=1108351648
DHAN_API_KEY=your_api_key
DHAN_API_SECRET=your_api_secret

# Access Token (AUTO-UPDATED)
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...
```

**Security Notes:**
- ✅ `.env` is in `.gitignore`
- ✅ Never commit `.env` to git
- ✅ Credentials not logged to console
- ✅ All operations local to your machine
- ✅ HTTPS for all API calls

---

## 🔐 Token Details

### JWT Format
Access tokens are JWT (JSON Web Tokens):

```
Structure: header.payload.signature

Example: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3M...
         └─ header                  └─ payload (base64)
         └─ Contains algorithm      └─ Contains: issuer, expiry, client ID
```

### Payload Information
```json
{
  "iss": "dhan",
  "exp": 1762440888,           // Unix timestamp (when token expires)
  "iat": 1762354488,           // Issued at timestamp
  "dhanClientId": "1108351648",// Your client ID
  "tokenConsumerType": "SELF"
}
```

### Token Expiry
- Typically valid for 24 hours
- Calculated from `exp` field in JWT payload
- Script automatically calculates remaining days
- Refresh before expiry to avoid API failures

---

## ⚙️ TOTP (Time-Based One-Time Password) Setup

### What is TOTP?
- Time-based OTP for 2FA
- Changes every 30 seconds
- Authenticated with secret key
- No internet required for generation

### Your Secret Key
Located in `.env` as `DHAN_TOTP_SECRET`:
```
N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
```

### How Script Uses It
```python
import pyotp

secret = os.getenv("DHAN_TOTP_SECRET")
totp = pyotp.TOTP(secret)
code = totp.now()  # Generates current 6-digit OTP
```

### Manual Generation
If you need to generate OTP manually:
```bash
python3 -c "import pyotp; print(pyotp.TOTP('N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM').now())"
```

---

## 🔄 Scheduling Automatic Token Refresh

### Option 1: Cron Job (Recommended)

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 3 AM):
0 3 * * * cd /Users/abhishekshah/Desktop/quantlab-workspace && ./.venv/bin/python scripts/dhan_login_auto_improved.py >> logs/dhan_token_refresh.log 2>&1
```

Create log directory first:
```bash
mkdir -p /Users/abhishekshah/Desktop/quantlab-workspace/logs
```

Check if cron is set:
```bash
crontab -l | grep dhan_login_auto
```

### Option 2: Manual Reminders

Set calendar reminders to refresh token:
- Token expires in 24 hours
- Set reminder for 12 hours before expiry
- Run: `python scripts/dhan_login_auto_improved.py`

---

## 🛠️ Troubleshooting

### "Chrome not found"
```bash
# Install Chrome
brew install google-chrome

# Verify installation
ls "/Applications/Google Chrome.app"
```

### "Login timeout"
- Network might be slow
- Dhan website might be down
- Try Option 2 (semi-automated instead)

### "OTP rejected"
- Check system time: `date`
- Verify TOTP secret: `grep DHAN_TOTP_SECRET .env`
- OTP changes every 30 seconds - try again

### "Token not extracted"
- Website layout might have changed
- Use Option 2 (manual entry)
- Or enter token directly in `.env`

### "Token validation fails"
- Token might be invalid
- Check token format (should start with "eyJ")
- Try generating new token
- Verify DHAN_CLIENT_ID in `.env`

### "All tests fail"
```bash
# Check token status
python scripts/dhan_token_manager.py

# If invalid, refresh:
python scripts/dhan_login_auto_improved.py

# Verify with test:
python scripts/test_simple.py
```

---

## ✅ Verification

### Quick Status Check
```bash
python scripts/dhan_token_manager.py
```

### Full API Test
```bash
python scripts/test_simple.py
```

### See Your Holdings
```bash
python scripts/dhan_working.py
```

---

## 📊 Implementation Details

### Files Used
- `scripts/dhan_login_auto_improved.py` - Main automation script
- `scripts/dhan_token_refresh.py` - Semi-automated backup
- `scripts/dhan_token_manager.py` - Token status checker

### Key Libraries
- `selenium` - Browser automation
- `pyotp` - OTP generation
- `requests` - HTTP calls
- `dotenv` - .env file handling

### Chrome Detection (macOS)
Script automatically searches:
1. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
2. `/usr/local/bin/google-chrome`
3. `/opt/homebrew/bin/google-chrome`

---

## 🔒 Security Best Practices

✅ **DO:**
- Store credentials in `.env`
- Use environment variables
- Keep `.env` in `.gitignore`
- Refresh tokens regularly
- Use HTTPS for all API calls

❌ **DON'T:**
- Hardcode credentials in scripts
- Commit `.env` to git
- Share access tokens
- Log credentials to console
- Use HTTP for API calls

---

## 📚 API Endpoints Used

Token management uses these endpoints:

```
POST https://login.dhan.co/         # Login page
GET  https://web.dhan.co/settings/apis  # API settings page
GET  https://api.dhan.co/profile    # Token validation
```

---

## 💡 Tips & Tricks

### Force Token Refresh
```bash
# Even if token seems valid
python scripts/dhan_login_auto_improved.py
```

### Generate OTP Manually
```bash
# Without running full script
python3 -c "import pyotp; print(pyotp.TOTP('YOUR_SECRET').now())"
```

### Check Token Without Refreshing
```bash
python scripts/dhan_token_manager.py
```

### View Current Token
```bash
grep DHAN_ACCESS_TOKEN .env
```

### Test API Immediately
```bash
python scripts/test_simple.py
```

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Refresh token (auto) | `python scripts/dhan_login_auto_improved.py` |
| Refresh token (manual) | `python scripts/dhan_token_refresh.py` |
| Check token status | `python scripts/dhan_token_manager.py` |
| Test API | `python scripts/test_simple.py` |
| View holdings | `python scripts/dhan_working.py` |

---

## ❓ FAQ

**Q: How often should I refresh the token?**
A: Every 24 hours. Script can be automated with cron.

**Q: What if I don't have Chrome?**
A: Use Method 2 (semi-automated) or manually enter token in `.env`.

**Q: Can I use the token multiple times?**
A: Yes, until it expires. Refresh before 24-hour mark.

**Q: What if token expires?**
A: API calls will return 401 Unauthorized. Refresh immediately.

**Q: Can I have multiple tokens?**
A: No, new token revokes previous one on Dhan's server.

**Q: Is the TOTP secret secure?**
A: Yes, it's only for generating OTP codes. Never share it.

**Q: Can I schedule this on Linux/Windows?**
A: Yes, adapt cron command for your OS (Windows: Task Scheduler).

---

## 🚀 Next Steps

1. **Check Current Token:**
   ```bash
   python scripts/dhan_token_manager.py
   ```

2. **If Token Valid (< 24 hours old):** Skip to API guide
   
3. **If Token Invalid/Expired:** Refresh immediately
   ```bash
   python scripts/dhan_login_auto_improved.py
   ```

4. **Verify New Token Works:**
   ```bash
   python scripts/test_simple.py
   ```

5. **Setup Automatic Refresh (Optional):**
   ```bash
   crontab -e
   # Add cron job as shown above
   ```

---

## ✨ Summary

✅ 3 token refresh methods available  
✅ Full browser automation with fallback options  
✅ TOTP 2FA support  
✅ Automatic token validation  
✅ Safe credential management  
✅ Cron scheduling support  
✅ Comprehensive error handling  

Your token is critical for API access. Keep it fresh and you're all set!
