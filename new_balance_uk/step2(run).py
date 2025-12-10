#!/usr/bin/env python3
import os
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

# ---------------------------
# Folder setup
# ---------------------------
BASE_DIR = os.path.join("UK", "data", datetime.today().strftime("%Y-%m-%d"))
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
os.makedirs(ITEM_URLS_DIR, exist_ok=True)

url = "https://www.newbalance.co.uk/"
PRODUCT_SELECTOR = "div.pdp-link"

all_urls = []
structured_data = {}
SKIP_CATEGORIES = {"Help", "FAQ", "Order Status", "Return Order", "New"}

# ---------------------------
# Smooth scrolling
# ---------------------------
def human_scroll(page, min_step=300, max_step=700, delay_range=(0.2, 0.5)):
    """Scrolls gradually until no new content loads."""
    position = 0
    last_height = 0
    same_height_counter = 0
    max_same_height = 4

    print("🔽 Starting human-like scroll...")
    while True:
        scroll_height = page.evaluate("() => document.body.scrollHeight")
        if scroll_height == last_height:
            same_height_counter += 1
            if same_height_counter >= max_same_height:
                print("✅ Reached bottom (no more new content).")
                break
        else:
            same_height_counter = 0

        step = random.randint(min_step, max_step)
        position = min(position + step, scroll_height)
        page.evaluate(f"window.scrollTo(0, {position})")
        time.sleep(random.uniform(*delay_range))
        last_height = scroll_height


# ---------------------------
# Load all products
# ---------------------------
def load_all_products(page):
    prev_count = -1
    print("📦 Loading all products...")
    for _ in range(25):  # lower iteration limit to speed up
        human_scroll(page)

        btn = page.query_selector("button:has-text('Load more'), button.load-more")
        if btn:
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(random.randint(1500, 2500))
            except Exception:
                print("⚠️ Could not click Load More button.")
                pass

        html = page.content()
        curr_count = len(BeautifulSoup(html, "html.parser").select(PRODUCT_SELECTOR))
        print(f" → Currently loaded products: {curr_count}")

        if curr_count == prev_count:
            print("🛑 No new products found, stopping scroll.")
            break
        prev_count = curr_count
        page.wait_for_timeout(random.randint(1000, 2000))


# ---------------------------
# Extract product URLs
# ---------------------------
def extract_urls(page):
    load_all_products(page)
    soup = BeautifulSoup(page.content(), "html.parser")
    urls = []
    for div in soup.select(PRODUCT_SELECTOR):
        a = div.find("a", class_="pname")
        if a and a.get("href"):
            href = a["href"]
            full = href if href.startswith("http") else f"https://www.newbalance.co.uk/{href.lstrip('/')}"
            urls.append(full)
    return urls


# ---------------------------
# Load category URLs
# ---------------------------
category_file = os.path.join(ITEM_URLS_DIR, "newbalance_categories_filtered.json")
try:
    with open(category_file, "r", encoding="utf-8") as f:
        category_data = json.load(f)
except FileNotFoundError:
    print(f"❌ Category file '{category_file}' not found.")
    exit(1)

