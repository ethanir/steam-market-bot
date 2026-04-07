import os
import logging
import sys
import time
import random
import re
import math

import requests
import chromedriver_autoinstaller

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from locators import PageLocators

chromedriver_autoinstaller.install()

# Connect to existing Chrome with CSFloat extension active
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

driver = webdriver.Chrome(options=chrome_options)
buy_count = 0

print("[INFO] Connected to existing Chrome browser")

# ============================================================
# FLOAT MODE: "over" or "under" — set at startup
# ============================================================
FLOAT_MODE = "over"


def ask_float_mode():
    global FLOAT_MODE
    print("\n========================================")
    print("  FLOAT MODE SELECTION")
    print("========================================")
    print("  1) OVER  — buy skins with float ABOVE the threshold")
    print("  2) UNDER — buy skins with float BELOW the threshold")
    print("========================================")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            FLOAT_MODE = "over"
            print("[INFO] Mode: BUY skins with float >= threshold\n")
            return
        elif choice == "2":
            FLOAT_MODE = "under"
            print("[INFO] Mode: BUY skins with float <= threshold\n")
            return
        else:
            print("Invalid choice. Enter 1 or 2.")


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def progress_bar(progress, total, urlcount, buycount, page):
    percent = 100 * (progress / float(total)) if total > 0 else 0
    bar = chr(9608) * int(percent) + chr(9617) * (100 - int(percent))
    clr = "\x1B[0K"
    print(f"URL No: {urlcount} | Page: {page} | Orders executed: {buycount} | Balance: {check_user_balance()}{clr}")
    print(f"|{bar}| {percent:.2f}%{clr}")


def check_user_balance():
    try:
        user_balance = WebDriverWait(driver, 60).until(ec.presence_of_element_located(PageLocators.USER_BALANCE))
        return ''.join(c for c in user_balance.text if c.isdigit())
    except TimeoutException:
        sys.stderr.write("Can't load user balance.")
        driver.quit()


def buy_log(item_name, item_float, item_pattern, item_price, count):
    logger = logging.getLogger('BUYLOGGER')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler("purchaseHistory.log", mode='a')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s%(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S%p %Z')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f"Item name: {item_name} , Float: {item_float} , Pattern: {item_pattern} , Price: {item_price}")
    count += 1
    cls()


def check_stickers(sticker_data, quantity):
    try:
        stickers = sticker_data.get('stickers', [])
        if len(stickers) == 0:
            return False
        if len(stickers) != int(quantity):
            return False
        return True
    except (KeyError, TypeError, AttributeError):
        return False


def buy_skin(buy_button):
    print("[DEBUG] buy_skin: clicking buy button...")
    driver.execute_script("arguments[0].click();", buy_button)
    time.sleep(1)
    try:
        check_box = WebDriverWait(driver, 5).until(ec.element_to_be_clickable(PageLocators.CHECK_BOX))
        driver.execute_script("arguments[0].click();", check_box)
        purchase_btn = WebDriverWait(driver, 5).until(ec.element_to_be_clickable(PageLocators.BUY_BUTTON))
        driver.execute_script("arguments[0].click();", purchase_btn)
        print("[DEBUG] Purchase clicked! Waiting 30s for phone confirmation...")
        time.sleep(30)
        try:
            close_button = WebDriverWait(driver, 2).until(ec.element_to_be_clickable(PageLocators.CLOSE_BUTTON))
            driver.execute_script("arguments[0].click();", close_button)
        except Exception:
            close_btns = driver.find_elements(By.CSS_SELECTOR, '.newmodal_close')
            if close_btns:
                driver.execute_script("arguments[0].click();", close_btns[0])
            time.sleep(0.5)
        return True
    except TimeoutException:
        print("[DEBUG] buy_skin: TIMED OUT")
        return False


# ============================================================
# PAGE NAVIGATION — simple: click numbered links at bottom
# ============================================================

def find_next_page():
    try:
        next_page = WebDriverWait(driver, 3).until(ec.visibility_of_element_located(PageLocators.NEXT_PAGE))
        driver.execute_script("arguments[0].click();", next_page)
        time.sleep(1.5)
        return True
    except (TimeoutException, NoSuchElementException):
        return False


def go_to_page(target_page):
    """Click a numbered page link at the bottom. Falls back to next button."""
    # Try clicking the page number link
    try:
        page_links = driver.find_elements(By.CSS_SELECTOR, '#searchResults_links .market_paging_pagelink')
        for link in page_links:
            try:
                if link.text.strip() == str(target_page):
                    driver.execute_script("arguments[0].click();", link)
                    time.sleep(1.5)
                    return True
            except StaleElementReferenceException:
                continue
    except Exception:
        pass
    # Fallback: next button
    return find_next_page()


def load_purchase_buttons():
    try:
        WebDriverWait(driver, 10).until(ec.visibility_of_element_located(PageLocators.BUY_BUTTON_END))
        buy_buttons = driver.find_elements(*PageLocators.BUY_BUTTON_END)
        prices_box = driver.find_elements(*PageLocators.PRICES_BOX)
        inspect_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="steam://rungame/730/"]')
        return inspect_links, buy_buttons, prices_box
    except TimeoutException:
        sys.stderr.write("Cant find buy buttons\n")
        return


