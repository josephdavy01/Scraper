import os
import json
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.async_api import async_playwright

# --- Helpers ---
def read_json_urls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def handle_cookies(page):
    try:
        button = await page.query_selector("button:has-text('Accept all cookies')")
        if button:
            await button.click()
            print("Cookies accepted")
    except:
        pass

# --- Ultra slow smooth scroll ---
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




# --- Scraper ---
async def scrape_usa_products(page, category_data, output_file):
    results = {}

    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                results = json.load(f)
            except:
                results = {}

    for main_category, subcategories in category_data.items():
        if main_category not in results:
            results[main_category] = {}

        for subcategory, url in subcategories.items():
            print(f"[USA] {main_category} -> {subcategory}")
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await handle_cookies(page)
            await page.wait_for_timeout(500)

            # use new JS-based scroll
            await auto_scroll(page)

            soup = BeautifulSoup(await page.content(), 'html.parser')
            links = []
            main_tag = soup.find('div', class_='row product-grid')
            if main_tag:
                product_divs = main_tag.find_all('div', class_='col-6 col-md-3 gridnumber')
                for product in product_divs:
                    tile_body = product.find('div', class_='tile-body plp-saveforlater plp-tile-layout')
                    if not tile_body:
                        continue
                    pdp_link_div = tile_body.find('div', class_='pdp-link')
                    if not pdp_link_div:
                        continue
                    a_tag = pdp_link_div.find('a', class_='link pagechoice', itemprop='url')
                    if a_tag:
                        link = a_tag.get('href')
                        if link.startswith('/'):
                            link = 'https://www.marksandspencer.com' + link
                        links.append(link)

            results[main_category][subcategory] = list(set(links))

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4)
            print(f"Saved {len(links)} links for {main_category} -> {subcategory}")

    return results

# --- Main ---
async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    file_path = f"USA/Data/{today}/Item_urls/USA_category_urls.json"
    output_file = os.path.join(os.path.dirname(file_path), "USA_product_urls.json")

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    category_data = read_json_urls(file_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
        viewport={"width": 1920, "height": 1080}  # Full HD resolution
         )
        page = await context.new_page()

        await scrape_usa_products(page, category_data, output_file)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
