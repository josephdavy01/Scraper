import logging
import json
import asyncio
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError
import os

PARALLEL = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def _save_debug_screenshot(page, suffix="debug"):
    try:
        debug_dir = "debug_screens"
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, f"{suffix}.png")
        await page.screenshot(path=path, full_page=True)
        logging.info(f"Saved debug screenshot: {path}")
    except Exception as e:
        logging.warning(f"Failed to save debug screenshot: {e}")

async def select_region(page, region_code="UK", wait_timeout=30000):
    logging.info("Attempting to open region selector / select region.")
    try:
        btn = page.locator("a.selected-store-btn, .selected-store-btn, .as-selector-modal a")
        if await btn.count() > 0:
            try:
                await btn.first.click()
            except Exception:
                try:
                    await btn.first.evaluate("el => el.click()")
                except Exception as e:
                    logging.warning(f"Could not click selector button normally: {e}")
        else:
            logging.info("Region selector button not found by known locators, attempting other triggers.")
            text_btn = page.locator("text=Region, text=Country, text=Store")
            if await text_btn.count() > 0:
                try:
                    await text_btn.first.click()
                except Exception:
                    try:
                        await text_btn.first.evaluate("el => el.click()")
                    except Exception:
                        logging.warning("Unable to click fallback region text button.")
        try:
            await page.wait_for_selector("#regionSelectorModal, .as-modal-region-list-with-region, .store-list", timeout=wait_timeout)
        except Exception:
            logging.info("Region modal not detected quickly; will attempt direct anchor search on page.")
        region_link = page.locator('a[data-region-code="UK"], a[href*="uk.anta.com"], a[href*="//uk.anta.com"]')
        if await region_link.count() == 0:
            region_link = page.locator("a", has_text="United Kingdom")
            if await region_link.count() == 0:
                region_link = page.locator('a[href*="/uk"]')
        if await region_link.count() == 0:
            logging.error("Could not find any UK region anchor on the page.")
            await _save_debug_screenshot(page, "region_anchor_not_found")
            return False
        for attempt in range(1, 5):
            try:
                if attempt == 1:
                    logging.info("Attempt 1: normal click on region anchor.")
                    async with page.expect_navigation(timeout=10000):
                        await region_link.first.click()
                    logging.info("Navigation triggered by click.")
                    return True
                elif attempt == 2:
                    logging.info("Attempt 2: JS evaluate click on anchor.")
                    href = await region_link.first.get_attribute("href")
                    try:
                        async with page.expect_navigation(timeout=10000):
                            await region_link.first.evaluate("el => el.click()")
                        logging.info("Navigation triggered by JS click.")
                        return True
                    except Exception:
                        if href:
                            logging.info("JS click didn't navigate; setting window.location.href to anchor href.")
                            await page.evaluate(f"window.location.href = {json.dumps(href)}")
                            await page.wait_for_load_state("domcontentloaded", timeout=15000)
                            return True
                elif attempt == 3:
                    logging.info("Attempt 3: scroll into view then click.")
                    try:
                        await region_link.first.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        async with page.expect_navigation(timeout=10000):
                            await region_link.first.click()
                        return True
                    except Exception as e:
                        logging.warning(f"Attempt 3 click failed: {e}")
                else:
                    logging.info("Attempt 4: final fallback - read href and set window.location.")
                    href = await region_link.first.get_attribute("href")
                    if href:
                        await page.evaluate(f"window.location.href = {json.dumps(href)}")
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)
                        return True
                    else:
                        logging.error("Region anchor has no href to navigate to.")
            except Exception as e:
                logging.warning(f"Region selection attempt {attempt} failed: {e}")
                await asyncio.sleep(0.5)
        logging.error("All attempts to select region failed.")
        await _save_debug_screenshot(page, "region_select_failed")
        return False
    except Exception as e:
        logging.exception(f"select_region error: {e}")
        await _save_debug_screenshot(page, "region_exception")
        return False

async def close_anta_popup(page, wait_timeout=5000):
    close_button_selector = "div[data-form-name='ANTA Subscription'] button.modal-close.as-close"
    try:
        close_button = page.locator(close_button_selector)
        await close_button.wait_for(state="visible", timeout=wait_timeout)
        logging.info("ANTA subscription pop-up detected. Attempting to close it.")
        await close_button.click(force=True)
        logging.info("Successfully closed the ANTA pop-up.")
        await page.wait_for_selector(close_button_selector, state="hidden", timeout=5000)
    except TimeoutError:
         logging.info("ANTA subscription pop-up did not appear within the timeout.")
    except Exception as e:
        logging.warning(f"Error while trying to close pop-up: {e}")

