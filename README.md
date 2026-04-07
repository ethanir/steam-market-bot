# Steam Market Bot

Automated Steam Community Market scanner and purchasing tool. Monitors skin listings in real-time using the CSFloat browser extension for float value analysis, and automatically purchases skins that match your configured criteria (float, pattern, stickers, price).

Includes a **web dashboard** for managing skins, configuring settings, and monitoring the bot live — no terminal editing required.

> ⚠️ **Currently macOS only.** Windows/Linux support is planned.

---

## Features

- **Real-time float scanning** via CSFloat Market Checker extension
- **Auto-purchase** skins matching your float, pattern, sticker, and price criteria
- **OVER/UNDER mode** — buy skins above or below a float threshold
- **Web dashboard** with live logs, skin management, and bot controls
- **Warm-up purchase** — one-click $0.03 buy to bypass phone confirmations
- **Smart pagination** — stale page detection and skip-ahead navigation
- **Rate limit handling** — configurable delays to avoid Steam throttling
- **Auto Chrome launch** — single command starts everything

---

## Requirements

- **macOS** (Apple Silicon or Intel)
- **Python 3.10+**
- **Google Chrome**
- **CSFloat Market Checker** Chrome extension

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ethanir/steam-market-bot.git
cd steam-market-bot
```

### 2. Install Python dependencies

```bash
pip3 install selenium requests chromedriver-autoinstaller pyyaml fastapi uvicorn
```

### 3. Install the CSFloat Market Checker extension

This extension is **required** — the bot uses it to read float values directly from Steam listings.

1. Open Chrome and go to the [Chrome Web Store](https://chromewebstore.google.com/detail/csfloat-market-checker/jjicbefpemnphinccgikpdaagjebbnhg)
2. Search for **"CSFloat Market Checker"**
3. Click **Add to Chrome**
4. Make sure the extension is enabled (puzzle icon → CSFloat should be listed)

### 4. Configure CSFloat settings

After installing CSFloat, click the extension icon and make sure:
- **Show float values on market pages** is enabled
- The extension has permission to run on `steamcommunity.com`

---

## Usage (Web Dashboard)

The web dashboard is the recommended way to use the bot. One command does everything:

```bash
cd steam-market-bot/backend
python3 app.py
```

This will:
1. **Launch Chrome** with remote debugging enabled
2. **Start the web server** at `http://localhost:8000`
3. **Open the dashboard** in your default browser

### First-time setup

1. **Log into Steam** in the Chrome window that opens
2. Click **Warm Up** in the dashboard — this buys a $0.03 skin to activate your session so you won't need phone confirmations while the bot runs
3. **Confirm the purchase** on your phone when prompted
4. Go to the **Skins** tab and add the skins you want to monitor
5. Configure **Float Mode** (OVER or UNDER)
6. Click **Start Bot**

### Adding skins

1. Go to the Steam Community Market and find the skin you want
2. Copy the full URL (e.g. `https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20(Battle-Scarred)`)
3. In the dashboard **Skins** tab, paste the URL
4. Set your **float threshold**, **max price**, and optionally a **pattern**
5. Click **Add Skin**

### Settings

In the **Settings** tab you can configure:

| Setting | Default | Description |
|---|---|---|
| Max Pages | 6 | How many pages to scan per skin |
| Cycle Cooldown | 15s | Wait time between full scan cycles |
| Page Delay | 3-5s | Random delay between page navigations |
| Skin Delay | 3-5s | Random delay between switching skins |

**Important:** Keep delays at 3+ seconds to avoid Steam rate limiting. If you get rate limited (pages stop changing), stop the bot and wait 15-30 minutes.

---

## Usage (Terminal Only)

If you prefer the terminal-based bot without the web dashboard:

### 1. Launch Chrome with debugging

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebug"
```

### 2. Log into Steam in that Chrome window

### 3. Edit your config file

Create `settings/config.yaml`:

```yaml
skins:
  - url: https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20(Battle-Scarred)
    float: 0.795
    price: 0.10
    number_of_stickers:
    pages:
    pattern:
```

- **float**: The float threshold (used with OVER/UNDER mode)
- **price**: Maximum price you're willing to pay
- **pattern**: Specific paint seed(s) — leave empty for any. Use `502, 800` for multiple
- **number_of_stickers**: Filter by sticker count — leave empty for any
- **pages**: Max pages to scan for this skin — leave empty for default

### 4. Run the bot

```bash
python3 csgo-market-sniper.py
```

Select OVER (1) or UNDER (2) mode when prompted, then the bot will start scanning.

---

## How It Works

1. The bot connects to your Chrome browser via remote debugging
2. For each skin in your config, it navigates to the Steam Market listing
3. CSFloat extension loads float values for all listings on the page
4. The bot reads these float values directly from the extension's DOM injection
5. It sorts by float (highest first for OVER mode, lowest for UNDER mode)
6. If a listing matches your criteria (float + price + pattern), it auto-purchases
7. It scans through multiple pages, then moves to the next skin
8. After all skins are scanned, it waits and starts a new cycle

### Stale Page Detection

Steam's pagination sometimes fails silently — you click "next page" but the content doesn't change. The bot detects this by comparing the top float value between pages. If the same float appears twice in a row, it knows the page didn't actually change and triggers recovery:

1. Jumps ahead to a further page (e.g. page 6)
2. If that page loads different content, scans backwards from there
3. If no pages work, moves to the next skin

### Rate Limiting

Steam will temporarily block pagination if you make too many requests. Signs of rate limiting:
- Every skin gets "stuck" on the same page
- Manual clicking in the browser also doesn't work

If this happens, stop the bot and wait 15-30 minutes. To prevent it, keep page delays at 3+ seconds and don't scan more than 2-3 skins at a time.

---

## Project Structure

```
steam-market-bot/
├── backend/                  # Web dashboard
│   ├── app.py               # FastAPI server + Chrome launcher
│   ├── bot_bridge.py        # Connects web UI to Selenium bot
│   ├── index.html           # Dashboard frontend
│   └── data/                # Saved skins & settings (auto-created)
├── functions.py             # Core bot logic (scanning, buying, navigation)
├── locators.py              # Selenium element selectors
├── config.py                # YAML config loader (terminal mode)
├── csgo-market-sniper.py    # Terminal-mode entry point
└── settings/
    ├── config.yaml          # Skin config (terminal mode, gitignored)
    └── requirements.txt
```

---

## Troubleshooting

### "Cannot connect to Chrome at 127.0.0.1:9222"

Chrome isn't running with remote debugging. If using the web dashboard, restart `python3 app.py` — it auto-launches Chrome. If using terminal mode, run:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeDebug"
```

The `--user-data-dir` flag is required — without it, Chrome won't enable the debugging port.

### CSFloat floats not loading

- Make sure the CSFloat Market Checker extension is installed and enabled
- Check that you're on a CS2 skin listing page (not cases, stickers, etc.)
- Try refreshing the page — CSFloat sometimes takes a few seconds to inject
- If using `--user-data-dir="$HOME/ChromeDebug"`, you may need to reinstall the extension in that Chrome profile

### Pages not changing / "stuck" on every skin

You're likely rate limited by Steam. Stop the bot and wait 15-30 minutes. When restarting, increase your delays in Settings (4-6 seconds recommended).

### Phone confirmation required on every purchase

Use the **Warm Up** button in the dashboard before starting the bot. This buys a $0.03 skin that you confirm on your phone, which activates your session for subsequent purchases.

### "session not created" error

Your chromedriver version doesn't match your Chrome version. Run:

```bash
pip3 install --upgrade chromedriver-autoinstaller
```

Then restart the bot — it will auto-install the correct chromedriver.

### Bot buys but the purchase fails

The listing may have been bought by someone else between scanning and clicking. This is normal on high-demand skins. The bot will continue scanning.

---

## Disclaimer

This tool is for educational purposes. Use at your own risk. Automated purchasing may violate Steam's Terms of Service. The authors are not responsible for any consequences including account restrictions.
