from functions import *
from config import load_config

# Login page load
cls()
driver.get("https://steamcommunity.com/login/home/?goto=market%2Flistings%2F730")

# Load config
url_info = load_config()
if url_info == None:
    driver.quit()
    sys.exit()

count = 0
input("Press enter to start if you are logged in and ready!")

# Ask float mode (OVER or UNDER)
ask_float_mode()

cls()
print("\n\n")

# ============================================================
# SETTINGS
# ============================================================
MAX_PAGES = 6          # scan pages 1-6 (the visible page links)
CYCLE_COOLDOWN = 3     # seconds between full cycles
# ============================================================

while True:
    if len(url_info) < 1:
        print("Populate config.yaml file and rerun. Exiting...")
        driver.quit()
        sys.exit()

    if count == len(url_info):
        count = 0
        cooldown = CYCLE_COOLDOWN + random.uniform(0, 2)
        print(f"\n[CYCLE] All {len(url_info)} skin(s) done. Waiting {cooldown:.0f}s...")
        time.sleep(cooldown)
        print(f"[CYCLE] Starting new cycle!\n")

    print(f"\n{'='*50}")
    print(f"[SKIN {count+1}/{len(url_info)}]")
    print(f"{'='*50}")

    driver.get(url_info[count][5])
    last_page, reason = check_whole_page(count, url_info, max_pages=MAX_PAGES)

    if reason == "price_exceeded":
        print(f"[DEBUG] Hit max price on page {last_page}.")
    elif reason == "last_page":
        print(f"[DEBUG] Scanned all {last_page} pages.")
    elif reason == "stale":
        print(f"[DEBUG] Pages stuck at page {last_page}.")
    else:
        print(f"[DEBUG] Stopped ({reason}) at page {last_page}.")

    count += 1
