import os
import time
import json
from datetime import date
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

COOKIES_JSON_FILE = "cookies.json"

def setup_browser(playwright, cookies_path, base_url):
    browser = playwright.chromium.launch(
        headless=False, channel="chrome",
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context()

    # Load cookies (if present)
    if os.path.exists(cookies_path):
        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        fixed_cookies = []
        for cookie in cookies:
            for key in ['hostOnly', 'session', 'storeId', 'id']:
                cookie.pop(key, None)

            if 'sameSite' in cookie:
                ss = cookie['sameSite'].lower() if isinstance(cookie['sameSite'], str) else None
                if ss in ["no_restriction", "none"]:
                    cookie['sameSite'] = "None"
                elif ss in ["lax", "unspecified"]:
                    cookie['sameSite'] = "Lax"
                elif ss in ["strict"]:
                    cookie['sameSite'] = "Strict"
                else:
                    cookie.pop('sameSite', None)

            if cookie.get("domain", "").startswith("."):
                cookie["domain"] = cookie["domain"].lstrip(".")

            fixed_cookies.append(cookie)

        context.add_cookies(fixed_cookies)
        print(f"Loaded {len(fixed_cookies)} cookies from {cookies_path}")
    else:
        print(f"Cookies file '{cookies_path}' not found. Continuing without cookies.")

    page = context.new_page()
    page.goto(base_url, timeout=60000)
    return browser, page

def fix_urls(data, base_url):
    if isinstance(data, dict):
        return {k: fix_urls(v, base_url) for k, v in data.items()}
    elif isinstance(data, str):
        return urljoin(base_url, data)
    return data


# ------------------------
# Scroll Function (yours)
# ------------------------
def slow_two_pass_scroll(page, step=800, delay_ms=1000, max_rounds=200, stable_checks=3):
    selector = "div.fr-ec-product-collection a[href]"
    prod_locator = page.locator(selector)

    def get_count():
        try:
            return prod_locator.count()
        except Exception:
            return 0

    print("Starting fast scroll (incremental, 1s between steps)...")
    prev_count = -1
    stable = 0
    rounds = 0

    while rounds < max_rounds:
        page.evaluate(f"window.scrollBy(0, {step});")
        page.wait_for_timeout(delay_ms)
        rounds += 1
        count = get_count()
        print(f"  Scroll {rounds}: {count} products visible")

        if count == prev_count:
            stable += 1
        else:
            stable = 0
        prev_count = count

        at_bottom = page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 50")
        if at_bottom and stable >= stable_checks:
            print(f"Scroll finished: reached bottom and stable ({count} products).")
            break

    page.wait_for_timeout(1000)
    print("Scrolling complete.")


def scrape_categories(page, output_dir, base_url, country_code):
    print("Scraping categories...")
    result = {}

    soup = BeautifulSoup(page.content(), "html.parser")
    nav = soup.find("ul", class_="nav navbar-nav navbar-category-links")

    allowed_main_categories = ['men', 'women', 'new', 'outlet', 'kids']

    if not nav:
        print("Navigation bar not found")
        return {}

    for li in nav.find_all("li", class_="nav-item", recursive=False):
        main_name_tag = li.find("span")
        main_link_tag = li.find("a")

        if not main_name_tag or not main_link_tag:
            continue

        main_name = main_name_tag.get_text(strip=True).lower()
        main_url = main_link_tag.get("href")

        if main_name not in allowed_main_categories:
            continue

        dropdown_ul = li.find("ul", class_="dropdown-menu")

        if not dropdown_ul:
            result[main_name] = {main_name: main_url}
            continue

        result[main_name] = {}
        for level1_li in dropdown_ul.find_all("li", recursive=False):
            classes = level1_li.get("class", [])
            if not all(c in classes for c in ["dropdown-item", "nav-item", "level-1", "top-category"]):
                continue

            level1_name_tag = level1_li.find("span")
            if not level1_name_tag:
                continue
            level1_name = level1_name_tag.get_text(strip=True).lower()

            level2_ul = level1_li.find("ul", class_="dropdown-menu")
            if not level2_ul:
                continue

            for level2_li in level2_ul.find_all("li", class_="dropdown-item nav-item level-2"):
                level2_name_tag = level2_li.find("span")
                level2_link_tag = level2_li.find("a")

                if level2_name_tag and level2_link_tag:
                    level2_name = level2_name_tag.get_text(strip=True).lower()
                    level2_url = level2_link_tag.get("href")

                    key = f"{level1_name}_{level2_name}"
                    result[main_name][key] = level2_url

    result = fix_urls(result, base_url)

    output_file = os.path.join(output_dir, f"{country_code}_category_urls.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Subcategories saved to: {output_file}")

    return result


# ------------------------
# Updated extract function
# ------------------------
def extract_product_links(page, base_url):
    product_links = set()
    prev_count = -1

    while True:
        # 1. Scroll down
        slow_two_pass_scroll(page)

        # 2. Parse current products
        soup = BeautifulSoup(page.content(), 'html.parser')
        tiles = soup.select("div.tile-row.col-6.col-md-4, div.product-tile")
        for tile in tiles:
            a = tile.find("a", href=True)
            if a:
                href = a["href"]
                full_url = urljoin(base_url, href)
                product_links.add(full_url)

        print(f"Collected {len(product_links)} products so far.")

        # 3. Try Load More
        try:
            load_more = page.query_selector("button[data-url*='Search-UpdateGrid']")
            if load_more and load_more.is_enabled():
                print("Clicking Load More button...")
                load_more.scroll_into_view_if_needed()
                load_more.click()
                page.wait_for_timeout(5000)
                continue
            else:
                print("No Load More button found or disabled. Ending extraction.")
                break
        except Exception as e:
            print(f"Load More error: {e}")
            break

        if len(product_links) == prev_count:
            print("No new products loaded, stopping.")
            break
        prev_count = len(product_links)

    return list(product_links)


def scrape_products(page, subcategory_urls, output_dir, base_url, country_code):
    print("\nScraping product URLs...")
    all_results = {}

    for main_cat, subcats in subcategory_urls.items():
        print(f"\nMain category: {main_cat}")
        main_result = {}

        if isinstance(subcats, str):
            try:
                page.goto(subcats, timeout=60000)
                page.wait_for_timeout(10000)
                page.wait_for_selector("div.product-tile, div.tile-row", timeout=10000)
                urls = extract_product_links(page, base_url)
                print(f"  → {len(urls)} products found.")
                main_result = urls
            except Exception as e:
                print(f"Error loading {subcats}: {e}")
                continue
        else:
            for subcat, url in subcats.items():
                print(f"  Subcategory: {subcat}")
                urls = []
                try:
                    page.goto(url, timeout=60000)
                    page.wait_for_timeout(10000)
                    page.wait_for_selector("div.product-tile, div.tile-row", timeout=10000)
                    urls = extract_product_links(page, base_url)
                    print(f"    → {len(urls)} products found.")
                except Exception as e:
                    print(f"Error loading {url}: {e}")
                main_result[subcat] = urls

        all_results[main_cat] = main_result

    output_file = os.path.join(output_dir, f"{country_code}_product_ids.json")
    with open(output_file, 'w', encoding='utf-8') as f_out:
        json.dump(all_results, f_out, ensure_ascii=False, indent=4)
    print(f"\nAll product URLs saved to: {output_file}")


def main_playwright(country):
    base_url = "https://www.hoka.com/en/ae/"
    today_str = date.today().strftime('%Y-%m-%d')
    output_dir = os.path.join(country, "Data", today_str, "Item_urls")
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser, page = setup_browser(p, COOKIES_JSON_FILE, base_url)

        try:
            print("Waiting for navigation bar to load...")
            page.wait_for_selector("ul.nav.navbar-nav.navbar-category-links", timeout=30000)
            print("Navigation bar loaded. Starting scraping...")

            subcategory_urls = scrape_categories(page, output_dir, base_url, country)
            scrape_products(page, subcategory_urls, output_dir, base_url, country)

            print("\nScraping finished.")

        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    main_playwright("UAE")
