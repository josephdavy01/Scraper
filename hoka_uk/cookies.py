import os
import json
import time
from playwright.sync_api import sync_playwright

COOKIES_JSON_FILE = "cookies.json"
TARGET_URL = "https://www.hoka.com/en/gb/"

def save_cookies_from_hoka():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled"
        ])
        context = browser.new_context()
        page = context.new_page()

        # Apply basic stealth
        page.evaluate("""
            () => {
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                window.navigator.chrome = { runtime: {} };
            }
        """)

        # Go to Hoka main page and wait for the nav bar instead of full network idle
        print(f"➡️ Open {TARGET_URL} and solve CAPTCHA manually...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_selector("ul.nav.navbar-nav.navbar-category-links", timeout=60000)

        # Optional: simulate small human-like interaction
        page.mouse.move(100, 100)
        time.sleep(1)
        page.mouse.move(200, 300)
        time.sleep(1)

        # Save cookies
        cookies = context.cookies()
        with open(COOKIES_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        print(f"✅ Cookies saved to {COOKIES_JSON_FILE}")

        input("Press Enter to close the browser...")
        browser.close()

if __name__ == "__main__":
    save_cookies_from_hoka()
