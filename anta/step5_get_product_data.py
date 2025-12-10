import os
import re
import json
import logging
import asyncio
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError # Import TimeoutError

# ---------------- LOGGING ---------------- #
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------- ALERT (safe import) ---------------- #
try:
    from alert import raise_ticket
except Exception:
    def raise_ticket(component, step, message, country=None):
        logging.error(f"ALERT [{component}::{step}] country={country} - {message}")

# ---------------- SAFE FILE OPERATIONS ---------------- #
def sanitize_filename(name: str) -> str:
    """Sanitize filenames for Windows (remove invalid chars)."""
    return re.sub(r'[<>:"/\\|?*]', "_", name.strip())

def save_json(gender, category, name, json_data, date_subfolder):
    """Safely save JSON data to a structured folder."""
    try:
        safe_gender = sanitize_filename(gender)
        safe_category = sanitize_filename(category)
        safe_name = sanitize_filename(name)

        json_path = date_subfolder / "Json_data" / safe_gender / safe_category
        json_path.mkdir(parents=True, exist_ok=True)

        json_file = json_path / f"{safe_name}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

        logging.info(f" Saved JSON: {json_file}")
    except Exception as e:
        logging.error(f" Error saving JSON file for {name}: {e}")
        raise_ticket("Step4", "save_json", f"Error saving JSON for {name}: {e}", None)

def check_file(gender, category, name, date_subfolder):
    safe_gender = sanitize_filename(gender)
    safe_category = sanitize_filename(category)
    safe_name = sanitize_filename(name)
    return (date_subfolder / "Json_data" / safe_gender / safe_category / f"{safe_name}.json").exists()

# ---------------- UK REGION SELECTOR ---------------- #

async def close_anta_popup(page, wait_timeout=5000):
    """
    Looks for the ANTA subscription pop-up and closes it if it appears.
    This is often required before interacting with other page elements.
    """
    close_button_selector = "div[data-form-name='ANTA Subscription'] button.modal-close.as-close"
    try:
        close_button = page.locator(close_button_selector)
        await close_button.wait_for(state="visible", timeout=wait_timeout)
        logging.info("ANTA subscription pop-up detected. Closing it.")
        await close_button.click(force=True)
        await page.wait_for_selector(close_button_selector, state="hidden", timeout=5000)
    except TimeoutError:
         logging.info("ANTA subscription pop-up did not appear within the timeout.")
    except Exception as e:
        logging.warning(f"Error while trying to close pop-up: {e}")


async def select_anta_region(page, region_code="UK", wait_timeout=30000):
    """
    Navigates to the main page (US), closes popups, scrolls down, and selects the specified region (UK).
    Returns True on successful navigation/selection.
    """
    logging.info(f"Attempting to open region selector / select region: {region_code}.")
    
    try:
        # 1. Open US page and wait for full load
        await page.goto("https://anta.com", timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3) # Wait for page scripts to execute

        # 2. Close any initial popups
        await close_anta_popup(page)
        
        # 3. Scroll to the bottom to reveal potential selector elements
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1) 

        # 4. Try clicking the typical region selector buttons
        btn = page.locator("a.selected-store-btn, .selected-store-btn, .as-selector-modal a")
        if await btn.count() > 0:
            try:
                await btn.first.click()
            except Exception as e:
                logging.warning(f"Could not click selector button normally: {e}. Trying fallback.")
        else:
            # 5. Fallback: text-based triggers
            text_btn = page.locator("text=Region, text=Country, text=Store")
            if await text_btn.count() > 0:
                try:
                    await text_btn.first.click()
                except Exception:
                    logging.warning("Unable to click fallback region text button.")
        
        await asyncio.sleep(1) # Wait for the modal/list to appear
        
        # 6. Locate and click the link to the target region
        # Search for link based on data-region-code or href
        region_selector = f'a[data-region-code="{region_code}"], a[href*="{region_code.lower()}.anta.com"]'
        region_link = page.locator(region_selector)
        
        # Last fallback: visible text "United Kingdom"
        if await region_link.count() == 0 and region_code == "UK":
            region_link = page.locator("a", has_text="United Kingdom")

        if await region_link.count() == 0:
            logging.error(f"Could not find any {region_code} region anchor on the page.")
            return False

        # Attempt navigation via click
        async with page.expect_navigation(timeout=15000):
            # Ensure the element is visible before clicking
            await region_link.first.scroll_into_view_if_needed()
            await region_link.first.click(force=True)
            
        await page.wait_for_load_state("domcontentloaded")
        logging.info(f"Navigation to {region_code} successful. Final URL: {page.url}")
        return True

    except Exception as e:
        logging.exception(f"select_anta_region error for {region_code}: {e}")
        return False


