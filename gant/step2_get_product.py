import json
import logging
from pathlib import Path
from datetime import date
from playwright.async_api import async_playwright
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ---------------- SAVE JSON ----------------
def save_json(today_str, gender, category, product, handle, country):
    try:
        output_path = Path(f'{country}/{today_str}/Json_data/{gender}/{category}')
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / f'{handle}.json', "w", encoding='utf-8') as outfile:
            json.dump(product, outfile, ensure_ascii=False, indent=4)
        # logging.info(f"{handle} saved to JSON file.")
    except Exception as e:
        logging.error(f"Error saving JSON file for {country}: {e}")


# ---------------- PROCESS PRODUCT LIST ----------------
def get_urls(today_str, gender, category, products, country):
    urls = []
    for product in products:
        handle = product["handle"]
        urls.append(f"https://gant.ae/products/{handle}")
        save_json(today_str, gender, category, product, handle, country)
    return urls


# ---------------- GET NEXT JSON PAGE ----------------
async def get_extra_json(category, page, page_obj):
    try:
        url = f'https://gant.ae/collections/{category}/products.json?limit=250&page={page}'
        await page_obj.goto(url, timeout=30000)  # 30 second timeout
        try:
            content = await page_obj.text_content("pre")
            json_data = json.loads(content)
            products = json_data.get("products", [])
            return products if products else None
        except (json.JSONDecodeError, AttributeError) as e:
            logging.warning(f"Failed to parse JSON for page {page}: {e}")
            return None
    except Exception as e:
        logging.error(f"Failed to load page {page} for category {category}: {e}")
        return None


# ---------------- GET FIRST JSON PAGE ----------------
async def get_json(today_str, gender, category, page_obj, country):
    try:
        url = f'https://gant.ae/collections/{category}/products.json?limit=250'
        await page_obj.goto(url, timeout=30000)  # 30 second timeout

        content = await page_obj.text_content("pre")
        json_data = json.loads(content)
        products = json_data.get("products", [])

        urls = []
        if products:
            urls += get_urls(today_str, gender, category, products, country)

            page_num = 2
            while len(products) == 250:
                products = await get_extra_json(category, page_num, page_obj)
                if not products:
                    break
                urls += get_urls(today_str, gender, category, products, country)
                page_num += 1

        return urls

    except Exception as e:
        logging.error(f"Error in category {category}: {e}")
        raise e  # Propagate error to trigger failure logging


# ---------------- RUN SCRAPER ----------------
async def run_scraper(CONFIG=None, TODAY_DATE=None, USER_AGENTS=None, COUNTRIES=None, COUNTRY_CODE_MAP=None, re_run=False):
    today_str = TODAY_DATE if TODAY_DATE else date.today().strftime('%Y-%m-%d')
    country = list(COUNTRIES.keys())[0] if COUNTRIES else "UAE"

    # --- Correct location for log file ---
    output_dir = Path(country) / today_str / "Item_urls"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{country}_product_urls.json"

    # User requested specific log file name
    log_file = output_dir / f"{country}_product_scrap_log.json"

    # Category path
    category_path = Path(country) / today_str / "Category" / f"{country}_category_urls.json"
    if not category_path.exists():
        logging.error(f"Category file not found: {category_path}")
        return

    with open(category_path, "r", encoding="utf-8") as f:
        category_data = json.load(f)

    # Load previous results if they exist, to avoid overwriting with partial data
    results = {}
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception as e:
            logging.warning(f"Could not load existing results: {e}")

    # Load previous log
    log_data = {}
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except Exception as e:
            logging.warning(f"Could not load existing log: {e}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for gender, categories in category_data.items():
            results.setdefault(gender, {})

            for category_name, url in categories.items():
                
                # Check if already scraped successfully (skip only if not re_run)
                if not re_run and url in log_data and log_data[url] == "success":
                    logging.info(f"Skipping already scraped category: {category_name} ({url})")
                    continue

                cat_key = url.split("/")[-1]
                logging.info(f"Scraping category: {gender}/{cat_key}")

                try:
                    urls = await get_json(today_str, gender, cat_key, page, country)
                    results[gender][cat_key] = urls

                    # -------- SAVE LOG AS SUCCESS --------
                    log_data[url] = "success"
                    with open(log_file, "w", encoding="utf-8") as f:
                        json.dump(log_data, f, indent=4)
                    
                    # Save intermediate results
                    with open(output_file, "w", encoding="utf-8") as outf:
                        json.dump(results, outf, indent=4)

                except Exception as e:
                    logging.error(f"Failed scraping {category_name}: {e}")
                    # -------- SAVE LOG AS FAIL --------
                    log_data[url] = "fail"
                    with open(log_file, "w", encoding="utf-8") as f:
                        json.dump(log_data, f, indent=4)

        await context.close()
        await browser.close()

    # Save final results (redundant but safe)
    with open(output_file, "w", encoding="utf-8") as outf:
        json.dump(results, outf, indent=4)

    logging.info(f"{country} product URLs saved successfully.")


# ---------------- MAIN CALL ----------------
async def main():
    await run_scraper()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
