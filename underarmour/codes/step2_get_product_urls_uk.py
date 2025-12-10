import logging
import json
import asyncio
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

base_url = 'https://www.underarmour.co.uk/'

countries = {
    "UK": "UK"
}

async def get_product_links(page, url):
    page_num = 1
    links = set()

    while True:
        paged_url = f"{url}?page={page_num}"
        logging.info(f"Fetching page: {paged_url}")

        await page.set_viewport_size({"width": 1329, "height": 654})
        await page.goto(paged_url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")

        await asyncio.sleep(2)

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        product_container = soup.find('div', class_='ProductBrowser_container__I1E0s')
        if not product_container:
            logging.warning(f"No product grid found on page {page_num}. Ending pagination.")
            break

        a_tags = product_container.find_all('a')

        new_links_found = False
        for a in a_tags:
            href = a.get("href")
            if href and ".html" in href and "color=" in href:
                full_url = urljoin(base_url, href)
                if full_url not in links:
                    links.add(full_url)
                    new_links_found = True

        if not new_links_found:
            logging.info(f"No new links found on page {page_num}. Ending pagination.")
            break

        logging.info(f"Collected {len(links)} unique links so far (page {page_num})")
        page_num += 1
        await asyncio.sleep(2)

    return list(links)


async def main():
    today = date.today().strftime('%Y-%m-%d')

    for country, _ in countries.items():
        input_file = Path(country).joinpath("Data", today, "Item_urls", f"Category_urls.json")
        if not input_file.is_file():
            logging.error(f"Input file not found: {input_file}")
            continue

        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)

        logging.info(f"Fetching {country} product URLs...")

        temp_urls = {}
        output_dir = Path(country).joinpath("Data", today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"product_urls.json"

        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=False)
            page = await browser.new_page()

            for gender, categories in url_dict.items():
                temp_urls.setdefault(gender, {})
                logging.info(f"Gender: {gender}")
                for category, url in categories.items():
                    logging.info(f"Category: {category}")
                    try:
                        links = await get_product_links(page, url)
                        temp_urls[gender][category] = links
                    except Exception as e:
                        logging.error(f"Error fetching links for {category}: {e}")
                        temp_urls[gender][category] = []

                    #  Save immediately after fetching each category
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(temp_urls, f, indent=2)
                    logging.info(f"Progress saved -> {output_path}")

            await browser.close()

        logging.info(f"All done! {country} product URLs saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