# ---------------- PRODUCT SCRAPER ---------------- #
async def process_urls(page, gender, category, urls, date_subfolder, country):
    for url in urls:
        name = url.split("/")[-1].split("?")[0]
        if check_file(gender, category, name, date_subfolder):
            logging.info(f"[{country}] Skipping existing file for {name}")
            continue

        try:
            await page.goto(url, timeout=60000) # Increased timeout for page load
            await page.wait_for_load_state("domcontentloaded")
            
            # --- POP-UP CLOSING ON PRODUCT PAGE ---
            await close_anta_popup(page) 
            # --------------------------------------
            
            # --- ADD DELAY FOR FULL PAGE RENDERING ---
            await asyncio.sleep(3) 
            # -----------------------------------------
            
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            product_data = {"url": url}

            # ---------------- VARIANT DATA ---------------- #
            script_tag = soup.find("script", {"class": "as-variants-data", "type": "application/json"})
            if script_tag and script_tag.string:
                try:
                    json_data = json.loads(script_tag.string.strip())
                    product_data["variants_data"] = json_data
                except Exception as e:
                    logging.warning(f"[{country}] Invalid JSON in variants for {url}: {e}")
                    # still continue; variants may be malformed

            # ---------------- IMAGE EXTRACTION ---------------- #
            image_urls = []
            wrappers = soup.find_all("div", class_="swiper-wrapper")
            wrapper = None

            # pick the wrapper that actually has product images
            for w in wrappers:
                if w.find("img", srcset=True) or w.find("img", src=True):
                    wrapper = w
                    break

            if wrapper:
                slides = wrapper.find_all("div", attrs={"data-swiper-slide-index": True})
                for slide in slides:
                    img_tag = slide.find("img")
                    if not img_tag:
                        continue

                    srcset = img_tag.get("srcset")
                    img_url = None

                    if srcset:
                        candidates = [p.strip() for p in srcset.split(",") if p.strip()]
                        # pick a good resolution candidate if present
                        for part in candidates:
                            if "1440w" in part:
                                img_url = part.split()[0].strip()
                                break
                        if not img_url and candidates:
                            img_url = candidates[-1].split()[0].strip()
                    else:
                        img_url = img_tag.get("src") or img_tag.get("data-src")

                    if img_url:
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url
                        if img_url not in image_urls:
                            image_urls.append(img_url)

            product_data["image_urls"] = image_urls

            #  SAVE JSON (only if at least variants or images present)
            if product_data.get("variants_data") or product_data.get("image_urls"):
                save_json(gender, category, name, product_data, date_subfolder)
            else:
                logging.warning(f"[{country}] No variant or image data found for {url}")
                # optionally save minimal JSON or raise alert
                # raise_ticket("Step4", "no_variant_image", f"No variant/image for {url}", country)

        except Exception as e:
            logging.error(f"[{country}] Error processing {url}: {e}")
            raise_ticket("Step4", "process_urls", f"Error processing {url}: {e}", country)
            continue

# ---------------- CATEGORY PROCESSOR ---------------- #
async def process_gender_section(page, gender, categories, date_subfolder, country):
    for category, urls in categories.items():
        try:
            logging.info(f"[{country}] Processing {gender} - {category} ({len(urls)} URLs)")
            await process_urls(page, gender, category, urls, date_subfolder, country)
        except Exception as e:
            logging.exception(f"[{country}] Error in process_gender_section for {gender}/{category}: {e}")
            raise_ticket("Step4", "process_gender_section", f"{gender}/{category}: {e}", country)

