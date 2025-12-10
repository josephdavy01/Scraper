import json
import os
import asyncio
from datetime import date, datetime
from playwright.async_api import async_playwright

# Define today's date
today = date.today().strftime("%Y-%m-%d")
base_dir = os.path.join("India", "data", today, "Item_urls")
os.makedirs(base_dir, exist_ok=True)

CATEGORY_FILE = os.path.join(base_dir, "category_id.json")
OUTPUT_FILE = os.path.join(base_dir, "product_urls.json")

PRODUCT_API = (
    "https://www.uniqlo.com/in/api/commerce/v3/en/products"
    "?categoryId={cat_id}&groupBy=subCategoryId&limit=24&offset={offset}&imageRatio=3x4&isV2Review=true"
)
PRODUCT_BASE = "https://www.uniqlo.com/in/en/products/{pid}?"

async def fetch_api(page, cat_id, offset):
    url = PRODUCT_API.format(cat_id=cat_id, offset=offset)
    await page.goto(url)
    pre_text = await page.inner_text("pre")
    return json.loads(pre_text)

async def main():
    # Only run on Monday, Wednesday, or Friday
    day = datetime.today().strftime('%A')
    if day not in ['Monday', 'Wednesday', 'Friday']:
        print(f"Today is {day}. Skipping script execution.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Load category data
        if not os.path.exists(CATEGORY_FILE):
            print(f"Category file not found: {CATEGORY_FILE}")
            await browser.close()
            return

        with open(CATEGORY_FILE, "r", encoding="utf-8") as f:
            category_data = json.load(f)

        product_urls = {}

        for gender, subcats in category_data.items():
            gender_map = {}
            for subcat_name, cat_id in subcats.items():
                print(f"Fetching products for {gender} → {subcat_name} (id={cat_id})")
                collected_ids = set()
                offset = 0
                total = None

                while True:
                    data = await fetch_api(page, cat_id, offset)
                    result = data.get("result", {})
                    products = result.get("groupedItems", {})

                    for prod_list in products.values():
                        for prod in prod_list:
                            pid = prod.get("productId")
                            if pid:
                                collected_ids.add(pid)

                    pagination = result.get("pagination", {})
                    count = pagination.get("count", 0)
                    total = pagination.get("total", total)
                    next_offset = pagination.get("offset", offset + count)

                    if total is None or len(collected_ids) >= total or count == 0:
                        break

                    offset = next_offset

                urls = [PRODUCT_BASE.format(pid=pid) for pid in sorted(collected_ids)]
                if urls:
                    gender_map[subcat_name] = urls

            if gender_map:
                product_urls[gender] = gender_map

        await browser.close()

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(product_urls, f, indent=2, ensure_ascii=False)

        print(f"Done! Saved product URLs to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
