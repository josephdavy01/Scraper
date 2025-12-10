import os
import json
import asyncio
import random
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError, Page

today = date.today().strftime("%Y-%m-%d")
# today = '2025-12-01'
CATEGORY_FILE = f"UK/data/{today}/Item_urls/category_urls.json"
PRODUCT_FILE = f"UK/data/{today}/Item_urls/product_urls.json"
BASE_URL = "https://www.brooksrunning.com"

async def random_delay(min_sec=1, max_sec=3):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

def load_category_urls():
    with open(CATEGORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_product_urls(data):
    folder_path = os.path.dirname(PRODUCT_FILE)
    os.makedirs(folder_path, exist_ok=True)
    with open(PRODUCT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Product URLs saved to {PRODUCT_FILE}")

async def handle_popups(page: Page):
    try:
        cookie_btn = page.locator(
            "button#onetrust-accept-btn-handler, button.cookie-accept, button.accept-cookies"
        )
        if await cookie_btn.is_visible():
            print("Cookie popup detected, clicking accept...")
            await cookie_btn.click()
            await random_delay(1, 2)
    except Exception:
        pass

async def handle_geo_popup(page):
    try:
        geo_modal = page.locator("div.o-geolocation-modal")
        if await geo_modal.is_visible(timeout=6000):
            print("Geo selection popup detected, handling...")
            uk_radio = page.locator("input#defaultCountry")
            if await uk_radio.is_visible():
                await uk_radio.check()
                await asyncio.sleep(0.5)
            apply_btn = page.locator("a.js-apply-country-change")
            if await apply_btn.is_visible():
                await apply_btn.click()
                await asyncio.sleep(1.5)
                print("Geo selection applied.")
            else:
                print("'Apply' button not found or already clicked.")
        else:
            print("Geo popup not visible, proceeding...")
    except Exception as e:
        print(f"Couldn't handle geo popup: {e}")

async def handle_sailthru_popup(page):
    try:
        close_btn = page.locator('button.sailthru-overlay-close')
        if await close_btn.is_visible(timeout=6000):
            print("Sailthru overlay detected, closing...")
            await close_btn.click()
            await asyncio.sleep(1)
        else:
            print("Sailthru overlay not present.")
    except Exception as e:
        print(f"Couldn't close Sailthru overlay: {e}")

async def scroll_and_load_products(page: Page, step=400, delay_ms=1500, stable_threshold=5):
    print("Starting initial scroll to show 'Load All' button...")
    prev_height = await page.evaluate("() => document.body.scrollHeight")
    stable_count = 0
    scroll_count = 0
    max_initial_scrolls = 1000
    while scroll_count < max_initial_scrolls:
        await page.evaluate(f"window.scrollBy(0, {step});")
        await asyncio.sleep(delay_ms / 1000)
        await handle_popups(page)
        await handle_geo_popup(page)
        await handle_sailthru_popup(page)
        load_all_btn = page.locator("button.js-load-more-button.js-load-more-products")
        if await load_all_btn.is_visible():
            print("'Load All' button appeared, clicking it...")
            await load_all_btn.click()
            await asyncio.sleep(random.uniform(2, 4))
            break
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == prev_height:
            stable_count += 1
            if stable_count >= stable_threshold:
                print("Reached bottom before 'Load All' appeared, breaking initial scroll.")
                break
        else:
            stable_count = 0
        prev_height = new_height
        scroll_count += 1
    print("Scrolling to load remaining products...")
    prev_height = await page.evaluate("() => document.body.scrollHeight")
    stable_count = 0
    scroll_count = 0
    max_final_scrolls = 1000
    while scroll_count < max_final_scrolls:
        await page.evaluate(f"window.scrollBy(0, {step});")
        await asyncio.sleep(delay_ms / 1000)
        await handle_popups(page)
        await handle_geo_popup(page)
        await handle_sailthru_popup(page)
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == prev_height:
            stable_count += 1
            if stable_count >= stable_threshold:
                print("All products loaded, stopping scroll.")
                break
        else:
            stable_count = 0
        prev_height = new_height
        scroll_count += 1
    print("Scrolling and loading complete!")

async def scrape_product_urls(category_data):
    product_data = {}
    if os.path.exists(PRODUCT_FILE):
        with open(PRODUCT_FILE, "r", encoding="utf-8") as f:
            product_data = json.load(f)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        for main_cat, subcats in category_data.items():
            if main_cat not in product_data:
                product_data[main_cat] = {}
            for cat_name, cat_url in subcats.items():
                clean_cat_name = cat_name.replace("caret right_", "")
                if clean_cat_name in product_data[main_cat]:
                    print(f"Skipping already scraped category: {main_cat} -> {clean_cat_name}")
                    continue
                print(f"Scraping {main_cat} -> {clean_cat_name} ...")
                urls = []
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await page.goto(cat_url, wait_until="networkidle", timeout=60000)
                        await handle_popups(page)
                        await handle_geo_popup(page)
                        await handle_sailthru_popup(page)
                        await asyncio.sleep(random.uniform(2, 4))
                        await scroll_and_load_products(page)
                        break
                    except TimeoutError:
                        print(f"Attempt {attempt + 1} failed for {cat_url}. Retrying...")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(random.uniform(2, 5))
                        else:
                            print(f"Failed to load {cat_url} after {max_retries} attempts.")
                            continue
                print("Extracting product URLs...")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                product_items = soup.find_all("li", class_="o-products-grid__item o-products-grid__item--col-1")
                print(f"Found {len(product_items)} product items...")
                for item in product_items:
                    try:
                        anchor = item.find("a", class_="js-grid-anchor m-product-tile__item-content-link")
                        if anchor and anchor.get("href"):
                            full_url = urljoin(BASE_URL, anchor["href"])
                            urls.append(full_url)
                        else:
                            print("No valid anchor tag found in product item.")
                    except Exception as e:
                        print(f"Error processing product item: {e}")
                urls = list(set(urls))
                print(f"Extracted {len(urls)} product URLs for {main_cat} -> {clean_cat_name}")
                product_data[main_cat][clean_cat_name] = urls
                save_product_urls(product_data)
        await browser.close()
    return product_data

if __name__ == "__main__":
    category_data = load_category_urls()
    asyncio.run(scrape_product_urls(category_data))
