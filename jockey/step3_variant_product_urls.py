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

# ------------------ CONCURRENCY LIMIT ------------------
SEMAPHORE = asyncio.Semaphore(3)
# -------------------------------------------------------


async def get_product_links(page, url):
    """Extract ALL product URLs that contain /products/ from any part of the HTML."""
    await page.goto(url, timeout=60000, wait_until="domcontentloaded")

    try:
        await page.wait_for_selector("div.variantCard", timeout=15000)
    except:
        logging.warning("variantCard not found, continuing...")

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    product_links = []
    div_elements = soup.find_all("div", {"class": "variantCard", "data-gtm-product-info": True})

    for div in div_elements:
        for anchor in div.find_all("a"):
            href = anchor.get("href")
            if not href:
                continue

            if href.startswith("/"):
                href = "https://www.jockey.in" + href

            product_links.append(href)

    return product_links


async def process_single_url(browser, url, idx, total, output_path, result_dict, current_path, progress_path=None):
    async with SEMAPHORE:
        if not isinstance(url, str) or not url.startswith("http"):
            return []

        logging.info(f"  [{idx}/{total}] Processing: {url}")

        page = await browser.new_page()
        try:
            variants = await get_product_links(page, url)

            if variants:
                # ---------- IMMEDIATE SAVE BLOCK (DUPLICATE SAFE) ----------
                target = result_dict
                for key in current_path[:-1]:
                    target = target.setdefault(key, {})

                target.setdefault(current_path[-1], [])
                target[current_path[-1]] = list(set(target[current_path[-1]] + variants))

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result_dict, f, indent=2)

                logging.info(f"    Saved {len(variants)} URLs immediately")
                
                # Log progress
                if progress_path:
                    category_path = "|".join(current_path).lower().replace(" ", "_")
                    with open(progress_path, "a", encoding="utf-8") as pf:
                        pf.write(f"{category_path}\n")

            return variants

        except Exception as e:
            logging.error(f"    Error: {e}")
            return []

        finally:
            await page.close()


async def process_urls(browser, urls, output_path, result_dict, current_path, progress_path=None):
    """Process URLs using asyncio.gather with limit 5"""
    tasks = []

    for idx, url in enumerate(urls, 1):
        task = process_single_url(
            browser, url, idx, len(urls),
            output_path, result_dict, current_path, progress_path
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    all_variants = [item for sublist in results for item in sublist]

    return all_variants


async def process_category(browser, data, output_path, result_dict, current_path=[], progress_path=None):
    """Recursively process nested category structure."""
    if isinstance(data, list):
        logging.info(f"Processing {len(data)} URLs for: {' > '.join(current_path)}")
        return await process_urls(browser, data, output_path, result_dict, current_path, progress_path)

    elif isinstance(data, dict):
        for key, value in data.items():
            await process_category(browser, value, output_path, result_dict, current_path + [key], progress_path)

    return None


async def variant_product_urls():
    today = date.today().strftime("%Y-%m-%d")

    for country, base_url in countries.items():
        input_file = Path(country).joinpath(today, "Item_urls", f"{country}_product_urls.json")
        if not input_file.is_file():
            logging.error(f"Input file not found: {input_file}")
            continue

        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)

        logging.info(f"Fetching {country} product URLs...")

        output_dir = Path(country).joinpath(today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{country}_variant_product_urls.json"
        progress_path = output_dir / f"{country}_variant_progress.log"
        
        # Initialize progress file
        with open(progress_path, "w", encoding="utf-8") as pf:
            pf.write("")  # Start with empty file

        result_dict = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            for gender, categories in url_dict.items():
                logging.info(f"Gender: {gender}")
                result_dict.setdefault(gender, {})
                await process_category(browser, categories, output_path, result_dict, [gender], str(progress_path))

            await browser.close()

        logging.info(f"All done! {country} variant product URLs saved to {output_path}")
        logging.info(f"Progress log saved to: {progress_path}")


if __name__ == "__main__":
    asyncio.run(variant_product_urls())