# ---------------- LIMITED PARALLEL TASK ---------------- #
async def limited_process_gender_section(p, gender, categories, date_subfolder, semaphore, country, max_retries=3):
    """
    Launches a browser, performs UK region selection if necessary, processes one gender section,
    then closes the browser.
    """
    async with semaphore:
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            browser = None
            page = None
            
            logging.info(f"[{country}] Launching browser for {gender} (Attempt {attempt}/{max_retries})")
            
            try:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()

                # --- UK REGION SELECTION (Conditional) ---
                if country.upper() == "UK":
                    logging.info("[UK] Navigating to anta.com to select UK region.")
                    region_selected = await select_anta_region(page, region_code="UK")
                    
                    if not region_selected:
                        if attempt < max_retries:
                            logging.warning(f"[UK] Region selection failed on attempt {attempt}. Retrying...")
                            await browser.close()
                            await asyncio.sleep(2) # Wait before retry
                            continue # Skip to next attempt
                        else:
                            logging.error("[UK] Region selection failed after all retries. Skipping task.")
                            raise Exception("Failed to set UK region after multiple retries.")
                    
                    await asyncio.sleep(1) # Short pause after successful region change
                
                # NOTE: For USA, this section is skipped, and it proceeds directly to scraping.
                # --------------------------------------------------

                # If region selection was successful (or not required for USA), proceed to scrape
                await process_gender_section(page, gender, categories, date_subfolder, country)
                return # Success!

            except Exception as e:
                logging.exception(f"[{country}] Exception while processing {gender} on attempt {attempt}: {e}")
                
                # Check if this was a fatal error (not related to region selection logic's internal retry)
                if country.upper() == "UK" and "Failed to set UK region" in str(e):
                    raise # Re-raise the final failure exception

                if attempt == max_retries:
                    raise_ticket("Step4", "limited_process_gender_section", f"{gender}: Max retries reached with error: {e}", country)
                    raise # Re-raise if all retries failed
                
                logging.warning(f"[{country}] Retrying process after error...")
                await asyncio.sleep(2) # Wait before retry

            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        logging.warning(f"[{country}] Error closing browser for {gender}")
                    logging.info(f"[{country}] Closed browser for {gender}")

# ---------------- COUNTRY HANDLER ---------------- #
async def handle_country(country, semaphore, TODAY_DATE):
    """
    Public async entrypoint to process a single country.
    """
    try:
        date_subfolder = Path(country) / "Data" / TODAY_DATE
        date_subfolder.mkdir(parents=True, exist_ok=True)

        item_urls_folder = date_subfolder / "Item_urls"
        item_urls_folder.mkdir(parents=True, exist_ok=True)

        file_path = item_urls_folder / f"{country}_unique_product_urls.json"
        if not file_path.exists():
            msg = f"URL file not found: {file_path}"
            logging.error(f"[{country}] {msg}")
            raise_ticket("Step4", "missing_unique_urls", msg, country)
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                urls_dict = json.load(f)
        except Exception as e:
            msg = f"Failed to read unique product URLs file {file_path}: {e}"
            logging.exception(f"[{country}] {msg}")
            raise_ticket("Step4", "read_unique_urls", msg, country)
            return

        async with async_playwright() as p:
            tasks = [
                limited_process_gender_section(p, gender, categories, date_subfolder, semaphore, country)
                for gender, categories in urls_dict.items()
            ]
            if not tasks:
                logging.info(f"[{country}] No gender sections found in {file_path}")
                return

            # gather and allow errors to be returned for logging
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, res in enumerate(results):
                if isinstance(res, Exception):
                    logging.error(f"[{country}] Task {idx} raised: {res}")
                    raise_ticket("Step4", "gender_task_exception", f"Task {idx} exception: {res}", country)

        logging.info(f"[{country}] scraping complete!")

    except Exception as e:
        logging.exception(f"[{country}] Unhandled exception in handle_country: {e}")
        raise_ticket("Step4", "handle_country", f"Unhandled exception: {e}", country)
        return

# ---------------- EXAMPLE RUNNER ---------------- #
if __name__ == "__main__":
    TODAY_STR = date.today().strftime("%Y-%m-%d")
    # control concurrency: Set to 2 parallel browsers maximum per country (Requirement)
    sem = asyncio.Semaphore(2) 
    countries = ["UK", "USA"]  # list the countries you want to process
    async def _run_all():
        await asyncio.gather(*(handle_country(c, sem, TODAY_STR) for c in countries))
    asyncio.run(_run_all())