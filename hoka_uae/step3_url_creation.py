import os
import json
import time
import random
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

# === CONFIGURATION ===
CAPTCHA_WAIT_SECONDS = 5
COOKIES_FILE = "cookies.json"
MAX_RETRIES = 3
MAIN_PAGE = "https://www.hoka.com/en/ae/"

# === LOAD AND NORMALIZE COOKIES ===
def load_cookies():
    if not os.path.exists(COOKIES_FILE):
        print("cookies.json not found. Continuing without cookies.")
        return []

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        normalized = []
        for cookie in cookies:
            c = cookie.copy()
            for key in ['hostOnly', 'session', 'storeId', 'id']:
                c.pop(key, None)
            ss = c.get("sameSite", "Lax")
            if isinstance(ss, str):
                ss_lower = ss.lower()
                if ss_lower in ["strict"]:
                    c["sameSite"] = "Strict"
                elif ss_lower in ["lax", "unspecified"]:
                    c["sameSite"] = "Lax"
                elif ss_lower in ["none", "no_restriction"]:
                    c["sameSite"] = "None"
                else:
                    c["sameSite"] = "Lax"
            else:
                c["sameSite"] = "Lax"
            if c.get("domain", "").startswith("."):
                c["domain"] = c["domain"].lstrip(".")
            normalized.append(c)
        print(f"Loaded {len(normalized)} cookies from {COOKIES_FILE}")
        return normalized
    except Exception as e:
        print(f"Failed to load cookies: {e}")
        return []

# === BROWSER SETUP WITH REAL CHROME AND STEALTH ===
def setup_context(pw, proxy_info=None):
    launch_args = {
        "headless": False,
        "args": ["--start-maximized", "--disable-blink-features=AutomationControlled"]
    }

    # Add proxy if provided
    if proxy_info:
        launch_args["proxy"] = {
            "server": proxy_info['server'],      # e.g., "http://ip:port"
            "username": proxy_info.get('username', None),
            "password": proxy_info.get('password', None)
        }
        print(f"Using proxy: {proxy_info['server']}")

    browser = pw.chromium.launch(channel="chrome",**launch_args)
    context = browser.new_context()

    # Add cookies
    cookies = load_cookies()
    if cookies:
        try:
            context.add_cookies(cookies)
            print("Cookies added to context.")
        except Exception as e:
            print(f"Failed to set cookies: {e}")

    page = context.new_page()

    # Apply stealth scripts
    page.evaluate("""() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    }""")

    return context, browser, page


# === SIMULATE HUMAN INTERACTIONS ===
def simulate_user_behavior(page):
    for i in range(random.randint(2, 5)):
        x = random.randint(0, 500)
        y = random.randint(0, 800)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.5, 1.5))
    #page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3)")
    #time.sleep(random.uniform(1.5, 3))
    #page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3)")
    #time.sleep(random.uniform(1.5, 3))
    page.evaluate("window.scrollBy(0, document.body.scrollHeight / 3)")
    time.sleep(random.uniform(2, 4))

def extract_variants_from_page(page, product_url,max_retries=3):
    attempt=0
    while attempt<max_retries:
        try:
            print(f"Visiting product page: {product_url} (Attempt {attempt+1})")
            page.goto(product_url, timeout=60000)
            simulate_user_behavior(page)

            html_content = page.content()
            if "access denied" in html_content.lower():
                raise Exception("Blocked")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            container = soup.select_one("div.container.product-detail.product-wrapper.boxed")
            if not container:
                print("Product container not found, skipping")
                return []

            url_pid = product_url.split("/")[-1].split(".html")[0]

            swatches = []
            # Look for all buttons under color attribute divs
            for attr_div in container.select("div.attribute.js-has-swatches.attribute-type-color"):
                div_pid = attr_div.get("data-pid")
                if div_pid != url_pid:
                    continue  # Skip if PID doesn't match

                buttons = attr_div.select("button.pull-left")
                for btn in buttons:
                    # Take all spans inside the button
                    for span in btn.select(
                        "span.color-value.swatch.swatch-square.swatch-image.swatch-value, "
                        "span.color-value.swatch.swatch-circle.swatch-image.swatch-value"
                    ):
                        if span.get("data-attr-value"):
                            swatches.append(span)

            base_url = product_url.split("?")[0]
            pid = url_pid
            variants = [
                f"{base_url}?dwvar_{pid}_color={span.get('data-attr-value')}"
                for span in swatches
            ]
            print(f"Found {len(variants)} variant(s) for {product_url}")
            return variants

        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            attempt += 1
            time.sleep(random.uniform(5, 10))

    print(f"All attempts failed for {product_url}")
    return []

