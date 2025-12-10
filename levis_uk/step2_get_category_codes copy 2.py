#!/usr/bin/env python3
"""
Levi's Product Scraper (Playwright + Firefox Version)
Optimized scrolling + pagination + skip logic + progress saving.
"""

import os, json, time, random, asyncio, logging
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ----------------------------------------------------------------------
# LOGGING & PATHS
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

today = datetime.today().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("UK", "data", today)
ITEM_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_DIR, exist_ok=True)

INPUT_FILE = os.path.join(ITEM_DIR, "Category_urls.json")
OUTPUT_NESTED = os.path.join(ITEM_DIR, "All_Product_URLs_by_Category.json")
OUTPUT_FLAT = os.path.join(ITEM_DIR, "All_Product_URLs_Flat.json")
OUTPUT_UNIQUE = os.path.join(ITEM_DIR, "All_Product_URLs_Unique.json")


# ----------------------------------------------------------------------
# SCROLLING
# ----------------------------------------------------------------------
async def human_like_scroll(page, max_scrolls=100):
    """Scroll down gradually and stop when bottom reached."""
    last_height = await page.evaluate("() => document.body.scrollHeight")
    same_count = 0

    for _ in range(max_scrolls):
        await page.evaluate(f"window.scrollBy(0, {random.randint(500, 1200)})")
        await asyncio.sleep(random.uniform(0.5, 1.2))
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            same_count += 1
            if same_count >= 3:
                break
        else:
            same_count = 0
        last_height = new_height
    await asyncio.sleep(random.uniform(1, 2))


# ----------------------------------------------------------------------
# EXTRACT PRODUCT URLs
# ----------------------------------------------------------------------
async def extract_product_urls(page) -> Set[str]:
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.select("a.product-link"):
        href = a.get("href")
        if href:
            full = href if href.startswith("http") else urljoin("https://www.levi.com/GB/en_GB/", href)
            urls.add(full)
    return urls


# ----------------------------------------------------------------------
# CLICK NEXT PAGE
# ----------------------------------------------------------------------
async def click_next_page(page) -> bool:
    selectors = [
        "a[aria-label='Next']",
        "li.next-btn a",
        "button.next",
        ".pagination-next a",
        "a.pagination__next",
    ]
    for sel in selectors:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            btn = await page.wait_for_selector(sel, timeout=1000)
            await btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await btn.click()
            logging.info("Clicked Next Page")
            await page.wait_for_selector("div.results-grid.-show", timeout=3000)
            await asyncio.sleep(random.uniform(2, 4))
            return True
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return False


# ----------------------------------------------------------------------
# SCRAPE ONE CATEGORY
# ----------------------------------------------------------------------
async def scrape_category(page, category_name: str, category_url: str) -> List[str]:
    logging.info(f"{'='*25} SCRAPING {category_name} {'='*25}")
    all_urls: Set[str] = set()
    page_num = 1

    try:
        await page.goto(category_url, timeout=9000)
        await page.wait_for_selector("div.results-grid.-show", timeout=9000)
        await asyncio.sleep(random.uniform(2, 4))
    except PlaywrightTimeout:
        logging.warning("Page load timeout — skipping category.")
        return []

    while True:
        logging.info(f"Page {page_num} — scrolling and collecting products...")
        await human_like_scroll(page)
        urls = await extract_product_urls(page)
        logging.info(f"Found {len(urls)} products on this page.")
        all_urls.update(urls)
        logging.info(f"Total so far: {len(all_urls)}")

        # Try next page up to 2 retries
        for _ in range(2):
            if await click_next_page(page):
                page_num += 1
                break
            await asyncio.sleep(2)
        else:
            logging.info("No more pages detected.")
            break

    logging.info(f"Finished {category_name}: {len(all_urls)} URLs")
    return sorted(all_urls)


# ----------------------------------------------------------------------
# SAVE PROGRESS
# ----------------------------------------------------------------------
def save_progress(all_data):
    try:
        with open(OUTPUT_NESTED, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        flat = []
        def flatten(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    flatten(v)
            elif isinstance(obj, list):
                flat.extend(v for v in obj)
        flatten(all_data)

        unique = sorted(set(flat))
        with open(OUTPUT_FLAT, "w", encoding="utf-8") as f:
            json.dump({"total": len(flat), "urls": flat}, f, indent=2, ensure_ascii=False)
        with open(OUTPUT_UNIQUE, "w", encoding="utf-8") as f:
            json.dump({"unique_count": len(unique), "urls": unique}, f, indent=2, ensure_ascii=False)

        logging.info("Progress saved successfully.")
    except Exception as e:
        logging.error(f"Error while saving progress: {e}")


# ----------------------------------------------------------------------
# PROCESS CATEGORY TREE (recursive)
# ----------------------------------------------------------------------
async def process_node(page, node: Dict, result_dict: Dict, existing_data: Dict):
    for name, value in node.items():
        if isinstance(value, str):
            if name in existing_data and existing_data[name]:
                logging.info(f"Skipping '{name}' — already scraped ({len(existing_data[name])} URLs).")
                result_dict[name] = existing_data[name]
                continue

            result_dict[name] = await scrape_category(page, name, value)
            save_progress(all_data)
        elif isinstance(value, dict):
            result_dict[name] = {}
            existing_sub = existing_data.get(name, {})
            await process_node(page, value, result_dict[name], existing_sub)


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
async def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # Load previous results if available
    existing_data = {}
    if os.path.exists(OUTPUT_NESTED):
        try:
            with open(OUTPUT_NESTED, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            logging.info("Loaded existing scraped data.")
        except Exception as e:
            logging.warning(f"Failed to load previous data: {e}")

    global all_data
    all_data = existing_data.copy()

    async with async_playwright() as p:
        # 🦊 Correct Firefox launch (awaited)
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await process_node(page, categories, all_data, existing_data)
        finally:
            await browser.close()

    save_progress(all_data)
    logging.info("DONE — ALL CATEGORIES SCRAPED")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
