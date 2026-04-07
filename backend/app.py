"""
Steam Market Bot — FastAPI Backend
Serves config management, bot control, and live status.
"""
import os
import json
import yaml
import asyncio
import threading
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ============================================================
# DATA MODELS
# ============================================================

class SkinConfig(BaseModel):
    url: str
    float_threshold: Optional[float] = None
    max_price: Optional[float] = None
    pattern: Optional[str] = None
    number_of_stickers: Optional[int] = None
    pages: Optional[int] = None

class BotSettings(BaseModel):
    max_pages: int = 6
    cycle_cooldown: int = 15
    page_delay_min: float = 3.0
    page_delay_max: float = 5.0
    skin_delay_min: float = 3.0
    skin_delay_max: float = 5.0
    float_mode: str = "over"  # "over" or "under"

class BotStatus(BaseModel):
    running: bool = False
    current_skin: int = 0
    total_skins: int = 0
    current_page: int = 0
    orders_executed: int = 0
    balance: str = "0"
    cycle_count: int = 0
    last_action: str = ""

# ============================================================
# CONFIG FILE PATHS
# ============================================================

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data")
SKINS_FILE = os.path.join(CONFIG_DIR, "skins.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOG_FILE = os.path.join(CONFIG_DIR, "purchases.log")

os.makedirs(CONFIG_DIR, exist_ok=True)

# ============================================================
# STATE
# ============================================================

bot_status = BotStatus()
log_messages: list[str] = []
ws_clients: list[WebSocket] = []
bot_thread: Optional[threading.Thread] = None
bot_stop_event = threading.Event()

# ============================================================
# HELPERS
# ============================================================

def load_skins() -> list[dict]:
    if os.path.exists(SKINS_FILE):
        with open(SKINS_FILE, "r") as f:
            return json.load(f)
    return []

def save_skins(skins: list[dict]):
    with open(SKINS_FILE, "w") as f:
        json.dump(skins, f, indent=2)

def load_settings() -> dict:
    defaults = BotSettings().model_dump()
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
            defaults.update(saved)
    return defaults

def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

def add_log(msg: str):
    """Add a log message and broadcast to WebSocket clients."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    log_messages.append(entry)
    # Keep last 500 logs in memory
    if len(log_messages) > 500:
        log_messages.pop(0)
    # Broadcast to connected clients (fire and forget)
    asyncio.run_coroutine_threadsafe(broadcast_log(entry), loop)

async def broadcast_log(msg: str):
    """Send log message to all connected WebSocket clients."""
    disconnected = []
    for ws in ws_clients:
        try:
            await ws.send_text(json.dumps({"type": "log", "message": msg}))
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_clients.remove(ws)

async def broadcast_status():
    """Send current bot status to all connected WebSocket clients."""
    data = json.dumps({"type": "status", **bot_status.model_dump()})
    disconnected = []
    for ws in ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_clients.remove(ws)

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="Steam Market Bot")
loop = asyncio.new_event_loop()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- SERVE DASHBOARD ----------

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return f.read()

# ---------- SKINS ----------

@app.get("/api/skins")
def get_skins():
    return load_skins()

@app.post("/api/skins")
def add_skin(skin: SkinConfig):
    skins = load_skins()
    skins.append(skin.model_dump())
    save_skins(skins)
    add_log(f"Added skin: {skin.url}")
    return {"ok": True, "count": len(skins)}

@app.put("/api/skins/{index}")
def update_skin(index: int, skin: SkinConfig):
    skins = load_skins()
    if 0 <= index < len(skins):
        skins[index] = skin.model_dump()
        save_skins(skins)
        add_log(f"Updated skin {index + 1}")
        return {"ok": True}
    return {"ok": False, "error": "Invalid index"}

@app.delete("/api/skins/{index}")
def delete_skin(index: int):
    skins = load_skins()
    if 0 <= index < len(skins):
        removed = skins.pop(index)
        save_skins(skins)
        add_log(f"Removed skin: {removed['url']}")
        return {"ok": True, "count": len(skins)}
    return {"ok": False, "error": "Invalid index"}

# ---------- SETTINGS ----------

@app.get("/api/settings")
def get_settings():
    return load_settings()

@app.put("/api/settings")
def update_settings(settings: BotSettings):
    save_settings(settings.model_dump())
    add_log("Settings updated")
    return {"ok": True}

# ---------- BOT CONTROL ----------

@app.post("/api/bot/start")
def start_bot():
    global bot_thread
    if bot_status.running:
        return {"ok": False, "error": "Bot already running"}
    
    skins = load_skins()
    if not skins:
        return {"ok": False, "error": "No skins configured"}
    
    bot_stop_event.clear()
    bot_status.running = True
    bot_status.current_skin = 0
    bot_status.total_skins = len(skins)
    bot_status.cycle_count = 0
    
    add_log(f"Bot started with {len(skins)} skin(s)")
    
    # Bot will run in a background thread
    # For now, just mark as running — actual bot integration comes next
    bot_thread = threading.Thread(target=bot_worker, daemon=True)
    bot_thread.start()
    
    return {"ok": True}

@app.post("/api/bot/stop")
def stop_bot():
    if not bot_status.running:
        return {"ok": False, "error": "Bot not running"}
    
    bot_stop_event.set()
    bot_status.running = False
    add_log("Bot stopped")
    return {"ok": True}

@app.get("/api/bot/status")
def get_status():
    return bot_status.model_dump()

@app.post("/api/bot/warmup")
def warmup():
    """Buy a cheap skin to activate the session (skip phone confirmations)."""
    if bot_status.running:
        return {"ok": False, "error": "Stop the bot first"}
    
    add_log("Starting warmup purchase...")
    
    def warmup_worker():
        from bot_bridge import warmup_purchase
        result = warmup_purchase(add_log)
        return result
    
    # Run in background thread
    t = threading.Thread(target=warmup_worker, daemon=True)
    t.start()
    
    return {"ok": True, "message": "Warmup started — confirm on your phone!"}

# ---------- LOGS ----------

@app.get("/api/logs")
def get_logs(limit: int = 100):
    return log_messages[-limit:]

@app.get("/api/purchases")
def get_purchases():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

# ---------- WEBSOCKET ----------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        # Send current status immediately
        await websocket.send_text(json.dumps({
            "type": "status", **bot_status.model_dump()
        }))
        # Send recent logs
        for msg in log_messages[-50:]:
            await websocket.send_text(json.dumps({"type": "log", "message": msg}))
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)

# ---------- EXPORT CONFIG (for legacy bot) ----------

@app.get("/api/export-yaml")
def export_yaml():
    """Export current config as YAML (compatible with original bot)."""
    skins = load_skins()
    yaml_skins = []
    for s in skins:
        yaml_skins.append({
            "url": s["url"],
            "float": s.get("float_threshold"),
            "price": s.get("max_price"),
            "pattern": s.get("pattern"),
            "number_of_stickers": s.get("number_of_stickers"),
            "pages": s.get("pages"),
        })
    return {"yaml": yaml.dump({"skins": yaml_skins}, default_flow_style=False)}

# ============================================================
# BOT WORKER — bridges to actual Selenium bot
# ============================================================

def bot_worker():
    """Background thread that runs the real bot via bot_bridge."""
    from bot_bridge import run_bot
    
    skins = load_skins()
    settings = load_settings()
    
    def log_cb(msg):
        add_log(msg)
    
    def status_cb(updates):
        for key, val in updates.items():
            if hasattr(bot_status, key):
                setattr(bot_status, key, val)
        asyncio.run_coroutine_threadsafe(broadcast_status(), loop)
    
    try:
        run_bot(skins, settings, bot_stop_event, log_cb, status_cb)
    except Exception as e:
        add_log(f"FATAL: {e}")
    finally:
        bot_status.running = False
        bot_status.current_skin = 0
        bot_status.current_page = 0
        asyncio.run_coroutine_threadsafe(broadcast_status(), loop)

# ============================================================
# RUN
# ============================================================

def launch_chrome():
    """Launch Chrome with remote debugging if not already running."""
    import subprocess
    import platform
    import socket
    
    # Check if Chrome is already listening on port 9222
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect(("127.0.0.1", 9222))
        sock.close()
        print("[INFO] Chrome already running on port 9222")
        return
    except (ConnectionRefusedError, socket.timeout, OSError):
        sock.close()
    
    print("[INFO] Launching Chrome with remote debugging...")
    
    system = platform.system()
    if system == "Darwin":  # macOS
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Windows":
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:  # Linux
        chrome_path = "google-chrome"
    
    user_data = os.path.expanduser("~/ChromeDebug")
    
    subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data}",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for Chrome to be ready
    import time
    for _ in range(15):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", 9222))
            s.close()
            print("[INFO] Chrome is ready!")
            return
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(1)
    
    print("[WARN] Chrome may not be ready yet — try manually if connection fails")


if __name__ == "__main__":
    import uvicorn
    
    # Launch Chrome automatically
    launch_chrome()
    
    # Start the async event loop in a background thread for broadcasting
    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    
    print("\n  Steam Market Bot running at: http://localhost:8000\n")
    
    # Auto-open dashboard in default browser
    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