async def get_product_urls_uk(page, url):
    base_url = "https://uk.anta.com"
    await page.goto(url, timeout=60000)
    await page.wait_for_load_state("domcontentloaded")
    await close_anta_popup(page) 
    await asyncio.sleep(2)
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    product_container = soup.find_all("div", class_="position-relative region-item")
    product_links = set()
    for container in product_container:
        for a in container.find_all("a"):
            if a.get("data-region-code") == "UK":
                href = a.get("href")
                if href:
                    product_links.add(urljoin(base_url, href))
    variant_urls = set()
    for product_url in product_links:
        try:
            await page.goto(product_url, timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await close_anta_popup(page) # Check for popup on product page
            await asyncio.sleep(2)
            product_html = await page.content()
            soup = BeautifulSoup(product_html, "html.parser")
            select_tag = soup.find("select", class_="as-product-variant")
            if not select_tag:
                continue
            seen = set()
            for opt in select_tag.find_all("option", class_="as-product-variant-option"):
                color = opt.get("data-option1")
                variant_id = opt.get("value")
                if color and variant_id and color not in seen:
                    seen.add(color)
                    variant_urls.add(f"{product_url}?variant={variant_id}")
        except Exception as e:
            logging.warning(f"[UK] Error at {product_url}: {e}")
            continue
    return list(variant_urls)

async def get_product_urls_usa(page, url):
    page_num = 1
    links = set()
    prev_page_links = set()
    base_url = "https://anta.com"
    while True:
        paged_url = f"{url}?page={page_num}"
        logging.info(f"[USA] Fetching page: {paged_url}")
        try:
            await page.set_viewport_size({"width": 1329, "height": 654})
            await page.goto(paged_url, timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await close_anta_popup(page) # Check for popup after category navigation
            await asyncio.sleep(2)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            product_container = soup.find_all("div", class_="position-relative product-card-img-wrap")
            if not product_container:
                logging.warning(f"[USA] No products found on page {page_num}. Stopping pagination.")
                break
            current_links = set()
            for container in product_container:
                a_tag = container.find("a", attrs={"data-as-stretched-link": True})
                if a_tag:
                    href = a_tag.get("href")
                    if href and href.startswith("/products/"):
                        current_links.add(urljoin(base_url, href))
            if current_links == prev_page_links:
                break
            links.update(current_links)
            prev_page_links = current_links
            logging.info(f"[USA] Collected {len(links)} links (page {page_num})")
            page_num += 1
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"[USA] Error fetching page {page_num}: {e}")
            break
    return list(links)

def persist_progress(output_path: Path, temp_urls: dict):
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(temp_urls, f, indent=2)
        logging.info(f"Progress saved to {output_path}")
    except Exception as e:
        logging.error(f"Failed to persist progress to {output_path}: {e}")

async def process_country_instance(p, country: str, url_dict: dict, today: str):
    logging.info(f"[{country}] Starting processing in its own browser.")
    browser = await p.chromium.launch(headless=False)
    page = await browser.new_page()
    try:
        if country.upper() == "UK":
            try:
                logging.info("[UK] Opening global page to select UK region...")
                await page.goto("https://anta.com", timeout=90000)
                await page.wait_for_load_state("domcontentloaded")
                await close_anta_popup(page)
                ok = await select_region(page, region_code="UK")
                if not ok:
                    logging.warning("[UK] Region selection failed; continuing but category pages might be region-locked.")
                else:
                    await asyncio.sleep(1.5)
                    logging.info(f"[UK] After region selection final URL: {page.url}")
            except Exception as e:
                logging.exception(f"[UK] Error during region selection: {e}")
        if country.upper() == "USA":
             await page.goto("https://anta.com", timeout=60000)
             await close_anta_popup(page)
        temp_urls = {}
        output_dir = Path(country, "Data", today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{country}_product_urls.json"
        for gender, categories in url_dict.items():
            temp_urls.setdefault(gender, {})
            logging.info(f"[{country}] Gender: {gender}")
            if isinstance(categories, dict):
                for category, url in categories.items():
                    logging.info(f"[{country}] Category: {category} -> {url}")
                    try:
                        if country.upper() == "UK":
                            full_url = url if url.startswith("http") else urljoin("https://uk.anta.com", url)
                            links = await get_product_urls_uk(page, full_url)
                        else:
                            full_url = url if url.startswith("http") else urljoin("https://anta.com", url)
                            links = await get_product_urls_usa(page, full_url)
                        temp_urls[gender][category] = links
                        logging.info(f"[{country}] Saved {len(links)} links for {gender}/{category}")
                    except Exception as e:
                        logging.error(f"[{country}] Error fetching {category}: {e}")
                        temp_urls[gender][category] = []
                    persist_progress(output_path, temp_urls)
            else:
                url = categories
                category = "default"
                logging.info(f"[{country}] Category: {category} -> {url}")
                try:
                    if country.upper() == "UK":
                        full_url = url if url.startswith("http") else urljoin("https://uk.anta.com", url)
                        links = await get_product_urls_uk(page, full_url)
                    else:
                        full_url = url if url.startswith("http") else urljoin("https://anta.com", url)
                        links = await get_product_urls_usa(page, full_url)
                    temp_urls[gender][category] = links
                    logging.info(f"[{country}] Saved {len(links)} links for {gender}/{category}")
                except Exception as e:
                    logging.error(f"[{country}] Error fetching {category}: {e}")
                    temp_urls[gender][category] = []
                persist_progress(output_path, temp_urls)
        logging.info(f"[{country}] Finished processing. Closing browser.")
    except Exception as e:
        logging.exception(f"[{country}] Unexpected error: {e}")
    finally:
        try:
            await browser.close()
        except Exception:
            logging.warning(f"[{country}] Error closing browser.")

async def main():
    today = date.today().strftime("%Y-%m-%d")
    inputs = {}
    for country in ["UK", "USA"]:
        input_file = Path(country, "Data", today, "Item_urls", f"{country}_category_urls.json")
        if not input_file.is_file():
            logging.error(f"[{country}] Input file not found: {input_file}")
            continue
        with open(input_file, "r", encoding="utf-8") as f:
            inputs[country] = json.load(f)
    if not inputs:
        logging.error("No input files found for any country. Exiting.")
        return
    async with async_playwright() as p:
        if PARALLEL:
            tasks = []
            for country, url_dict in inputs.items():
                tasks.append(process_country_instance(p, country, url_dict, today))
            await asyncio.gather(*tasks)
        else:
            if "UK" in inputs:
                logging.info("Sequential mode: Processing UK first.")
                await process_country_instance(p, "UK", inputs["UK"], today)
            if "USA" in inputs:
                logging.info("Sequential mode: Processing USA next.")
                await process_country_instance(p, "USA", inputs["USA"], today)
    logging.info("All done.")

if __name__ == "__main__":
    asyncio.run(main())