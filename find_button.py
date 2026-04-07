from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
d = webdriver.Chrome(options=opts)

# Scroll down first
d.execute_script("window.scrollTo(0, 600)")
import time
time.sleep(2)

result = d.execute_script("""
    function deepSearch(root, depth) {
        var results = [];
        if (depth > 10) return results;
        var els = root.querySelectorAll('*');
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            try {
                var t = (el.textContent || '').trim();
                if (t.includes('Sort by Float') && t.length < 100) {
                    results.push({depth: depth, tag: el.tagName, text: t.substring(0,60), hasShadow: !!el.shadowRoot});
                }
                if (t.includes('Powered by CSFloat') && t.length < 100) {
                    results.push({depth: depth, tag: el.tagName, text: t.substring(0,60), hasShadow: !!el.shadowRoot});
                }
            } catch(e) {}
            if (el.shadowRoot) {
                results = results.concat(deepSearch(el.shadowRoot, depth + 1));
            }
        }
        return results;
    }
    return deepSearch(document, 0);
""")

print("=== SORT BUTTON SEARCH ===")
for r in result:
    print(r)

if not result:
    print("Nothing found! Checking all custom elements...")
    result2 = d.execute_script("""
        var customs = [];
        function findCustom(root, depth) {
            if (depth > 5) return;
            var els = root.querySelectorAll('*');
            for (var i = 0; i < els.length; i++) {
                if (els[i].tagName.includes('-')) {
                    customs.push({depth: depth, tag: els[i].tagName, hasShadow: !!els[i].shadowRoot});
                }
                if (els[i].shadowRoot) findCustom(els[i].shadowRoot, depth + 1);
            }
        }
        findCustom(document, 0);
        return customs;
    """)
    for r in result2:
        print(r)
