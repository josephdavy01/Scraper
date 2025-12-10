import logging
import json
import asyncio
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

countries = {
    "india": "india"
}

async def auto_scroll(page):
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 10;

            while (noChangeCount < maxAttempts) {
                window.scrollBy(0, 200);
                await delay(150);
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

async def get_product_links(page, url):
    """Extract ALL product URLs that contain /products/ from any part of the HTML."""
    await page.set_viewport_size({"width": 1329, "height": 654})
    await page.goto(url, timeout=60000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(2)

    await auto_scroll(page)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    links = []

    # NEW LOGIC: Find any <a> tag with /products/ in href
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" in href:
            full_url = urljoin(url, href)
            if full_url not in links:
                links.append(full_url)

    logging.info(f" → Extracted {len(links)} product links")
    return links


async def main():
    today = date.today().strftime("%Y-%m-%d")

    for country, base_url in countries.items():
        input_file = Path(country).joinpath("Data", today, "Item_urls", f"{country}_category_urls.json")
        if not input_file.is_file():
            logging.error(f"Input file not found: {input_file}")
            continue

        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)

        logging.info(f"Fetching {country} product URLs...")

        output_dir = Path(country).joinpath("Data", today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{country}_product_urls.json"

        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                temp_urls = json.load(f)
        else:
            temp_urls = {}

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=False)
            except Exception:
                browser = await p.chromium.launch(headless=False)

            page = await browser.new_page()

            for gender, categories in url_dict.items():
                temp_urls.setdefault(gender, {})
                logging.info(f"Gender: {gender}")

                for category, url in categories.items():
                    if category in temp_urls.get(gender, {}) and temp_urls[gender][category]:
                        logging.info(f"  Skipping {category}, already scraped.")
                        continue

                    logging.info(f"Category: {category}")
                    try:
                        links = await get_product_links(page, url)
                        temp_urls[gender][category] = links
                        logging.info(f"   Found {len(links)} links")
                    except Exception as e:
                        logging.error(f"Error fetching links for {category}: {e}")
                        temp_urls[gender][category] = []

                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(temp_urls, f, indent=2)

            await browser.close()

        logging.info(f"All done! {country} product URLs saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