def needs_float_check(count, url_info):
    has_float = url_info[count][0] is not None
    has_pattern = url_info[count][1] is not None
    has_stickers = url_info[count][2] is not None
    return has_float or has_pattern or has_stickers


# ============================================================
# CSFLOAT EXTENSION INTEGRATION
# ============================================================

def scroll_to_listings():
    driver.execute_script("""
        var results = document.querySelector('#searchResultsTable') || 
                      document.querySelector('#searchResultsRows') ||
                      document.querySelector('.market_listing_table_header');
        if (results) {
            results.scrollIntoView({behavior: 'instant', block: 'start'});
            window.scrollBy(0, -150);
        } else {
            window.scrollTo(0, 1000);
        }
    """)
    time.sleep(0.3)


def click_sort_by_float():
    return driver.execute_script("""
        function findAndClick(root, depth) {
            if (depth > 10) return false;
            var els = root.querySelectorAll('*');
            for (var i = 0; i < els.length; i++) {
                var el = els[i];
                try {
                    var t = (el.textContent || '').trim();
                    if ((el.tagName === 'A' || el.tagName === 'SPAN' || el.tagName === 'BUTTON') && 
                        (t === 'Sort by Float' || t === 'Sort by Float ▲' || t === 'Sort by Float ▼')) {
                        el.click();
                        return t;
                    }
                } catch(e) {}
                if (el.shadowRoot) {
                    var result = findAndClick(el.shadowRoot, depth + 1);
                    if (result) return result;
                }
            }
            return false;
        }
        return findAndClick(document, 0);
    """)


def wait_for_csfloat_and_sort(timeout=20):
    """Wait for CSFloat, sort by float. Returns True if sorted."""
    scroll_to_listings()

    start = time.time()
    extension_ready = False
    while time.time() - start < timeout:
        has_floats = driver.execute_script("""
            function checkFloats(root, depth) {
                if (depth > 10) return false;
                var els = root.querySelectorAll('*');
                for (var i = 0; i < els.length; i++) {
                    try {
                        var t = (els[i].textContent || '');
                        if (t.match(/0\\.\\d{4,}/) && t.length < 200) return true;
                    } catch(e) {}
                    if (els[i].shadowRoot) {
                        if (checkFloats(els[i].shadowRoot, depth + 1)) return true;
                    }
                }
                return false;
            }
            return checkFloats(document, 0);
        """)
        if has_floats:
            extension_ready = True
            break
        time.sleep(0.5)

    if not extension_ready:
        print("[DEBUG] CSFloat didn't load in time")
        return False

    if FLOAT_MODE == "over":
        for i in range(2):
            result = click_sort_by_float()
            if not result:
                print("[DEBUG] Could not find Sort by Float button!")
                return False
            time.sleep(1.5)
    else:
        result = click_sort_by_float()
        if not result:
            print("[DEBUG] Could not find Sort by Float button!")
            return False
        time.sleep(1.5)

    scroll_to_listings()
    sort_label = "highest" if FLOAT_MODE == "over" else "lowest"
    print(f"[DEBUG] Sorted — {sort_label} floats first")
    return True


