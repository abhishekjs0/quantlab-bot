# Dhan Authentication - Setup Complete ✅

## What Changed

Your Dhan authentication script has been **completely refactored** to use a simpler, Zerodha-style approach:

### Before (Complex)
- Used Selenium for headless Chrome automation
- Required webdriver-manager
- Complex Flask callback server with decorators
- Hard to understand flow

### After (Simple) ✅
- Uses native Python HTTP callback server
- Browser-based login (you do it manually, not automated)
- Clean step-by-step flow
- Only requires: `pyotp`, `requests`, `python-dotenv`

## Files

| File | Purpose | Status |
|------|---------|--------|
| `scripts/dhan_auth.py` | Main authentication script | ✅ Ready |
| `.env` | Configuration with credentials | ✅ Updated (added TOTP_SECRET) |
| `.dhan_token.json` | Generated token file (after login) | ⏳ Will be created |
| `docs/DHAN_AUTH_SETUP.md` | Complete setup guide | ✅ Created |

## How to Use

### 1. Fill in Your Credentials

Edit `.env` and add:

```properties
DHAN_USER_ID=your_username
DHAN_PASSWORD=your_password
```

All other fields already have values (keep them as-is).

### 2. Run the Script

```bash
python3 scripts/dhan_auth.py
```

### 3. What Happens

1. ✅ Script validates your credentials
2. ✅ Generates consent at Dhan
3. ✅ Starts callback server on port 8000
4. ✅ Opens Dhan login page in your browser
5. ✅ Prints your TOTP code
6. ✅ You enter credentials + TOTP in browser (manual)
7. ✅ Dhan redirects → callback captures tokenId
8. ✅ Script exchanges tokenId for accessToken
9. ✅ Token saved to `.dhan_token.json`
10. ✅ Token validated with /v2/profile endpoint

### 4. Use the Token

```python
import json

with open(".dhan_token.json") as f:
    token = json.load(f)

headers = {
    "access-token": token["accessToken"],
    "dhanClientId": token["dhanClientId"],
}

# Use headers in your API calls to Dhan
```

## Requirements Installed

```bash
pyotp            ✅ TOTP code generation
requests         ✅ HTTP requests
python-dotenv    ✅ Load .env file
```

Already installed in your `.venv`!

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Your Computer                                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  python3 dhan_auth.py                                       │
│         │                                                    │
│         ├─→ [STEP 1] Generate Consent                       │
│         │        └─→ POST auth.dhan.co/app/generate-consent │
│         │            ← Returns: consentAppId                │
│         │                                                    │
│         ├─→ [STEP 2] Start Callback Server                  │
│         │        └─→ Listening on http://127.0.0.1:8000    │
│         │                                                    │
│         ├─→ [STEP 3] Open Browser + Show TOTP              │
│         │        ├─→ Opens https://auth.dhan.co/login       │
│         │        └─→ Prints: "TOTP code: 123456"           │
│         │                                                    │
│         ├─→ [STEP 4] Wait for User (YOU!) to Login         │
│         │        └─→ Enter: User ID → Password → TOTP      │
│         │            (in your browser)                      │
│         │                                                    │
│         ├─→ [STEP 5] Capture Redirect with tokenId         │
│         │        └─→ Dhan redirects to callback server      │
│         │            http://127.0.0.1:8000/callback        │
│         │            └─→ Server captures tokenId            │
│         │                                                    │
│         ├─→ [STEP 6] Exchange tokenId for accessToken      │
│         │        └─→ POST auth.dhan.co/app/consumeApp-     │
│         │            consent with tokenId                   │
│         │            ← Returns: accessToken                 │
│         │                                                    │
│         ├─→ [STEP 7] Save Token                            │
│         │        └─→ Write .dhan_token.json                 │
│         │                                                    │
│         └─→ [STEP 8] Validate Token                        │
│              └─→ GET api.dhan.co/v2/profile                 │
│                  ← Success! Token is valid                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Differences from Previous Version

| Aspect | Old | New |
|--------|-----|-----|
| Browser Automation | Selenium (headless) | Manual (you click) |
| Login Method | Auto-submit form | You enter credentials |
| Dependencies | Flask, Selenium, webdriver-manager | pyotp, requests, python-dotenv |
| Lines of Code | 500+ | 300+ |
| Complexity | High | Low |
| Reliability | Chrome driver updates | Simple HTTP |
| User Experience | Black box | Clear steps |

## Troubleshooting

**Q: Script says "MISSING: DHAN_USER_ID"**
- A: Edit `.env` and add your Dhan login username

**Q: Browser doesn't open**
- A: Script prints the URL. Open it manually.

**Q: TOTP code doesn't work**
- A: Copy the exact code printed by script (only valid for 30 seconds)

**Q: "Port 8000 already in use"**
- A: Something else is using port 8000. Change PORT in script or kill the process.

**Q: Token validation fails**
- A: Token expired (24-hour limit) or API credentials wrong. Re-run login.

## Next Steps

1. ✅ Fill in `DHAN_USER_ID` and `DHAN_PASSWORD` in `.env`
2. ✅ Run: `python3 scripts/dhan_auth.py`
3. ✅ Complete login in your browser
4. ✅ Check: `cat .dhan_token.json` (token saved successfully)
5. ✅ Use token in your QuantLab scripts

## Documentation

- **Quick Start**: `docs/DHAN_AUTH_SETUP.md`
- **Original Guide**: `docs/DHAN_AUTH_GUIDE.md`
- **Implementation Summary**: `DHAN_AUTH_IMPLEMENTATION.md`

---

**Status**: ✅ **READY TO USE**

Just add your credentials and run!

```bash
python3 scripts/dhan_auth.py
```
