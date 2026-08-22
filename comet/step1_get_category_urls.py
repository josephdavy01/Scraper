import os
import json
import asyncio
from datetime import date
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

countries = {'india': 'https://www.wearcomet.com/'}

async def main():
    today_str = date.today().strftime("%Y-%m-%d")
    country = "India"
    base_dir = f"{country}/Data/{today_str}/Item_urls"
    os.makedirs(base_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(countries['india'], wait_until="domcontentloaded", timeout=60000)
        soup = BeautifulSoup(await page.content(), "html.parser")
        base_url = countries['india']
        category_links = {"men": {}, "women": {}}

        for block in soup.find_all('div', class_='content-block'):
            tab_id = block.get('content-tab-id')
            gender = "men" if tab_id == "tab-1" else "women" if tab_id == "tab-2" else None
            if not gender:
                continue
            for a_tag in block.find_all('a', href=True):
                href = a_tag['href'].strip()
                if '/collections/' not in href:
                    continue
                full_url = urljoin(base_url, href)
                name = re.sub(r'\s+', ' ', a_tag.get_text(strip=True))
                if not name or full_url in category_links[gender].values():
                    continue
                if name.lower() in ['x lows', 'aeon', 'alter']:
                    name = name.upper()
                category_links[gender][name] = full_url

        json_path = os.path.join(base_dir, f"{country}_category_urls.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(category_links, f, indent=4, ensure_ascii=False)

        await browser.close()

        print(f"Saved to: {json_path}")

if __name__ == "__main__":
    asyncio.run(main())