def wait_for_csfloat_on_page(timeout=12):
    """Wait for CSFloat on subsequent pages (no sort needed)."""
    scroll_to_listings()
    start = time.time()
    while time.time() - start < timeout:
        has_floats = driver.execute_script("""
            function checkFloats(root, depth) {
                if (depth > 10) return false;
                var els = root.querySelectorAll('*');
                for (var i = 0; i < els.length; i++) {
                    try {
                        var t = (els[i].textContent || '');
                        if (t.match(/0\\.\\d{4,}/) && t.length < 200) return true;
                    } catch(e) {}
                    if (els[i].shadowRoot) {
                        if (checkFloats(els[i].shadowRoot, depth + 1)) return true;
                    }
                }
                return false;
            }
            return checkFloats(document, 0);
        """)
        if has_floats:
            return True
        time.sleep(0.5)
    return False


def get_floats_from_extension():
    js = """
    function getFloats() {
        var rows = document.querySelectorAll('#searchResultsRows .market_listing_row');
        var results = [];
        rows.forEach(function(row) {
            var floatVal = null;
            var paintSeed = null;
            var stickerCount = 0;
            function searchShadow(root, depth) {
                if (depth > 10 || (floatVal && paintSeed)) return;
                var els = root.querySelectorAll('*');
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    try {
                        var t = (el.textContent || '');
                        if (!floatVal) {
                            var fm = t.match(/(0\\.\\d{4,})/);
                            if (fm) floatVal = parseFloat(fm[1]);
                        }
                        if (!paintSeed) {
                            var sm = t.match(/Paint\\s*Seed[:\\s]*(\\d+)/i);
                            if (sm) paintSeed = parseInt(sm[1]);
                        }
                    } catch(e) {}
                    if (el.shadowRoot) {
                        searchShadow(el.shadowRoot, depth + 1);
                    }
                }
            }
            searchShadow(row, 0);
            if (!floatVal) {
                var rowText = row.textContent || '';
                var dm = rowText.match(/Float[:\\s]*(0\\.\\d{4,})/i);
                if (dm) floatVal = parseFloat(dm[1]);
            }
            if (!paintSeed) {
                var rowText2 = row.textContent || '';
                var ps = rowText2.match(/Paint\\s*Seed[:\\s]*(\\d+)/i);
                if (ps) paintSeed = parseInt(ps[1]);
            }
            results.push({ float: floatVal, seed: paintSeed, stickers: stickerCount });
        });
        return results;
    }
    return getFloats();
    """
    try:
        return driver.execute_script(js)
    except Exception as e:
        print(f"[DEBUG] Error scraping floats: {e}")
        return []


def get_float_from_inspect_link(inspect_url):
    if not inspect_url or 'csgo_econ_action_preview' not in inspect_url:
        return None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1.1)
            response = requests.get(
                'https://api.csfloat.com/',
                params={'url': inspect_url},
                headers={'Origin': 'chrome-extension://jjicbefpemnphinccgikpdaagjebbnhg'},
                timeout=15
            )
            if response.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if response.status_code != 200:
                time.sleep(2)
                continue
            json_response = response.json()
            item_name = str(json_response["iteminfo"]["full_item_name"])
            item_float = float(json_response["iteminfo"]["floatvalue"])
            item_pattern = int(json_response["iteminfo"]["paintseed"])
            stickers = json_response["iteminfo"].get("stickers", [])
            return item_name, item_float, item_pattern, {"stickers": stickers}
        except Exception as e:
            print(f"[DEBUG] Float API error (attempt {attempt+1}): {e}")
            time.sleep(3)
    return None


