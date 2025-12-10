#!/usr/bin/env python3
"""
Levi's Product Scraper (Full Pagination + Infinite Scroll)
Skips already scraped categories if present in saved results.
"""

import os, json, time, random, logging
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List, Set

from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# LOGGING & PATHS
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

today = datetime.today().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("USA", "data", today)
ITEM_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_DIR, exist_ok=True)

INPUT_FILE = os.path.join(ITEM_DIR, "Category_urls.json")
OUTPUT_NESTED = os.path.join(ITEM_DIR, "All_Product_URLs_by_Category.json")
OUTPUT_FLAT = os.path.join(ITEM_DIR, "All_Product_URLs_Flat.json")
OUTPUT_UNIQUE = os.path.join(ITEM_DIR, "All_Product_URLs_Unique.json")

# ----------------------------------------------------------------------
# BROWSER SETUP
# ----------------------------------------------------------------------
options = Options()
options.headless = False
service = FirefoxService()
driver = webdriver.Firefox(service=service, options=options)
driver.maximize_window()
driver.set_page_load_timeout(120)
driver.set_script_timeout(120)

# ----------------------------------------------------------------------
# HUMAN-LIKE SCROLLING
# ----------------------------------------------------------------------
def human_like_scroll(driver, max_scrolls=250):
    last_height = driver.execute_script("return document.body.scrollHeight")
    same_count = 0
    for i in range(max_scrolls):
        scroll_height = random.randint(400, 1200)
        driver.execute_script(f"window.scrollBy(0, {scroll_height});")
        time.sleep(random.uniform(1.0, 2.0))
        if random.random() < 0.2:
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(random.uniform(0.5, 1.2))
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            same_count += 1
            if same_count >= 5:
                break
        else:
            same_count = 0
        last_height = new_height
    time.sleep(random.uniform(2, 4))

# ----------------------------------------------------------------------
# EXTRACT PRODUCT URLs
# ----------------------------------------------------------------------
def extract_product_urls(driver) -> Set[str]:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    urls = set()
    for a in soup.select("a.product-link"):
        href = a.get("href")
        if href:
            full = href if href.startswith("http") else urljoin("https://www.levi.com/US/en_US/", href)
            urls.add(full)
    return urls

# ----------------------------------------------------------------------
# CLICK NEXT PAGE
# ----------------------------------------------------------------------
def click_next_page(driver) -> bool:
    next_selectors = [
        "a[aria-label='Next']",
        "li.next-btn a",
        "button.next",
        ".pagination-next a",
        "a.pagination__next",
    ]
    for sel in next_selectors:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 3))
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_button)
            time.sleep(random.uniform(0.5, 2.0))
            driver.execute_script("arguments[0].click();", next_button)
            logging.info("➡️ Clicked Next Page")
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.results-grid.-show"))
            )
            time.sleep(random.uniform(4, 7))
            return True
        except (TimeoutException, NoSuchElementException,
                ElementClickInterceptedException, StaleElementReferenceException):
            continue
    return False

# ----------------------------------------------------------------------
# SCRAPE ONE CATEGORY
# ----------------------------------------------------------------------
def scrape_category(category_name: str, category_url: str) -> List[str]:
    logging.info(f"\n{'='*25} SCRAPING {category_name} {'='*25}")
    all_urls: Set[str] = set()
    page_num = 1

    pause = random.uniform(20, 60)
    logging.info(f"🕒 Waiting {pause:.1f}s before loading category '{category_name}'...")
    time.sleep(pause)

    try:
        driver.get(category_url)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.results-grid.-show"))
        )
        time.sleep(random.uniform(5, 8))
    except TimeoutException:
        logging.warning("⚠️ Page load timeout — skipping category.")
        return []

    while True:
        logging.info(f"📄 Page {page_num} — scrolling and collecting products...")
        human_like_scroll(driver)
        urls = extract_product_urls(driver)
        logging.info(f"✅ Found {len(urls)} products on this page.")
        all_urls.update(urls)
        logging.info(f"📊 Total so far: {len(all_urls)}")

        next_clicked = False
        for _ in range(3):
            if click_next_page(driver):
                next_clicked = True
                break
            else:
                time.sleep(random.uniform(3, 6))
        if not next_clicked:
            logging.info("⏹️ No more pages detected.")
            break
        page_num += 1
        time.sleep(random.uniform(4, 8))

    logging.info(f"🎉 Finished {category_name}: {len(all_urls)} URLs")
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

        logging.info("💾 Progress saved successfully.")
    except Exception as e:
        logging.error(f"⚠️ Error while saving progress: {e}")

# ----------------------------------------------------------------------
# PROCESS CATEGORY TREE WITH SKIP LOGIC
# ----------------------------------------------------------------------
def process_node(node: Dict, result_dict: Dict, existing_data: Dict):
    for name, value in node.items():
        if isinstance(value, str):
            # ✅ Skip category if already scraped
            if name in existing_data and existing_data[name]:
                logging.info(f"⏩ Skipping '{name}' — already scraped ({len(existing_data[name])} URLs).")
                result_dict[name] = existing_data[name]
                continue

            result_dict[name] = scrape_category(name, value)
            save_progress(all_data)
        elif isinstance(value, dict):
            result_dict[name] = {}
            existing_sub = existing_data.get(name, {})
            process_node(value, result_dict[name], existing_sub)

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # 🔹 Load previous results if available
    existing_data = {}
    if os.path.exists(OUTPUT_NESTED):
        try:
            with open(OUTPUT_NESTED, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            logging.info("📂 Loaded existing scraped data.")
        except Exception as e:
            logging.warning(f"⚠️ Failed to load previous data: {e}")

    global all_data
    all_data = existing_data.copy()

    try:
        process_node(categories, all_data, existing_data)
    finally:
        driver.quit()

    save_progress(all_data)
    logging.info("\n✅ DONE — ALL CATEGORIES SCRAPED")

# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
