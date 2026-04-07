"""
Bot Bridge — connects the FastAPI backend to the actual Selenium bot logic.
This module handles:
1. Redirecting print() to the web UI log system
2. Importing functions.py (which connects to Chrome)
3. Converting web UI config to url_info format
4. Running the scan loop
"""
import sys
import os
import time
import random
import builtins
import threading

# Add parent directory to path so we can import functions.py, locators.py, etc.
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)


def convert_skins_to_url_info(skins):
    """Convert web UI skin format to the url_info format that functions.py expects.
    
    url_info[i][0] = float_threshold
    url_info[i][1] = pattern  
    url_info[i][2] = number_of_stickers
    url_info[i][3] = max_price
    url_info[i][4] = pages (max pages for this skin)
    url_info[i][5] = url
    """
    url_info = []
    for skin in skins:
        entry = [None] * 6
        entry[0] = skin.get("float_threshold")
        entry[1] = skin.get("pattern")
        entry[2] = skin.get("number_of_stickers")
        entry[3] = skin.get("max_price")
        entry[4] = skin.get("pages")
        entry[5] = skin.get("url")
        
        # Convert pattern string to list if needed (e.g. "502, 800" -> ["502", "800"])
        if entry[1] is not None and isinstance(entry[1], str):
            entry[1] = [p.strip() for p in entry[1].split(",")]
        
        url_info.append(entry)
    return url_info


