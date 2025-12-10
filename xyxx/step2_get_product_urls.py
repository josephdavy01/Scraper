import asyncio
import json
import logging
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
from datetime import datetime

# ---------------- LOGGING ---------------- #
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- CONFIG ---------------- #
HEADLESS = False
SCROLL_PAUSE = 0.5        
STABLE_ROUNDS = 3
NAV_TIMEOUT_MS = 30000
MAX_IDLE_SECONDS = 100
MIN_STEP_PX = 120
STEP_VIEWPORT_FRACTION = 0.20


# ---------------- SCROLL HANDLER ---------------- #
async def scroll_until_done(page, list_container_selector: str):
    last_height = None
    stable_rounds = 0
    start_time = time.time()

    # ✅ WAIT FOR INITIAL PAGE & PRODUCTS
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
        await page.wait_for_selector(list_container_selector, timeout=10000)
        await page.wait_for_timeout(1500)
    except Exception:
        logger.warning("Initial product grid not detected")

    async def try_click_load_more():
        selectors = [
            "button:has-text('Load more')",
            "button:has-text('Load More')",
            "button[class*='load-more']",
            ".load-more",
            ".btn-load-more",
            "a:has-text('Load more')"
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    logger.info("Clicking Load More: %s", sel)
                    await el.scroll_into_view_if_needed()
                    await page.wait_for_timeout(600)
                    await el.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(1200)
                    return True
            except Exception:
                continue
        return False

    await page.wait_for_timeout(2000)

    while True:
        try:
            height = await page.evaluate(
                "() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
            )
            viewport = await page.evaluate("() => window.innerHeight")
            scroll_y = await page.evaluate("() => window.scrollY || window.pageYOffset")
        except Exception:
            height = last_height if last_height else 0
            viewport = 800
            scroll_y = 0

        if last_height is None or height != last_height:
            stable_rounds = 0
            last_height = height
        else:
            stable_rounds += 1

        step = max(MIN_STEP_PX, int(viewport * STEP_VIEWPORT_FRACTION))
        next_y = scroll_y + step
        if next_y + viewport > height:
            next_y = max(0, height - viewport)

        try:
            await page.evaluate("(y) => window.scrollTo(0, y)", next_y)
        except Exception:
            await page.evaluate("(y) => window.scrollBy(0, y)", step)

        await page.wait_for_timeout(int(SCROLL_PAUSE * 1000))

        try:
            clicked = await try_click_load_more()
            if clicked:
                last_height = None
                stable_rounds = 0
                continue
        except Exception:
            pass

        try:
            at_bottom = await page.evaluate(
                "() => (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 5)"
            )
        except Exception:
            at_bottom = False

        if at_bottom and stable_rounds >= STABLE_ROUNDS:
            logger.info("Reached bottom and height stable.")
            break

        if time.time() - start_time > MAX_IDLE_SECONDS:
            logger.warning("MAX_IDLE_SECONDS reached, stopping scroll.")
            break

    await page.wait_for_timeout(1500)
    return await page.content()


# ---------------- PRODUCT URL EXTRACTOR ---------------- #
def extract_product_urls_from_html(html: str, base: Optional[str]) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    lis = soup.find_all("li", class_=lambda c: c and "wizzy-result-product" in c)

    for li in lis:
        try:
            a = li.find("a", href=True)
            if not a:
                continue

            href = a["href"]

            if base and href.startswith("/"):
                href = urljoin(base, href)
            elif base and not href.startswith("http"):
                href = urljoin(base, href)

            if href not in seen:
                results.append(href)
                seen.add(href)
        except Exception:
            continue

    return results


# ---------------- CATEGORY SCRAPER ---------------- #
async def scrape_category_page(page, url: str) -> List[str]:
    logger.info("Visiting category page: %s", url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        await page.wait_for_load_state("networkidle", timeout=10000)
        await page.wait_for_selector("li.wizzy-result-product", timeout=10000)
        await page.wait_for_timeout(1000)

    except PlaywrightTimeoutError:
        logger.warning("Timeout loading %s", url)
    except Exception as e:
        logger.error("Navigation error: %s", e)
        return []

    final_html = await scroll_until_done(page, "li.wizzy-result-product")
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    product_urls = extract_product_urls_from_html(final_html, base)
    logger.info("Extracted %d products from %s", len(product_urls), url)

    return product_urls


# ---------------- MAIN FUNCTION ---------------- #
async def fetch_product_urls_from_categories():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Import COUNTRY_MAPPING from master
    try:
        from master import COUNTRY_MAPPING
        country_key = 'india'
        COUNTRY = COUNTRY_MAPPING.get(country_key, 'India')
    except ImportError:
        COUNTRY = "India"

    base_dir = Path(f"{COUNTRY}/{today}/Category")
    category_file = base_dir / f"{COUNTRY}_category_urls.json"
    
    output_dir = Path(f"{COUNTRY}/{today}/Items_urls")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{COUNTRY}_product_urls.json"
    progress_file = output_dir / f"{COUNTRY}_progress.log"

    # Check if category file exists
    if not category_file.exists():
        logger.error(f"Category file not found: {category_file}")
        return

    # Load category data
    try:
        with open(category_file, "r", encoding="utf-8") as f:
            category_data: Dict[str, Dict[str, str]] = json.load(f)
            logger.info("Loaded categories from %s", category_file)
    except Exception as e:
        logger.error("Category file error: %s", e)
        return

    # Load existing output if resuming
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as ef:
                output = json.load(ef)
                logger.info("Resuming from existing progress file: %s", output_file)
        except Exception as e:
            logger.warning("Could not load existing output file: %s", e)
            output = {}
    else:
        output = {}

    # Load progress log to skip already processed categories
    processed_categories = set()
    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        processed_categories.add(line)
            logger.info("Found %d already-processed categories in progress log", len(processed_categories))
        except Exception as e:
            logger.warning("Could not read progress log: %s", e)

    def log_progress(main_slug: str, subkey: str):
        """Write main_slug|subkey to progress log file"""
        key = f"{main_slug}|{subkey}"
        try:
            with open(progress_file, "a", encoding="utf-8") as f:
                f.write(f"{key}\n")
        except Exception as e:
            logger.warning("Could not write to progress log: %s", e)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        total_categories = sum(len(submap) for submap in category_data.values())
        processed_count = 0

        for main_slug, submap in category_data.items():
            output.setdefault(main_slug, {})

            for subkey, cat_url in submap.items():
                processed_count += 1
                progress_key = f"{main_slug}|{subkey}"
                
                # Skip if already processed
                if progress_key in processed_categories:
                    logger.info(f"[{processed_count}/{total_categories}] Skipping (already processed): {main_slug} > {subkey}")
                    continue

                logger.info(f"[{processed_count}/{total_categories}] Processing: {main_slug} > {subkey}")

                if not cat_url:
                    output[main_slug][subkey] = []
                    log_progress(main_slug, subkey)
                    continue

                try:
                    urls = await scrape_category_page(page, cat_url)
                    output[main_slug][subkey] = urls
                    
                    # Save progress immediately after each category
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(output, f, indent=2, ensure_ascii=False)
                    
                    # Log to progress file
                    log_progress(main_slug, subkey)
                    
                    logger.info(f" Saved {len(urls)} URLs for {main_slug} > {subkey}")
                    
                except Exception as e:
                    logger.exception("Scraping failed %s -> %s: %s", main_slug, subkey, e)
                    output[main_slug][subkey] = []
                    log_progress(main_slug, subkey)  # Log even on failure to avoid retry

                await page.wait_for_timeout(800)

        await browser.close()

    # Final save
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Finished. Output: %s", output_file)
    logger.info("Progress log: %s", progress_file)
    return output_file, output


# ---------------- RUNNER ---------------- #
if __name__ == "__main__":
    asyncio.run(fetch_product_urls_from_categories())
