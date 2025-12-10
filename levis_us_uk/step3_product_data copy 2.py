#!/usr/bin/env python3
import os
import json
import re
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# -------------------------------------------------------------------
# 1️⃣ Directory setup
# -------------------------------------------------------------------
today = '2025-11-05'
BASE_DIR = os.path.join("UK", "data", today)
ITEM_URLS_DIR = os.path.join(BASE_DIR, "item_urls")
JSON_DATA_DIR = os.path.join(BASE_DIR, "json_data")
os.makedirs(JSON_DATA_DIR, exist_ok=True)

# -------------------------------------------------------------------
# 2️⃣ Load product URLs (handle multiple formats)
# -------------------------------------------------------------------
json_path = os.path.join(ITEM_URLS_DIR, "All_Product_URLs_Unique.json")
print("📄 Reading:", json_path)

if not os.path.exists(json_path):
    raise FileNotFoundError(f"❌ File not found: {json_path}")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Detect structure automatically
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

    # --- Extract ld+json data ---
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

    # --- Extract launch price ---
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
        "launch_price": launch_price  # ✅ Added here
    }


def get_firefox_driver():
    """Create a new Firefox instance."""
    service = Service()
    options = webdriver.FirefoxOptions()
    options.add_argument("--start-maximized")
    # Uncomment for headless scraping:
    # options.add_argument("--headless")
    driver = webdriver.Firefox(service=service, options=options)
    return driver


def human_like_scroll(driver, steps=6):
    """Simulate slow, human-like scrolling."""
    print("    🖱️ Scrolling through product page...")
    for _ in range(steps):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight/6);")
        time.sleep(random.uniform(1.5, 3.0))
    print("    ✅ Finished scrolling.")


def human_delay(label="Resting", min_delay=18, max_delay=25):
    """Pause between actions to look human."""
    delay = random.uniform(min_delay, max_delay)
    print(f"    ⏸️ {label} for {delay:.1f}s...")
    time.sleep(delay)


# -------------------------------------------------------------------
# 4️⃣ Scrape all products (human-like, batch of 2)
# -------------------------------------------------------------------
total_scraped = 0
batch_size = 2
driver = None

for idx, url in enumerate(product_urls, start=1):
    print(f"\n🔎 [{idx}/{len(product_urls)}] {url}")

    # --- Determine output filename and skip if already scraped ---
    pid = re.findall(r"/p/([^/]+)$", url)
    pid = pid[0] if pid else f"product_{idx}"
    out_file = os.path.join(JSON_DATA_DIR, f"{sanitize_filename(pid)}.json")

    if os.path.exists(out_file):
        print(f"    ⏭️ Skipping (already saved): {out_file}")
        continue

    # Launch browser if not running or at the start of a new batch
    if driver is None or (idx - 1) % batch_size == 0:
        if driver:
            driver.quit()
            print("    🔴 Browser closed for batch cooldown.")
            print("    💤 Taking 20s break before next batch...")
            time.sleep(20)

        pre_delay = random.uniform(5, 10)
        print(f"    🚀 Launching new browser in {pre_delay:.1f}s...")
        time.sleep(pre_delay)
        driver = get_firefox_driver()

    try:
        driver.get(url)

        # Wait for page load
        think_delay = random.uniform(3, 6)
        print(f"    🤔 Browsing page... waiting {think_delay:.1f}s.")
        time.sleep(think_delay)

        # Check for "Access Denied"
        if re.search(r"access\s*denied", driver.page_source, re.I):
            print("    🚫 Access Denied detected! Closing browser and waiting 10m...")
            driver.quit()
            driver = None
            time.sleep(600)
            continue

        # Wait for main content
        try:
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main, h1"))
            )
        except TimeoutException:
            print("    ⚠️ Timeout waiting for main content")
            continue

        # Extra JS wait
        time.sleep(random.uniform(5, 8))

        # Retry loading scripts a few times
        for _ in range(3):
            scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            if scripts:
                break
            time.sleep(3)

        # Scroll
        human_like_scroll(driver)

        html = driver.page_source
        product_data = extract_product_data(html)
        product_data["url"] = url

        # Save JSON
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)

        total_scraped += 1
        print(f"    ✅ Saved → {out_file}")

        # Human cooldown between products
        human_delay("Taking a break", 18, 25)

    except WebDriverException as e:
        print(f"    ❌ WebDriver error: {e}")
        if driver:
            driver.quit()
            driver = None
            print("    💤 Waiting 30s before relaunch due to WebDriver error...")
            time.sleep(30)
        continue
    except Exception as e:
        print(f"    ⚠️ Unexpected error: {e}")
        continue

# Cleanup after loop
if driver:
    driver.quit()
print(f"\n✅ Finished scraping {total_scraped} products total.")