# ============================================================
# MAIN PAGE CHECKING LOOP
# ============================================================

def check_whole_page(count, url_info, max_pages=6):
    """Scan pages 1 through max_pages for a skin.
    Returns (last_page_scanned, reason).
    reason: 'price_exceeded', 'done', 'last_page', 'stale', 'error'"""

    # Brief delay before starting
    skin_delay = random.uniform(1.5, 3)
    print(f"[DEBUG] Waiting {skin_delay:.1f}s...")
    time.sleep(skin_delay)

    require_api = needs_float_check(count, url_info)
    sorted_by_float = False
    print(f"[DEBUG] require_api={require_api}, float_threshold={url_info[count][0]}, max_price={url_info[count][3]}")

    # Sort by float on page 1
    if require_api:
        sorted_by_float = wait_for_csfloat_and_sort(timeout=20)
        print(f"[DEBUG] sorted_by_float={sorted_by_float}")

    total_pages = safe_page_count()
    items = total_pages * 10
    skin_count = 0
    last_float_sig = None
    stale_count = 0
    STALE_LIMIT = 1

    page = 0  # incremented at top of loop

    while page < max_pages:
        page += 1

        # Load elements
        try:
            result = load_purchase_buttons()
            if result is None:
                return (page, "error")
            inspect_links, buy_now, prices = result
        except (NoSuchElementException, TypeError):
            return (page, "error")

        # Parse prices
        try:
            price_text_num = []
            for price in prices:
                price_text_num.append(int(''.join(c for c in price.text if c.isdigit())) / 100)
        except (StaleElementReferenceException, ValueError):
            return (page, "error")

        # Get floats from extension
        page_floats = []
        if require_api and sorted_by_float:
            page_floats = get_floats_from_extension()
            if len(page_floats) > 0:
                print(f"[DEBUG] Extension returned {len(page_floats)} items, first float: {page_floats[0].get('float')}")
            else:
                print(f"[DEBUG] Extension returned 0 items")

        skin_count += 1
        progress_bar(skin_count, items, count + 1, buy_count, page)

        if len(price_text_num) == 0 or len(buy_now) == 0:
            return (page, "error")

        print(f"[DEBUG] Page {page} best listing | Price: {price_text_num[0]}")

        # Price check
        if not check_max_price(0, price_text_num, count, url_info):
            print(f"[DEBUG] Price ${price_text_num[0]} exceeds max ${url_info[count][3]}. Done.")
            return (page, "price_exceeded")

        if require_api:
            item_float = None
            item_pattern = None
            sticker_data = {"stickers": []}
            item_name = "From Extension"

            # Extension data
            if sorted_by_float and len(page_floats) > 0 and page_floats[0].get('float') is not None:
                item_float = page_floats[0]['float']
                item_pattern = page_floats[0].get('seed')
                sticker_count = page_floats[0].get('stickers', 0)
                sticker_data = {"stickers": [{}] * sticker_count} if sticker_count > 0 else {"stickers": []}
                print(f"[DEBUG] Float: {item_float} | Pattern: {item_pattern}")

            # API fallback
            elif len(inspect_links) > 0:
                href = inspect_links[0].get_attribute('href')
                float_result = get_float_from_inspect_link(href)
                if float_result is not None:
                    item_name, item_float, item_pattern, sticker_data = float_result
                    print(f"[DEBUG] Float (API): {item_float} | Pattern: {item_pattern}")

            # Stale detection — if same float repeats, pages aren't actually changing
            if item_float is not None:
                if item_float == last_float_sig:
                    stale_count += 1
                    if stale_count >= STALE_LIMIT:
                        print(f"[DEBUG] Same float {item_float} for {stale_count + 1} pages — stuck at page {page}.")
                        print(f"[DEBUG] Jumping ahead then scanning backwards...")
                        stuck_page = page
                        found_working = None

                        # Jump ahead to find a page that actually loads different content
                        for try_page in range(max_pages, stuck_page, -1):
                            print(f"[DEBUG] Trying page {try_page}...")
                            go_to_page(try_page)
                            time.sleep(1)
                            if require_api and sorted_by_float:
                                wait_for_csfloat_on_page(timeout=8)
                            tf = get_floats_from_extension()
                            tfv = tf[0].get('float') if len(tf) > 0 else None
                            if tfv is not None and tfv != last_float_sig:
                                print(f"[DEBUG] Page {try_page} works! Float: {tfv}")
                                found_working = try_page
                                break
                            else:
                                print(f"[DEBUG] Page {try_page} same content, trying lower...")
                            time.sleep(0.5)

                        if not found_working:
                            print(f"[DEBUG] Couldn't unstick. Moving to next skin.")
                            return (page, "stale")

                        # Scan backwards from found page down to stuck_page+1
                        last_back_float = None
                        for scan_page in range(found_working, stuck_page, -1):
                            if scan_page != found_working:
                                delay = random.uniform(1.5, 2.5)
                                time.sleep(delay)
                                go_to_page(scan_page)
                                if require_api and sorted_by_float:
                                    wait_for_csfloat_on_page(timeout=8)

                            pf = get_floats_from_extension()
                            if len(pf) > 0 and pf[0].get('float') is not None:
                                sf = pf[0]['float']
                                # Skip if this page has the original stale float or same as last scanned
                                if sf == last_float_sig:
                                    print(f"[DEBUG] Page {scan_page} still has stale float {sf}, skipping.")
                                    continue
                                if sf == last_back_float:
                                    print(f"[DEBUG] Page {scan_page} same as previous ({sf}), stuck again — stopping backwards scan.")
                                    break
                                last_back_float = sf
                                sp = pf[0].get('seed')
                                sc = pf[0].get('stickers', 0)
                                sd = {"stickers": [{}] * sc} if sc > 0 else {"stickers": []}
                                print(f"[DEBUG] Page {scan_page} | Float: {sf} | Pattern: {sp}")

                                if check_item_parameters(sf, sp, sd, count, url_info):
                                    try:
                                        pr = load_purchase_buttons()
                                        if pr:
                                            _, bns, prs = pr
                                            px = int(''.join(c for c in prs[0].text if c.isdigit())) / 100
                                            if check_max_price(0, [px], count, url_info):
                                                bal = float(check_user_balance()) / 100
                                                if bal >= px:
                                                    print(f"[DEBUG] >>> BUY at ${px}")
                                                    res = buy_skin(bns[0])
                                                    print(f"[DEBUG] Buy result: {res}")
                                                    buy_log("From Extension", sf, sp, px, buy_count)
                                            else:
                                                print(f"[DEBUG] Price ${px} exceeds max. Done.")
                                                return (scan_page, "price_exceeded")
                                    except Exception:
                                        pass
                                else:
                                    print(f"[DEBUG] No match on page {scan_page}")
                            else:
                                print(f"[DEBUG] No float data on page {scan_page}, skipping.")

                        return (found_working, "done")
                else:
                    stale_count = 0
                    last_float_sig = item_float

            # Check if it matches
            if item_float is not None and check_item_parameters(item_float, item_pattern, sticker_data, count, url_info):
                try:
                    user_bal_num = float(check_user_balance()) / 100
                except (ValueError, TypeError):
                    sys.stderr.write("Can't get balance. Logged in?")
                    driver.quit()
                    sys.exit()

                if user_bal_num >= price_text_num[0]:
                    print(f"[DEBUG] >>> BUY at ${price_text_num[0]}")
                    result = buy_skin(buy_now[0])
                    print(f"[DEBUG] Buy result: {result}")
                    buy_log(item_name, item_float, item_pattern, price_text_num[0], buy_count)
                else:
                    print("[DEBUG] Not enough balance")
            else:
                if item_float is not None:
                    print(f"[DEBUG] No match — best float on page {page} is {item_float}")
                else:
                    print(f"[DEBUG] Couldn't read float on page {page}")
        else:
            # No float check — buy first listing
            item_name = "Unknown"
            item_float = "N/A"
            item_pattern = "N/A"
            try:
                user_bal_num = float(check_user_balance()) / 100
            except (ValueError, TypeError):
                sys.stderr.write("Can't get balance. Logged in?")
                driver.quit()
                sys.exit()

            if user_bal_num >= price_text_num[0]:
                print(f"[DEBUG] >>> BUY at ${price_text_num[0]}")
                result = buy_skin(buy_now[0])
                print(f"[DEBUG] Buy result: {result}")
                buy_log(item_name, item_float, item_pattern, price_text_num[0], buy_count)
            else:
                print("[DEBUG] Not enough balance")

        # Check page limits from config
        if url_info[count][4] is not None:
            if page >= url_info[count][4]:
                print(f"[DEBUG] Reached config page limit ({url_info[count][4]}).")
                return (page, "done")

        if page >= total_pages:
            print(f"[DEBUG] Last page ({total_pages}).")
            return (page, "last_page")

        # Navigate to next page — skip ahead if a page fails
        if page < max_pages:
            delay = random.uniform(1.5, 3)
            print(f"[DEBUG] Waiting {delay:.1f}s before next page...")
            time.sleep(delay)

            navigated = False
            skipped = []
            for try_page in range(page + 1, min(page + 4, max_pages + 1)):
                if go_to_page(try_page):
                    if try_page > page + 1:
                        print(f"[DEBUG] Skipped to page {try_page} (pages {page+1}-{try_page-1} failed)")
                    page = try_page - 1  # will be +1'd at top of while loop
                    navigated = True
                    break
                else:
                    skipped.append(try_page)
                    print(f"[DEBUG] Page {try_page} failed, trying next...")
                    time.sleep(1)

            if not navigated:
                # Try going back to skipped pages
                for skip_page in skipped:
                    if go_to_page(skip_page):
                        print(f"[DEBUG] Went back to skipped page {skip_page}")
                        page = skip_page - 1
                        navigated = True
                        break
                    time.sleep(1)

            if not navigated:
                print(f"[DEBUG] Can't navigate past page {page}. Stopping.")
                return (page, "error")

            # Wait for CSFloat on new page
            if require_api and sorted_by_float:
                wait_for_csfloat_on_page(timeout=10)

    return (page, "done")


