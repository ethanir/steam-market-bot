"""
Diagnostic: Open a market page with CSFloat extension and check what it injects.
Run this, log into Steam in the browser, navigate to a BS skin listing, 
wait for floats to appear visually, then press Enter.
"""
import os
import glob
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()

chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

# Load CSFloat extension
CSFLOAT_EXT = glob.glob(os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Extensions/jjicbefpemnphinccgikpdaagjebbnhg/*"
))
if CSFLOAT_EXT:
    chrome_options.add_argument(f"--load-extension={CSFLOAT_EXT[0]}")
    print(f"[INFO] Loaded CSFloat extension from: {CSFLOAT_EXT[0]}")
else:
    print("[ERROR] CSFloat extension not found!")
    exit()

driver = webdriver.Chrome(options=chrome_options)

# Navigate to a BS skin page
url = "https://steamcommunity.com/market/listings/730/P250%20%7C%20Boreal%20Forest%20%28Battle-Scarred%29"
print(f"[INFO] Opening: {url}")
driver.get(url)

print("\n=== INSTRUCTIONS ===")
print("1. Log into Steam if needed")
print("2. Wait until you can SEE float values on the page (or not)")
print("3. Press ENTER here to run diagnostics")
input("\nPress ENTER when ready...")

print("\n=== DIAGNOSTIC RESULTS ===\n")

# Check 1: Are there listing rows?
rows = driver.find_elements("css selector", "#searchResultsRows .market_listing_row")
print(f"1. Market listing rows found: {len(rows)}")

# Check 2: Can we see the extension's elements?
js_check = """
const rows = document.querySelectorAll('#searchResultsRows .market_listing_row');
const results = [];
let idx = 0;

rows.forEach(row => {
    idx++;
    const info = {row: idx, customElements: [], shadowRoots: [], allText: '', dataAttrs: {}};
    
    // Find ALL custom elements (they have a dash in the tag name)
    const allEls = row.querySelectorAll('*');
    allEls.forEach(el => {
        if (el.tagName.includes('-')) {
            info.customElements.push(el.tagName.toLowerCase());
        }
        if (el.shadowRoot) {
            const shadowText = el.shadowRoot.textContent || '';
            info.shadowRoots.push({
                tag: el.tagName.toLowerCase(),
                textPreview: shadowText.substring(0, 200),
                innerHTML: el.shadowRoot.innerHTML.substring(0, 500)
            });
            
            // Check nested shadow roots
            const innerEls = el.shadowRoot.querySelectorAll('*');
            innerEls.forEach(inner => {
                if (inner.shadowRoot) {
                    const innerText = inner.shadowRoot.textContent || '';
                    info.shadowRoots.push({
                        tag: 'nested:' + inner.tagName.toLowerCase(),
                        textPreview: innerText.substring(0, 200),
                        innerHTML: inner.shadowRoot.innerHTML.substring(0, 500)
                    });
                }
            });
        }
    });
    
    // Get all data-* attributes on the row
    for (const attr of row.attributes) {
        if (attr.name.startsWith('data-')) {
            info.dataAttrs[attr.name] = attr.value;
        }
    }
    
    // Get direct text that might contain float
    info.allText = row.textContent.replace(/\\s+/g, ' ').substring(0, 300);
    
    if (idx <= 3) results.push(info);  // Only first 3 rows
});

return JSON.stringify(results, null, 2);
"""

result = driver.execute_script(js_check)
print(f"2. DOM analysis of first 3 rows:\n{result}")

# Check 3: Look for any csfloat-specific elements anywhere on page
js_csfloat = """
const csfloatEls = document.querySelectorAll('[class*="csfloat"], [id*="csfloat"], [class*="float"], csfloat-listing-row, csfloat-market-listing');
const found = [];
csfloatEls.forEach(el => {
    found.push({tag: el.tagName, id: el.id, class: el.className, text: (el.textContent || '').substring(0, 100)});
});
return JSON.stringify(found, null, 2);
"""
result2 = driver.execute_script(js_csfloat)
print(f"\n3. CSFloat-specific elements on page:\n{result2}")

# Check 4: Check if extension popup/banner exists
js_ext = """
const allCustom = document.querySelectorAll('*');
const customs = [];
allCustom.forEach(el => {
    if (el.tagName.includes('-') && !el.tagName.startsWith('OPTION')) {
        customs.push(el.tagName.toLowerCase());
    }
});
return [...new Set(customs)];
"""
result3 = driver.execute_script(js_ext)
print(f"\n4. All custom element tags on page: {result3}")

print("\n=== DONE ===")
print("Copy ALL output above and send it to me.")

input("\nPress ENTER to close browser...")
driver.quit()