def run_bot(skins, settings, stop_event, log_callback, status_callback):
    """
    Main bot loop. Runs in a background thread.
    
    Args:
        skins: list of skin dicts from the web UI
        settings: dict of bot settings from the web UI
        stop_event: threading.Event to signal stop
        log_callback: function(msg) to send log messages to the web UI
        status_callback: function(status_dict) to update status in the web UI
    """
    
    # Redirect print() to the log system
    original_print = builtins.print
    def patched_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        log_callback(msg)
        # Also print to terminal for debugging
        original_print(*args, **kwargs)
    
    builtins.print = patched_print
    
    try:
        # Import functions.py — this connects to Chrome via debugger
        log_callback("Connecting to Chrome browser...")
        
        try:
            import functions
            # Reload in case it was previously imported with different state
            import importlib
            importlib.reload(functions)
        except Exception as e:
            log_callback(f"ERROR: Could not connect to Chrome: {e}")
            log_callback("Make sure Chrome is running with: --remote-debugging-port=9222")
            return
        
        log_callback("Connected to Chrome!")
        
        # Set float mode
        float_mode = settings.get("float_mode", "over")
        functions.FLOAT_MODE = float_mode
        log_callback(f"Mode: {'OVER (buy >= threshold)' if float_mode == 'over' else 'UNDER (buy <= threshold)'}")
        
        # Convert skins to url_info format
        url_info = convert_skins_to_url_info(skins)
        max_pages = settings.get("max_pages", 6)
        cycle_cooldown = settings.get("cycle_cooldown", 15)
        
        log_callback(f"Loaded {len(url_info)} skin(s), max {max_pages} pages, {cycle_cooldown}s cooldown")
        
        # Main loop — same as csgo-market-sniper.py
        count = 0
        cycle = 0
        
        while not stop_event.is_set():
            # End of cycle
            if count == len(url_info):
                count = 0
                cycle += 1
                
                status_callback({
                    "cycle_count": cycle,
                    "current_skin": 0,
                    "current_page": 0,
                })
                
                cooldown = cycle_cooldown + random.uniform(0, 2)
                log_callback(f"[CYCLE {cycle}] All {len(url_info)} skin(s) done. Waiting {cooldown:.0f}s...")
                
                # Interruptible sleep
                for _ in range(int(cooldown)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                
                if stop_event.is_set():
                    break
                    
                log_callback(f"[CYCLE] Starting new cycle!")
            
            # Update status
            status_callback({
                "current_skin": count + 1,
                "total_skins": len(url_info),
                "cycle_count": cycle + 1,
            })
            
            log_callback(f"[SKIN {count+1}/{len(url_info)}]")
            
            # Navigate to skin URL
            try:
                functions.driver.get(url_info[count][5])
            except Exception as e:
                log_callback(f"ERROR: Could not load URL: {e}")
                count += 1
                continue
            
            # Scan the skin
            try:
                last_page, reason = functions.check_whole_page(count, url_info, max_pages=max_pages)
                
                # Update status with page info
                status_callback({"current_page": last_page})
                
                if reason == "price_exceeded":
                    log_callback(f"Hit max price on page {last_page}.")
                elif reason == "last_page":
                    log_callback(f"Scanned all {last_page} pages.")
                elif reason == "stale":
                    log_callback(f"Pages stuck at page {last_page}.")
                else:
                    log_callback(f"Stopped ({reason}) at page {last_page}.")
                    
            except Exception as e:
                log_callback(f"ERROR scanning skin {count+1}: {e}")
            
            count += 1
        
        log_callback("Bot stopped.")
        
        # Update balance one last time
        try:
            bal = functions.check_user_balance()
            if bal:
                status_callback({"balance": str(float(bal) / 100)})
        except Exception:
            pass
            
    except Exception as e:
        log_callback(f"FATAL ERROR: {e}")
    finally:
        builtins.print = original_print


def warmup_purchase(log_callback):
    """
    Buy a cheap $0.03 skin to activate the Steam session.
    After this, no more phone confirmations are needed.
    """
    import builtins
    original_print = builtins.print
    builtins.print = lambda *a, **k: log_callback(" ".join(str(x) for x in a))
    
    WARMUP_URL = "https://steamcommunity.com/market/listings/730/Tec-9%20%7C%20Blue%20Blast%20%28Field-Tested%29"
    
    try:
        # Import functions (connects to Chrome)
        log_callback("Connecting to Chrome...")
        try:
            import functions
            import importlib
            importlib.reload(functions)
        except Exception as e:
            log_callback(f"ERROR: Could not connect to Chrome: {e}")
            log_callback("Make sure Chrome is running with: --remote-debugging-port=9222")
            return {"ok": False, "error": str(e)}
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.webdriver.support import expected_conditions as ec
        from locators import PageLocators
        
        log_callback("Navigating to warmup skin (Tec-9 Blue Blast)...")
        functions.driver.get(WARMUP_URL)
        time.sleep(3)
        
        # Find and click the first buy button
        log_callback("Looking for buy button...")
        try:
            buy_buttons = WebDriverWait(functions.driver, 10).until(
                ec.presence_of_all_elements_located(PageLocators.BUY_BUTTON_END)
            )
            if not buy_buttons:
                log_callback("ERROR: No buy buttons found")
                return {"ok": False, "error": "No buy buttons found"}
            
            log_callback("Clicking buy button...")
            functions.driver.execute_script("arguments[0].click();", buy_buttons[0])
            time.sleep(1)
            
            # Accept SSA checkbox
            log_callback("Accepting Steam Subscriber Agreement...")
            check_box = WebDriverWait(functions.driver, 5).until(
                ec.element_to_be_clickable(PageLocators.CHECK_BOX)
            )
            functions.driver.execute_script("arguments[0].click();", check_box)
            
            # Click purchase
            purchase_btn = WebDriverWait(functions.driver, 5).until(
                ec.element_to_be_clickable(PageLocators.BUY_BUTTON)
            )
            functions.driver.execute_script("arguments[0].click();", purchase_btn)
            
            log_callback("⚡ Purchase initiated! Confirm on your phone NOW!")
            log_callback("Waiting up to 60 seconds for phone confirmation...")
            
            # Wait for "Purchase completed successfully" to appear
            confirmed = False
            for i in range(60):
                time.sleep(1)
                try:
                    page_text = functions.driver.execute_script("""
                        var dialogs = document.querySelectorAll('.newmodal, #market_buynow_dialog');
                        var text = '';
                        dialogs.forEach(function(d) { text += d.textContent; });
                        return text;
                    """)
                    if page_text and "Purchase completed successfully" in page_text:
                        log_callback("✅ Purchase confirmed! Closing dialog...")
                        # Click Close button
                        try:
                            close_btns = functions.driver.find_elements(By.CSS_SELECTOR, '.newmodal_close, #market_buynow_dialog_close, .btn_green_white_innerfade')
                            for btn in close_btns:
                                try:
                                    if btn.is_displayed():
                                        functions.driver.execute_script("arguments[0].click();", btn)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        confirmed = True
                        break
                except Exception:
                    pass
                
                if i % 10 == 9:
                    log_callback(f"Still waiting... ({i+1}s)")
            
            if confirmed:
                log_callback("✅ Warmup complete! You can now start the bot without phone confirmations.")
                return {"ok": True}
            else:
                # Try to close any dialog anyway
                try:
                    close_btns = functions.driver.find_elements(By.CSS_SELECTOR, '.newmodal_close')
                    if close_btns:
                        functions.driver.execute_script("arguments[0].click();", close_btns[0])
                except Exception:
                    pass
                log_callback("⚠️ Timed out waiting for confirmation. Try again or confirm manually.")
                return {"ok": False, "error": "Timed out waiting for phone confirmation"}
                
        except Exception as e:
            log_callback(f"ERROR during purchase: {e}")
            return {"ok": False, "error": str(e)}
            
    finally:
        builtins.print = original_print