# ---------------------------
# Load existing scraped data
# ---------------------------
existing_file = os.path.join(ITEM_URLS_DIR, "all_products_by_category.json")
existing_data = {}
if os.path.exists(existing_file):
    try:
        with open(existing_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        print(f"✅ Loaded existing data: {sum(len(v) for v in existing_data.values())} subcategories.")
    except Exception as e:
        print(f"⚠️ Could not load existing data: {e}")

# ---------------------------
# Main scraping logic
# ---------------------------
with sync_playwright() as pw:
    try:
        browser = pw.firefox.launch(headless=False)

        # Flatten all subcategory URLs
        all_subcats = [
            (main, sub, url)
            for main, subs in category_data.items()
            if main.strip() not in SKIP_CATEGORIES
            for sub, url in subs.items()
        ]

        print(f"Total subcategories: {len(all_subcats)}")

        # Skip already scraped ones
        all_subcats = [
            (main, sub, url)
            for main, sub, url in all_subcats
            if main not in existing_data or sub not in existing_data[main]
        ]

        print(f"🆕 New subcategories to scrape: {len(all_subcats)}")

        for i in range(0, len(all_subcats), 2):
            batch = all_subcats[i:i+2]
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            print(f"\n🧭 Batch {i//2 + 1} ({len(batch)} subcategories)")

            for main_cat, subcat_name, url in batch:
                print(f"\n➡️ {main_cat} → {subcat_name}")
                structured_data.setdefault(main_cat, existing_data.get(main_cat, {}))

                retries = 0
                max_retries = 3
                page_relaunched = False

                while retries < max_retries:
                    try:
                        page.goto(url, timeout=60000)
                        page.wait_for_timeout(3000)  # short wait for stability

                        if not page.query_selector(PRODUCT_SELECTOR):
                            print(f"⚠️ No products found in {subcat_name}. Skipping...")
                            structured_data[main_cat][subcat_name] = {
                                "status": "no_products_found",
                                "category_url": url,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            with open(existing_file, "w", encoding="utf-8") as f:
                                json.dump(structured_data, f, indent=2)
                            break

                        html_content = page.content()
                        if "Oops" in html_content or "went wrong" in html_content:
                            retries += 1
                            print(f"⚠️ 'Oops something went wrong' → retry {retries}/{max_retries}")
                            page.close()
                            time.sleep(60)  # reduced cooldown from 10min → 1min
                            page = browser.new_page(viewport={"width": 1280, "height": 800})
                            page_relaunched = True
                            retries = 0
                            continue

                        page.wait_for_selector(PRODUCT_SELECTOR, timeout=30000)
                        urls = extract_urls(page)

                        if not urls:
                            retries += 1
                            print(f"🔁 Empty results → retry {retries}/{max_retries}")
                            page.reload()
                            time.sleep(5)
                            continue

                        # ✅ Success
                        all_urls.extend(urls)
                        structured_data[main_cat][subcat_name] = urls
                        print(f"✅ {len(urls)} products found for '{subcat_name}'")

                        with open(existing_file, "w", encoding="utf-8") as f:
                            json.dump(structured_data, f, indent=2)
                        break

                    except TimeoutError:
                        retries += 1
                        print(f"⏰ Timeout → retry {retries}/{max_retries}")
                        if retries >= max_retries and not page_relaunched:
                            page.close()
                            page = browser.new_page(viewport={"width": 1280, "height": 800})
                            retries = 0
                            page_relaunched = True
                        else:
                            page.reload()
                            time.sleep(5)

                    except Exception as e:
                        retries += 1
                        print(f"❌ Error: {e}")
                        if retries >= max_retries and not page_relaunched:
                            page.close()
                            page = browser.new_page(viewport={"width": 1280, "height": 800})
                            retries = 0
                            page_relaunched = True
                        else:
                            page.reload()
                            time.sleep(5)

            page.close()
            print(f"✅ Closed batch {i//2 + 1}")

        browser.close()

    except Exception as e:
        print(f"💥 Failed to run scraper: {e}")
        if 'browser' in locals():
            browser.close()

# ---------------------------
# Save final output
# ---------------------------
with open(os.path.join(ITEM_URLS_DIR, "all_products_by_category.json"), "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=2)

with open(os.path.join(ITEM_URLS_DIR, "all_product_urls_list.json"), "w", encoding="utf-8") as f:
    json.dump({"total": len(all_urls), "urls": all_urls}, f, indent=2)

unique = list(set(all_urls))
with open(os.path.join(ITEM_URLS_DIR, "all_product_urls_set.json"), "w", encoding="utf-8") as f:
    json.dump({"unique_count": len(unique), "urls": unique}, f, indent=2)

print(f"\n✅ Done. Scraped {len(all_urls)} | Unique: {len(unique)}")
