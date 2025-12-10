# import logging
# import json
# import asyncio
# from datetime import date
# from pathlib import Path
# from bs4 import BeautifulSoup
# from playwright.async_api import async_playwright

# # Configure logging
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# countries = {
#     "india": "india"
# }


# async def auto_scroll(page):
#     """Scroll down gradually to load all dynamic content"""
#     await page.evaluate("""
#         async () => {
#             const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
#             let lastHeight = document.body.scrollHeight;
#             let noChangeCount = 0;
#             const maxAttempts = 20;  // Increased for lazy loading

#             while (noChangeCount < maxAttempts) {
#                 window.scrollTo(0, document.body.scrollHeight);
#                 await delay(800);
#                 let newHeight = document.body.scrollHeight;
#                 if (newHeight === lastHeight) {
#                     noChangeCount++;
#                 } else {
#                     noChangeCount = 0;
#                     lastHeight = newHeight;
#                 }
#             }
#         }
#     """)


# async def get_product_tiles(page, url):
#     """Fetch page and extract all data-product-tile values"""
#     await page.set_viewport_size({"width": 1521, "height": 730})

#     try:
#         await page.goto(url, timeout=90000, wait_until="domcontentloaded")
#     except Exception as e:
#         logging.error(f"Failed to load {url}: {e}")
#         return []

#     await asyncio.sleep(3)

#     # Scroll multiple times to ensure lazy-loaded products appear
#     for _ in range(3):
#         await auto_scroll(page)
#         await asyncio.sleep(1.5)

#     html_content = await page.content()
#     soup = BeautifulSoup(html_content, "html.parser")

#     product_tiles = []

#     # Target the main product grid container
#     container = soup.find("div", class_="w-full relative md:pl-[23px] md:pr-[22px] md:mt-4 pb-[32px] md:pb-0")
#     if not container:

#         container = soup.find("div", {"data-product-grid": True})
#     if not container:
#         logging.warning(f"Product container not found for {url}")
#         return []

#     # Find all divs with data-product-tile attribute
#     tiles = container.find_all('div', attrs={'data-product-tile': True})
#     base_url = "https://tenxyou.com/product-details/"

#     for tile in tiles:
#         tile_id = tile.get('data-product-tile')
#         if tile_id:
#             full_url = base_url + tile_id
#             product_tiles.append(full_url)

#     logging.info(f"Extracted {len(product_tiles)} product tiles from {url}")
#     return product_tiles


# async def main():
#     today = date.today().strftime("%Y-%m-%d")

#     for country, base_url in countries.items():
#         input_file = Path(country).joinpath("Data", today, "Item_urls", f"{country}_category_urls.json")
#         if not input_file.is_file():
#             logging.error(f"Input file not found: {input_file}")
#             continue

#         with open(input_file, "r", encoding="utf-8") as f:
#             url_dict = json.load(f)

#         logging.info(f"Scraping {country} product tiles...")

#         output_dir = Path(country).joinpath("Data", today, "Item_urls")
#         output_dir.mkdir(parents=True, exist_ok=True)
#         output_path = output_dir / f"{country}_product_urls.json"

#         # Load existing data or start fresh
#         if output_path.exists():
#             with open(output_path, "r", encoding="utf-8") as f:
#                 temp_data = json.load(f)
#         else:
#             temp_data = {}

#         async with async_playwright() as p:
#             try:
#                 browser = await p.chromium.launch(channel="chrome", headless=False)
#             except Exception:
#                 browser = await p.chromium.launch(headless=False)

#             page = await browser.new_page()

#             for gender, categories in url_dict.items():
#                 temp_data.setdefault(gender, {})
#                 logging.info(f"Processing Gender: {gender}")

#                 for category, url in categories.items():
#                     if category in temp_data.get(gender, {}) and temp_data[gender][category]:
#                         logging.info(f"  Skipping {category}, already scraped.")
#                         continue

#                     logging.info(f"  Scraping Category: {category}")
#                     try:
#                         tiles = await get_product_tiles(page, url)
#                         temp_data[gender][category] = tiles
#                         logging.info(f"  Found {len(tiles)} product tiles")

