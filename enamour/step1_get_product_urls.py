import json
import asyncio
import logging
from pathlib import Path
from datetime import date, datetime   
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# --- Configure logging to both file and console ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

# --- Define fixed categories ---
categories = {
    'Bra': 'https://www.enamor.co.in/collections/bras',
    'Panties': 'https://www.enamor.co.in/collections/panties',
    'spring-summer': 'https://www.enamor.co.in/collections/spring-summer-25',
    'all-athleisure': 'https://www.enamor.co.in/collections/all-athleisure',
    'essentials-and-more': 'https://www.enamor.co.in/collections/essentials-and-more',
    'enamor-xo': 'https://www.enamor.co.in/pages/enamor-xo'
}

# --- Slower full-page scroll using JS ---
async def auto_scroll(page):
    logging.info("Starting slow scroll...")
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 15;

            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 200);
                await delay(500);
                let newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) {
                    noChangeCount++;
                } else {
                    noChangeCount = 0;
                    lastHeight = newHeight;
                }
            }
        }
    """)
    logging.info("Finished scrolling.")

# --- Scroll and extract product links ---
async def scroll_and_get_urls(page, url):
    await page.set_viewport_size({"width": 1585, "height": 865})
    await page.goto(url, wait_until="load", timeout=100000)
    logging.info(f"Opened URL: {url}")

    try:
        await page.wait_for_selector('#ProductGridContainer', timeout=100000)
    except Exception:
        logging.warning("Product grid not found. Skipping.")
        return []

    await auto_scroll(page)

    await page.wait_for_function("""
        () => {
            const links = document.querySelectorAll('.grid__item a[href]');
            return links.length > 0 && Array.from(links).every(link => link.offsetParent !== null);
        }
    """, timeout=10000)

    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")

    linklist = set()
    grid_tag = soup.find('div', class_='product-grid-container', id='ProductGridContainer')
    if not grid_tag:
        logging.warning("Grid not found after scroll.")
        return []

    product_tags = grid_tag.find_all('li', class_='grid__item')
    for tag in product_tags:
        link = tag.find('a')
        if link and link.get('href'):
            full_url = f"https://www.enamor.co.in{link['href'].split('?')[0]}"
            linklist.add(full_url)

    logging.info(f"Collected {len(linklist)} product URLs for {url}.")
    return list(linklist)

# --- Main scraping logic ---
async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    today_day = datetime.today().strftime('%A')  
    country = "India"
    women_data = {}

    # Run only on Mon, Wed, Fri
    if today_day not in ['Monday','Tuesday', 'Wednesday', 'Friday']:
        logging.info(f"Today is {today_day}. Script will not run.")
        return

    # Prepare output folder & file once
    output_dir = Path(country) / "Data" / today_str / "Item_urls"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{country}_product_urls.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # change to True for background runs
        context = await browser.new_context()
        page = await context.new_page()

        for category_name, url in categories.items():
            logging.info(f"Scraping category: {category_name}")
            links = await scroll_and_get_urls(page, url)
            women_data[category_name] = links
            logging.info(f"Completed scraping {category_name} with {len(links)} links")

            #  Save immediately after scraping each category
            output_data = {"Women": women_data}
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)

            logging.info(f"Saved product links after {category_name} → {output_file}")

        await browser.close()

# --- Entry point ---
if __name__ == "__main__":
    asyncio.run(main())
