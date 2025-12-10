import json
import os
import asyncio
from datetime import date, datetime
from playwright.async_api import async_playwright

today = date.today().strftime("%Y-%m-%d")
base_dir = os.path.join("India", "data", today, "Item_urls")
os.makedirs(base_dir, exist_ok=True)
CATEGORY_URL_FILE = os.path.join(base_dir, "category_urls.json")
OUTPUT_FILE = os.path.join(base_dir, "category_id.json")
API_URL = "https://www.uniqlo.com/in/api/commerce/v3/en/products/taxonomies?withSubcategories=false"

async def fetch_api_data():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(API_URL)
        pre_text = await page.inner_text("pre")
        await browser.close()
        return json.loads(pre_text)

async def main():
    day = datetime.today().strftime('%A')
    if day not in ["Monday", "Wednesday", "Friday"]:
        print(f"Today is {day}. Script runs only on Monday, Wednesday, and Friday. Exiting.")
        return

    with open(CATEGORY_URL_FILE, "r", encoding="utf-8") as f:
        category_urls = json.load(f)
    valid_keys = {}
    for gender, cats in category_urls.items():
        valid_keys.setdefault(gender, set())
        for cat_name in cats.keys():
            valid_keys[gender].add(cat_name)
    api_data = await fetch_api_data()
    categories = api_data["result"]["categories"]
    output = {"men": {}, "women": {}, "kids": {}, "baby": {}}
    for cat in categories:
        cat_id = cat["id"]
        cat_name = cat["name"].strip()
        parents = cat.get("parents", [])
        gender = None
        parent_name = None
        for p in parents:
            if p["key"] in ["men", "women", "kids", "baby"]:
                gender = p["key"]
            else:
                parent_name = p["name"]
        if gender and parent_name:
            key = f"{parent_name}_{cat_name}"
            if key in valid_keys.get(gender, set()):  # only keep if present in category_urls.json
                output[gender][key] = cat_id
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Done! Saved filtered category IDs to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
