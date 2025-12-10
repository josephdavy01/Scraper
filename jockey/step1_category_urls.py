import os
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time

POP_KEYS = ["Accessories"]

async def category_urls():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.jockey.in/", timeout=90000)
        await page.wait_for_timeout(15000)

        page_html = await page.content()
        soup = BeautifulSoup(page_html, "html.parser")

        l22_lists = soup.find_all('ul', {'role': 'list'})

        final_json = {}

        for ul in l22_lists:
            for a in ul.find_all("a", class_="mega-menu__link"):
                text = a.get_text(strip=True)
                url = a.get("href", "").strip()

                parent = a.get("data-parentdata") or ""
                if any(k in parent for k in POP_KEYS):
                    continue

                category = a.get("data-categorydata") or ""
                if any(k in category for k in POP_KEYS):
                    continue

                subcat = a.get("data-subcategorydata") or ""
                if any(k in subcat for k in POP_KEYS):
                    continue

                if url.startswith("/"):
                    url = "https://www.jockey.in" + url

                parent_name = parent.split(",")[0] if parent else ""
                category_name = category.split(",")[0] if category else ""
                subcat_name = subcat.split(",")[0] if subcat else text

                if parent_name not in final_json:
                    final_json[parent_name] = {}

                if category_name not in final_json[parent_name]:
                    final_json[parent_name][category_name] = {}

                final_json[parent_name][category_name][subcat_name] = url

        today = datetime.today().strftime("%Y-%m-%d")
        save_path = os.path.join("India", today, "Category")
        os.makedirs(save_path, exist_ok=True)

        country = "India"
        file_path = os.path.join(save_path, f"{country}_category_urls.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4, ensure_ascii=False)

        print(f"Saved JSON {file_path}")

        await browser.close()  

if __name__ == "__main__":
    asyncio.run(category_urls())