#                     except Exception as e:
#                         logging.error(f"Error scraping {category}: {e}")
#                         temp_data[gender][category] = []

#                     # Save after each category safely
#                     with open(output_path, "w", encoding="utf-8") as f:
#                         json.dump(temp_data, f, indent=2, ensure_ascii=False)

#             await browser.close()

#         logging.info(f"{country.upper()} scraping complete! Saved to {output_path}")


# if __name__ == "__main__":
#     asyncio.run(main())
import logging
import json
import asyncio
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

countries = {
    "india": "india"
}


async def auto_scroll(page):
    """Scroll down gradually to load all dynamic content"""
    await page.evaluate("""
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            let lastHeight = document.body.scrollHeight;
            let noChangeCount = 0;
            const maxAttempts = 20;

            while (noChangeCount < maxAttempts) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(800);
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


async def get_product_tiles(page, url):
    """Fetch page and extract all data-product-tile values"""
    await page.set_viewport_size({"width": 1521, "height": 730})

    try:
        await page.goto(url, timeout=90000, wait_until="domcontentloaded")
    except Exception as e:
        logging.error(f"Failed to load {url}: {e}")
        return []

    await asyncio.sleep(3)

    # Scroll multiple times to ensure lazy-loaded products appear
    for _ in range(3):
        await auto_scroll(page)
        await asyncio.sleep(1.5)

    html_content = await page.content()
    soup = BeautifulSoup(html_content, "html.parser")

    product_tiles = []

    # Target the main product grid container with fallbacks
    container = soup.find(
        "div",
        class_="w-full relative md:pl-[23px] md:pr-[22px] md:mt-4 pb-[32px] md:pb-0"
    )

    if not container:
        container = soup.find(
            "div",
            class_="w-full relative md:pl-[23px] md:pr-[22px] md:mt-4"
        )

    if not container:
        container = soup.find("div", {"data-product-grid": True})

    if not container:
        logging.warning(f"Product container not found for {url}")
        return []

    # Find all divs with data-product-tile attribute
    tiles = container.find_all('div', attrs={'data-product-tile': True})
    base_url = "https://tenxyou.com/product-details/"

    for tile in tiles:
        tile_id = tile.get('data-product-tile')
        if tile_id:
            full_url = base_url + tile_id
            product_tiles.append(full_url)

    logging.info(f"Extracted {len(product_tiles)} product tiles from {url}")
    return product_tiles


async def main():
    today = date.today().strftime("%Y-%m-%d")

    for country, base_url in countries.items():
        input_file = Path(country).joinpath("Data", today, "Item_urls", f"Category_urls.json")
        if not input_file.is_file():
            logging.error(f"Input file not found: {input_file}")
            continue

        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)

        logging.info(f"Scraping {country} product tiles...")

        output_dir = Path(country).joinpath("Data", today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{country}_product_urls.json"

        # Load existing data or start fresh
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                temp_data = json.load(f)
        else:
            temp_data = {}

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=False)
            except Exception:
                browser = await p.chromium.launch(headless=False)

            page = await browser.new_page()

            for gender, categories in url_dict.items():
                temp_data.setdefault(gender, {})
                logging.info(f"Processing Gender: {gender}")

                for category, url in categories.items():
                    if category in temp_data.get(gender, {}) and temp_data[gender][category]:
                        logging.info(f"  Skipping {category}, already scraped.")
                        continue

                    logging.info(f"  Scraping Category: {category}")
                    try:
                        tiles = await get_product_tiles(page, url)
                        temp_data[gender][category] = tiles
                        logging.info(f"  Found {len(tiles)} product tiles")

                    except Exception as e:
                        logging.error(f"Error scraping {category}: {e}")
                        temp_data[gender][category] = []

                    # Save after each category safely
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(temp_data, f, indent=2, ensure_ascii=False)

            await browser.close()

        logging.info(f"{country.upper()} scraping complete! Saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
