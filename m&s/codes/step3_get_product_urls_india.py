import os
import json
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.async_api import async_playwright

def read_json_urls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def auto_scroll(page, step=200, delay=300, max_scrolls=300000):
    """
    Slowly scrolls the page to trigger lazy loading of products.

    step: how many pixels to scroll each time
    delay: time (ms) to wait after each scroll
    max_scrolls: safety cap to avoid infinite scrolling
    """
    print("Starting ultra-slow scroll...")
    await page.evaluate(f"""
        async () => {{
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let totalScrolled = 0;
            let scrollStep = {step};
            let maxScrolls = {max_scrolls};
            let scrollCount = 0;

            while (scrollCount < maxScrolls) {{
                window.scrollBy(0, scrollStep);
                totalScrolled += scrollStep;
                scrollCount++;
                await delay({delay});
                
                // stop if reached bottom
                if ((window.innerHeight + window.scrollY) >= document.body.scrollHeight) {{
                    break;
                }}
            }}
        }}
    """)
    print("Finished scrolling!")

async def scrape_india_products(page, category_data):
    results = {}
    for main_category, subcategories in category_data.items():
        results[main_category] = {}
        for subcategory, url in subcategories.items():
            print(f"[India] {main_category} -> {subcategory}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)
            await auto_scroll(page)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            links = []
            main_tags = soup.find('div', {'class': 'product-grid'})
            if main_tags:
                for tag in main_tags.find_all('a', {'class': 'pagechoice'}):
                    link = tag.get('href')
                    if link.startswith('/'):
                        link = 'https://www.marksandspencer.in' + link
                    links.append(link)
            results[main_category][subcategory] = list(set(links))
    return results

async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    file_path = f"India/Data/{today}/Item_urls/India_category_urls.json"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    category_data = read_json_urls(file_path)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        results = await scrape_india_products(page, category_data)

        output_file = os.path.join(os.path.dirname(file_path), "India_product_urls.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"Saved India product URLs to: {output_file}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