def check_item_parameters(item_float, item_pattern, sticker_data, count, url_info):
    if url_info[count][0] is not None:
        threshold = float(url_info[count][0])
        if FLOAT_MODE == "over":
            if item_float < threshold:
                return False
        else:
            if item_float > threshold:
                return False

    if url_info[count][1] is not None:
        match = False
        if type(url_info[count][1]) is not int:
            for pattern in url_info[count][1]:
                if int(pattern) == item_pattern:
                    match = True
                    break
            if not match:
                return False

    if url_info[count][2] is not None:
        if not check_stickers(sticker_data, url_info[count][2]):
            return False

    return True


def check_max_price(order, price, count, url_info):
    if url_info[count][3] is not None:
        if float(url_info[count][3]) <= float(price[order]):
            return False
    return True


def safe_page_count():
    for _ in range(3):
        try:
            WebDriverWait(driver, 3).until(ec.presence_of_element_located(PageLocators.LAST_PAGE))
            last_page = driver.find_elements(*PageLocators.LAST_PAGE)
            if last_page:
                text = last_page[-1].text.strip()
                if text.isdigit():
                    return int(text)
            return 1
        except (TimeoutException, StaleElementReferenceException, IndexError):
            time.sleep(0.5)
    return 1


def page_count():
    return safe_page_count()


def actual_page_number():
    try:
        actual = WebDriverWait(driver, 2).until(ec.presence_of_element_located(PageLocators.PAGE_NUMBER)).text
        return int(actual)
    except (TimeoutException, ValueError, StaleElementReferenceException):
        return 1


def safe_items_on_page():
    try:
        return int(safe_page_count()) * 10
    except Exception:
        return 100


def items_on_page():
    return safe_items_on_page()
