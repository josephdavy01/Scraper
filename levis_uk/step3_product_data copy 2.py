#!/usr/bin/env python3
import os
import json
import re
import asyncio
import random
import time
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# -------------------------------------------------------------------
# 1️⃣ Directory setup
# -------------------------------------------------------------------
today = '2025-11-07'
BASE_DIR = os.path.join("UK", "data", today)
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
JSON_DATA_DIR = os.path.join(BASE_DIR, "json_data")
os.makedirs(JSON_DATA_DIR, exist_ok=True)

# -------------------------------------------------------------------
# 2️⃣ Load product URLs
# -------------------------------------------------------------------
json_path = os.path.join(ITEM_URLS_DIR, "All_Product_URLs_Unique.json")
print("📄 Reading:", json_path)

if not os.path.exists(json_path):
    raise FileNotFoundError(f"❌ File not found: {json_path}")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

if isinstance(data, dict) and "urls" in data:
    product_urls = data["urls"]
elif isinstance(data, list):
    product_urls = data
elif isinstance(data, dict):
    for v in data.values():
        if isinstance(v, list):
            product_urls = v
            break
    else:
        raise ValueError("❌ No valid URL list found in JSON file.")
else:
    raise ValueError("❌ Unsupported JSON format.")

print(f"✅ Loaded {len(product_urls)} product URLs.\n")

# -------------------------------------------------------------------
# 3️⃣ Utility functions
# -------------------------------------------------------------------
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", str(name))


def extract_product_data(html):
    """Extract ld+json, sizes, composition, features, and launch price."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Extract ld+json ---
    ld_json_data = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string.strip())
            if isinstance(data, dict) and data.get("@type") == "Product":
                ld_json_data = data
                break
        except Exception:
            continue

    # --- Available sizes ---
    size_buttons = soup.select("li.size-tile-list-item button[aria-disabled='false']")
    available_sizes = [btn.get_text(strip=True) for btn in size_buttons]

    # --- Composition & Features ---
    composition, features = [], []
    for container in soup.select("div.contentContainer"):
        parent = container.find_previous_sibling("div")
        if parent and "Composition" in parent.get_text():
            composition = [li.get_text(strip=True) for li in container.select("li")]
        else:
            possible_features = [li.get_text(strip=True) for li in container.select("li")]
            if any(len(text.split()) < 10 for text in possible_features):
                features.extend(possible_features)

    # --- Launch price ---
    launch_price = None
    price_tag = soup.find("span", class_="price strikedOut")
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        price_match = re.search(r"[\d.,]+", price_text)
        if price_match:
            launch_price = price_match.group().replace(",", "")

    return {
        "ld_json": ld_json_data,
        "available_sizes": available_sizes,
        "composition": composition,
        "features": features,
        "launch_price": launch_price
    }


async def human_like_scroll(page, steps=6):
    """Simulate human scrolling."""
    print("    🖱️ Scrolling through product page...")
    for _ in range(steps):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight / 6)")
        await asyncio.sleep(random.uniform(1.5, 3.0))
    print("    ✅ Finished scrolling.")


async def human_delay(label="Resting", min_delay=18, max_delay=25):
    delay = random.uniform(min_delay, max_delay)
    print(f"    ⏸️ {label} for {delay:.1f}s...")
    await asyncio.sleep(delay)

# -------------------------------------------------------------------
# 4️⃣ Main Scraper (Playwright)
# -------------------------------------------------------------------
async def scrape_all_products():
    total_scraped = 0
    batch_size = 2

    async with async_playwright() as p:
        browser = None

        for idx, url in enumerate(product_urls, start=1):
            print(f"\n🔎 [{idx}/{len(product_urls)}] {url}")

            pid_match = re.findall(r"/p/([^/]+)$", url)
            pid = pid_match[0] if pid_match else f"product_{idx}"
            out_file = os.path.join(JSON_DATA_DIR, f"{sanitize_filename(pid)}.json")

            if os.path.exists(out_file):
                print(f"    ⏭️ Skipping (already saved): {out_file}")
                continue

            # Relaunch browser in batches
            if browser is None or (idx - 1) % batch_size == 0:
                if browser:
                    await browser.close()
                    print("    🔴 Browser closed for batch cooldown.")
                    print("    💤 Taking 20s break before next batch...")
                    await asyncio.sleep(20)

                pre_delay = random.uniform(5, 10)
                print(f"    🚀 Launching new browser in {pre_delay:.1f}s...")
                await asyncio.sleep(pre_delay)

                browser = await p.firefox.launch(headless=False)
                context = await browser.new_context(viewport={"width": 1280, "height": 800})
                page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.uniform(3, 6))

                # Access denied check
                page_text = await page.content()
                if re.search(r"access\s*denied", page_text, re.I):
                    print("    🚫 Access Denied! Waiting 10 minutes...")
                    await browser.close()
                    browser = None
                    await asyncio.sleep(600)
                    continue

                # Wait for main content
                try:
                    await page.wait_for_selector("main, h1", timeout=45000)
                except Exception:
                    print("    ⚠️ Timeout waiting for main content")
                    continue

                await asyncio.sleep(random.uniform(5, 8))
                await human_like_scroll(page)

                html = await page.content()
                product_data = extract_product_data(html)
                product_data["url"] = url

                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(product_data, f, indent=2, ensure_ascii=False)

                total_scraped += 1
                print(f"    ✅ Saved → {out_file}")

                await human_delay("Taking a break", 18, 25)

            except Exception as e:
                print(f"    ⚠️ Error on {url}: {e}")
                continue

        if browser:
            await browser.close()

    print(f"\n✅ Finished scraping {total_scraped} products total.")


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(scrape_all_products())