def process_variant_urls(country, today_str):
    base_path = f"{country}/Data/{today_str}/Item_urls"
    input_path = os.path.join(base_path, f"{country}_unique_product_ids.json")
    output_path = os.path.join(base_path, f"{country}_variant_product_ids.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not os.path.exists(input_path):
        print(f" Input file not found: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        product_data = json.load(f)

    result_data = {}
    url_counter= 0

    with sync_playwright() as pw:
        context, browser, page = setup_context(pw)

        for attempt in range(3):
            try:
                print(f"Visiting main page: {MAIN_PAGE} (Attempt {attempt+1})")
                page.goto(MAIN_PAGE, timeout=60000)
                page.wait_for_selector("ul.nav.navbar-nav.navbar-category-links", timeout=30000)
                simulate_user_behavior(page)
                break
            except Exception as e:
                print(f"Main page visit failed: {e}")
                time.sleep(random.uniform(5, 10))

        for main_cat, subcats in product_data.items():
            print(f"\n Main Category: {main_cat}")

            if isinstance(subcats, list):
                all_urls = subcats
            elif isinstance(subcats, dict):
                all_urls = [u for urls in subcats.values() for u in urls]
            else:
                print(f"Skipping unknown format under: {main_cat}")
                continue

            # Skip if no color URLs
            if not any("color=" in u for u in all_urls):
                print(f"No color URLs in {main_cat}, skipping...")

            category_result = {}

            if isinstance(subcats, list):
                combined_list = []
                for url in subcats:
                    url_counter += 1
                    variants=[]
                    # Only extract variants if URL has color parameter
                    if "color=" in url:
                        variants = extract_variants_from_page(page, url)
                        if variants:
                            combined_list.extend(variants)
                        else:
                            combined_list.append(url)
                    else:
                        combined_list.append(url)

                    # Close and reopen browser every 4 products
                    if url_counter % 4 == 0:
                        print("Resetting browser to avoid block...")
                        context.close()
                        browser.close()
                        context, browser, page = setup_context(pw)
                        for attempt in range(3):
                            try:
                                page.goto(MAIN_PAGE, timeout=60000)
                                page.wait_for_selector("ul.nav.navbar-nav.navbar-category-links", timeout=30000)
                                simulate_user_behavior(page)
                                break
                            except Exception as e:
                                print(f"Main page visit failed: {e}")
                                time.sleep(random.uniform(5, 10))

                result_data[main_cat] = combined_list

            elif isinstance(subcats, dict):
                category_result={}
                for subcat, urls in subcats.items():
                    print(f"    Subcategory: {subcat}")
                    combined_list = []
                    for url in urls:
                        url_counter += 1
                        variants=[]
                        if "color=" in url:
                            variants = extract_variants_from_page(page, url)
                            if variants:
                                combined_list.extend(variants)
                            else:
                                combined_list.append(url)
                        else:
                            combined_list.append(url)

                        if url_counter % 4 == 0:
                            print("Resetting browser to avoid block...")
                            context.close()
                            browser.close()
                            context, browser, page = setup_context(pw)
                            for attempt in range(3):
                                try:
                                    page.goto(MAIN_PAGE, timeout=60000)
                                    page.wait_for_selector("ul.nav.navbar-nav.navbar-category-links", timeout=30000)
                                    simulate_user_behavior(page)
                                    break
                                except Exception as e:
                                    print(f"Main page visit failed: {e}")
                                    time.sleep(random.uniform(5, 10))

                    category_result[subcat] = combined_list

                result_data[main_cat] = category_result
        context.close()
        browser.close()

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)

    print(f"\n Variant product URLs saved to: {output_path}")

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    countries = ['UAE']
    for country in countries:
        process_variant_urls(country, today_str)
