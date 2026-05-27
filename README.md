<div align="center">

# 🎯 Steam Market Bot

### A real-time CS2 float sniper for the Steam Community Market — scan, match, and auto-buy

<p>
  <img src="https://img.shields.io/badge/platform-macOS-000000?style=flat-square&logo=apple&logoColor=white" alt="macOS">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Selenium-43B02A?style=flat-square&logo=selenium&logoColor=white" alt="Selenium">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 18">
  <img src="https://img.shields.io/badge/CSFloat-required-3b82f6?style=flat-square" alt="CSFloat required">
  <img src="https://img.shields.io/badge/license-educational-eab308?style=flat-square" alt="Educational use">
</p>

</div>

---

## ✨ Overview

**Steam Market Bot** watches CS2 skin listings in real time and snipes the ones that match your exact criteria — float, paint seed, sticker count, and price. It reads live float values straight from the **CSFloat Market Checker** extension, sorts listings, walks through pages, and auto-purchases anything that fits.

Drive it from a clean **web dashboard** — add skins, tune settings, and watch a live log stream — or run it straight from the terminal. No config editing required unless you want it.

## 🎮 Features

- 🔍 **Real-time float scanning** — reads float values live from the CSFloat extension's DOM injection.
- ⚡ **Auto-purchase** — buys skins matching your float, pattern, sticker, and price criteria automatically.
- 🔀 **OVER / UNDER mode** — snipe skins above *or* below a float threshold.
- 🖥️ **Web dashboard** — live logs, skin management, and bot controls in the browser. One command starts everything.
- 🔥 **Warm-up purchase** — one-click $0.03 buy to activate your session and skip phone confirmations.
- 🧭 **Smart pagination** — detects stale pages and skips ahead to recover.
- 🐢 **Rate-limit handling** — configurable delays to stay under Steam's throttle.
- 🚀 **Auto Chrome launch** — a single command spins up Chrome with remote debugging and opens the dashboard.

## 📦 Requirements

| Requirement | Notes |
|:------------|:------|
| **macOS** | Apple Silicon or Intel. Windows/Linux planned. |
| **Python 3.10+** | — |
| **Google Chrome** | Launched with remote debugging. |
| **CSFloat Market Checker** | Chrome extension — **required** for float reading. |

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/ethanir/steam-market-bot.git
cd steam-market-bot

# 2. Install dependencies
pip3 install selenium requests chromedriver-autoinstaller pyyaml fastapi uvicorn

# 3. Launch the dashboard (auto-starts Chrome + opens browser)
cd backend
python3 app.py
```

Then install the [CSFloat Market Checker](https://chromewebstore.google.com/detail/csfloat-market-checker/jjicbefpemnphinccgikpdaagjebbnhg) extension, enable **Show float values on market pages**, and allow it to run on `steamcommunity.com`.

## 🖥️ Using the Dashboard

The dashboard at `http://localhost:8000` is the recommended way to run the bot.

1. **Log into Steam** in the Chrome window that opens.
2. Click **Warm Up** — buys a $0.03 skin to activate your session. Confirm on your phone.
3. Open the **Skins** tab and paste a Steam Market URL, then set float threshold, max price, and (optionally) a pattern.
4. Pick **Float Mode** — OVER or UNDER.
5. Hit **Start Bot** and watch the live log.

## ⌨️ Terminal Mode

Prefer no dashboard? Run the classic bot directly.

```bash
# 1. Launch Chrome with remote debugging
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/ChromeDebug"

# 2. Log into Steam in that Chrome window, then run:
python3 csgo-market-sniper.py
```

Configure your skins in `settings/config.yaml`:

```yaml
skins:
  - url: https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20(Battle-Scarred)
    float: 0.795        # threshold (used with OVER/UNDER mode)
    price: 0.10         # max price you'll pay
    pattern:            # paint seed(s) — e.g. "502, 800". empty = any
    number_of_stickers: # filter by sticker count. empty = any
    pages:              # max pages to scan. empty = default
```

## ⚙️ Settings

| Setting | Default | Description |
|:--------|:-------:|:------------|
| Max Pages | 6 | Pages scanned per skin |
| Cycle Cooldown | 15s | Wait between full scan cycles |
| Page Delay | 3–5s | Random delay between page navigations |
| Skin Delay | 3–5s | Random delay between switching skins |

> ⚠️ Keep delays at **3+ seconds** to avoid Steam rate limiting. If pages stop changing, stop the bot and wait 15–30 minutes.

## 🏗️ How It Works

1. Connects to your running Chrome via remote debugging.
2. Navigates to each skin's Market listing.
3. CSFloat loads float values for every listing; the bot reads them from the extension's DOM.
4. Sorts by float — highest first for OVER, lowest for UNDER.
5. If the top listing matches float + price + pattern, it auto-purchases.
6. Scans across pages, then moves to the next skin and loops.

**Stale-page recovery:** Steam pagination sometimes fails silently. The bot detects a repeated top float, jumps ahead to a fresh page, then scans backwards to cover the gap. **Rate limiting:** if every skin gets stuck on the same page, you're throttled — stop and wait 15–30 minutes.

## 📁 Project Structure

```
steam-market-bot/
├── backend/                  # Web dashboard
│   ├── app.py                # FastAPI server + Chrome launcher
│   ├── bot_bridge.py         # Bridges web UI to the Selenium bot
│   ├── index.html            # React dashboard frontend
│   └── data/                 # Saved skins & settings (auto-created)
├── functions.py              # Core bot logic — scanning, buying, navigation
├── locators.py               # Selenium element selectors
├── config.py                 # YAML config loader (terminal mode)
├── csgo-market-sniper.py     # Terminal-mode entry point
└── settings/
    ├── config.yaml           # Skin config (terminal mode, gitignored)
    └── requirements.txt
```

## 🩹 Troubleshooting

| Problem | Fix |
|:--------|:----|
| `Cannot connect to Chrome at 127.0.0.1:9222` | Chrome isn't running with debugging. Restart `python3 app.py`, or relaunch Chrome with the `--remote-debugging-port` flag. |
| CSFloat floats not loading | Confirm the extension is installed/enabled on a CS2 listing page. Refresh — injection takes a few seconds. |
| Pages "stuck" on every skin | You're rate limited. Stop and wait 15–30 min; raise delays to 4–6s. |
| Phone confirmation on every buy | Use **Warm Up** before starting the bot. |
| `session not created` | Chromedriver/Chrome version mismatch — run `pip3 install --upgrade chromedriver-autoinstaller`. |

---

## ⚠️ Disclaimer

This tool is for **educational purposes**. Automated purchasing may violate Steam's Terms of Service. Use at your own risk — the author is not responsible for any consequences, including account restrictions.

---

<div align="center">

© 2026 Ethan Irimiciuc · All rights reserved.

</div>
