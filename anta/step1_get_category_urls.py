import logging
import os
import json
import re
import asyncio
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import unicodedata

# ---------------------- LOGGING ---------------------- #
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

countries = {
    "USA": "https://anta.com/",
    "UK": "https://uk.anta.com/"
}

def create_base_dir(country):
    today_str = date.today().strftime("%Y-%m-%d")
    base_dir = f"{country}/Data/{today_str}/Item_urls"
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

# ---------------------- SCRAPERS ---------------------- #

async def scrape_uk_category_urls(page, base_dir, base_url):
    """
    Extract category -> subcategory mapping for UK site.

    Special handling for Basketball / Kyrie Irving:
      - Walk descendant <li> elements and for each take the first <a href> -> URL and a.get_text(strip=True) -> name.
      - Apply the variant filter (Option 3): drop any URL containing '?variant='.

    Default behavior for other categories remains the same.
    """
    category_urls = {}
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    exclude_keywords = ["login", "cart"]

    special_mains = {"basketball", "kyrie irving", "kyrie-irving", "kyrie"}

    def is_variant_url(href: str) -> bool:
        """Return True if URL contains a variant query param (we will drop those)."""
        if not href:
            return False
        return "?" in href and "variant=" in href

    # iterate through nav list items (top-level menu)
    for li in soup.find_all("li", class_=re.compile(r"(nav-item|tab-menu-wrapper)")):
        main_a = li.find("a", href=True)
        if not main_a:
            continue

        main_href = main_a["href"].strip()
        if any(k in main_href.lower() for k in exclude_keywords):
            continue

        main_name = (main_a.get("aria-label") or main_a.get_text(strip=True) or "").strip()
        main_name = unicodedata.normalize("NFKD", main_name).encode("ascii", "ignore").decode("utf-8")
        if not main_name:
            continue

        main_href = urljoin(base_url, main_href)
        category_urls[main_name] = {}

        # --- SPECIAL CASE: Basketball / Kyrie Irving ---
        if main_name.strip().lower() in special_mains:
            # Find the relevant container(s) that hold the level-2 items.
            # We'll look for the desktop container first, then fall back to mobile list.
            containers = []

            # desktop: look for the second-menu-wrapper block inside this li
            desktop_container = li.find("div", class_=re.compile(r"second-menu-wrapper|scroll-content|scroll-container"))
            if desktop_container:
                containers.append(desktop_container)

            # mobile / accessible lists (ul with second-menu-wrapper-only-text)
            mobile_ul = li.find("ul", class_=re.compile(r"second-menu-wrapper-only-text"))
            if mobile_ul:
                containers.append(mobile_ul)

            # also, try the whole li as a last resort
            if not containers:
                containers.append(li)

            seen = set()
            for container in containers:
                # iterate <li> descendants that represent items (this matches the provided HTML)
                for item_li in container.find_all("li", recursive=True):
                    # find the first anchor inside the li
                    a = item_li.find("a", href=True)
                    if not a:
                        continue
                    href = a["href"].strip()
                    # drop variant URLs per rule 3
                    if is_variant_url(href):
                        continue
                    if any(k in href.lower() for k in exclude_keywords):
                        continue
                    name = a.get_text(strip=True)
                    if not name:
                        # if anchor text empty, try nearby text nodes
                        name = item_li.get_text(separator=" ", strip=True)
                    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("utf-8")
                    if not name:
                        continue
                    full_href = urljoin(base_url, href)
                    # Avoid duplicates (normalize by lowercased href)
                    key = (name.lower(), full_href)
                    if key in seen:
                        continue
                    seen.add(key)
                    category_urls[main_name][name] = full_href

            logging.info(f"Special-case ({main_name}): extracted {len(category_urls[main_name])} items from li->a parsing.")
            continue  # done with this li

        # --- DEFAULT BEHAVIOR FOR NON-SPECIAL CATEGORIES ---
        sub_links = li.find_all("a", class_=re.compile(r"dropdown-item"), href=True)
        if sub_links:
            for sub_a in sub_links:
                sub_href = sub_a["href"].strip()
                if is_variant_url(sub_href):
                    continue
                if any(k in sub_href.lower() for k in exclude_keywords):
                    continue
                sub_name = (sub_a.get("aria-label") or sub_a.get_text(strip=True) or "").strip()
                sub_name = unicodedata.normalize("NFKD", sub_name).encode("ascii", "ignore").decode("utf-8")
                if sub_name:
                    sub_href = urljoin(base_url, sub_href)
                    category_urls[main_name][sub_name] = sub_href
        else:
            category_urls[main_name] = main_href

    # -------------------------
    # POST-PROCESSING CLEANUP
    # -------------------------
    # remove accidental top-level entries that are not dicts (like "Clutch", "Klay", etc.)
    keys_to_delete = []
    for key, val in list(category_urls.items()):
        if not isinstance(val, dict):
            keys_to_delete.append(key)

    for key in keys_to_delete:
        logging.info(f"Removing accidental top-level entry: {key}")
        del category_urls[key]

    logging.info(f"Extracted {len(category_urls)} main categories from UK site.")
    return category_urls


async def scrape_usa_category_urls(page, base_dir, base_url):
    category_urls = {}
    pop_key = ["Bag", "Cap", "Hat", "Socks", "Accessories"]
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    div_tag = soup.find("div", class_=re.compile("site-header-container"))
    if div_tag:
        sub_div_tags = div_tag.find_all(
            "div", class_=re.compile("grid-template-rows-wrapper-third|as-sub-dropdown-menu")
        )
        for sub in sub_div_tags:
            a_tags = sub.find_all("a", href=True)
            for a in a_tags:
                href = urljoin(base_url, a["href"].strip())
                text = a.get_text(strip=True)
                text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
                if any(keyword in text for keyword in pop_key):
                    continue
                if text:
                    category_urls[text] = href

    logging.info(f"Extracted {len(category_urls)} categories from USA site.")
    return category_urls

# ---------------------- IMPROVED REGION SELECTOR ---------------------- #

async def _save_debug_screenshot(page, suffix="region_fail"):
    try:
        debug_dir = "debug_screens"
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, f"{suffix}.png")
        await page.screenshot(path=path, full_page=True)
        logging.info(f"Saved debug screenshot: {path}")
    except Exception as e:
        logging.warning(f"Failed to save debug screenshot: {e}")

async def select_region(page, region_code="UK", wait_timeout=30000):
    """
    Robustly select a region inside the region modal. Tries multiple fallbacks:
    1) locator.click()
    2) scrollIntoViewIfNeeded() + locator.click()
    3) evaluate(el => el.click()) (bypass Playwright visibility checks)
    4) find parent .region-item with visible text "United Kingdom" and click anchor via JS
    5) fallback to window.location = href
    Returns True on success, False on failure.
    """
    logging.info("Scrolling to bottom to ensure region selector is loaded...")
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass
    await asyncio.sleep(1.0)

    # open modal
    logging.info("Opening region selector modal...")
    btn = page.locator('a.selected-store-btn, .selected-store-btn')
    if await btn.count() > 0:
        try:
            await btn.first.click()
        except Exception:
            # try evaluate click as fallback
            await btn.first.evaluate("el => el.click()")
    else:
        alt = page.locator('.as-selector-modal a')
        if await alt.count() > 0:
            try:
                await alt.first.click()
            except Exception:
                await alt.first.evaluate("el => el.click()")
        else:
            logging.error("Region selector button not found.")
            return False

    # wait for modal and its store-list to appear
    try:
        await page.wait_for_selector('#regionSelectorModal', timeout=wait_timeout)
        # wait for at least one store-list entry to appear inside modal
        await page.wait_for_selector('#regionSelectorModal .store-list, .as-modal-region-list-with-region, .as-modal-region-list-without-region', timeout=wait_timeout)
    except Exception as e:
        logging.error(f"Region modal did not appear or content not loaded: {e}")
        await _save_debug_screenshot(page, "modal_missing")
        return False

    await asyncio.sleep(0.7)

    # attempt to locate the anchor
    locator_selector = f'a.stretched-link.as-store[data-region-code="{region_code}"]'
    region_link = page.locator(locator_selector)
    if await region_link.count() == 0:
        logging.info("Primary locator not found, trying by visible text 'United Kingdom' or href contains 'uk.anta.com'...")
        region_link = page.locator('a.stretched-link.as-store', has_text="United Kingdom")
        if await region_link.count() == 0:
            region_link = page.locator('a.stretched-link.as-store[href*="uk.anta.com"]')

    if await region_link.count() == 0:
        # final fallback: search within region-item blocks for the text and then select anchor inside it
        logging.info("Trying to find .region-item that contains 'United Kingdom' text...")
        candidate = page.locator('.region-item', has_text="United Kingdom")
        if await candidate.count() > 0:
            region_link = candidate.locator('a.stretched-link.as-store')

    if await region_link.count() == 0:
        logging.error("Could not find any UK region anchor inside modal.")
        await _save_debug_screenshot(page, "region_anchor_not_found")
        return False

    logging.info(f"Found {await region_link.count()} candidate(s) for UK region. Attempting click...")

    # Try several click methods, returning on first success
    for attempt in range(1, 5):
        try:
            if attempt == 1:
                # Normal Playwright click (requires visible/stable)
                logging.info("Attempt 1: locator.click()")
                async with page.expect_navigation(timeout=10000):
                    await region_link.first.click()
                logging.info("Clicked and navigation detected.")
                return True
            elif attempt == 2:
                # scroll into view and click
                logging.info("Attempt 2: scrollIntoViewIfNeeded() + click")
                try:
                    await region_link.first.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                async with page.expect_navigation(timeout=10000):
                    await region_link.first.click()
                logging.info("Clicked after scroll and navigation detected.")
                return True
            elif attempt == 3:
                # JS click (bypass Playwright visibility)
                logging.info("Attempt 3: evaluate(el => el.click())")
                href = await region_link.first.get_attribute("href")
                # Try evaluate click and wait for navigation
                try:
                    async with page.expect_navigation(timeout=10000):
                        await region_link.first.evaluate("el => el.click()")
                    logging.info("JS click triggered navigation.")
                    return True
                except Exception:
                    # if no navigation observed, but href exists, set location
                    if href:
                        logging.info("No navigation after JS click; setting window.location.href to the anchor href as fallback.")
                        await page.evaluate(f"window.location.href = {json.dumps(href)}")
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)
                        return True
            elif attempt == 4:
                # Last resort: get href and set window.location to it
                logging.info("Attempt 4: final fallback -> read href and set window.location")
                href = await region_link.first.get_attribute("href")
                if href:
                    await page.evaluate(f"window.location.href = {json.dumps(href)}")
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    logging.info("Navigation by setting window.location succeeded.")
                    return True
                else:
                    logging.error("Region anchor has no href to navigate to.")
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed: {e}")
            await asyncio.sleep(0.5)

    # If we reach here, all attempts failed
    logging.error("All attempts to click/select the UK region failed.")
    await _save_debug_screenshot(page, "region_click_failed")
    return False

# ---------------------- MAIN FLOW (open USA page, wait, then UK page) ---------------------- #

async def scrape_country(context, country, url):
    base_dir = create_base_dir(country)
    page = await context.new_page()
    logging.info(f"Opening {country}: {url}")
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        logging.info(f"Loaded {url} status: {resp.status if resp else 'no response'}")
    except Exception as e:
        logging.error(f"Failed to open {url}: {e}")
        await page.close()
        return False

    # If UK, run the selector helper
    if country == "UK":
        logging.info("Selecting UK region…")
        ok = await select_region(page, region_code="UK")
        if not ok:
            logging.warning("Region selection failed. Proceeding to scrape current page anyway.")
        # small wait for the site to settle
        await asyncio.sleep(1.5)

    current_url = page.url.rstrip("/") + "/"
    logging.info(f"Final URL for {country}: {current_url}")

    # scrape
    try:
        if country == "UK":
            categories = await scrape_uk_category_urls(page, base_dir, current_url)
        else:
            categories = await scrape_usa_category_urls(page, base_dir, current_url)
    except Exception as e:
        logging.error(f"Error during scraping for {country}: {e}")
        categories = {}

    # save
    out_path = os.path.join(base_dir, f"{country}_category_urls.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=4, ensure_ascii=False)
    logging.info(f"Saved category urls -> {out_path}")

    await page.close()
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        # 1) Open USA page first
        logging.info("=== START: USA PAGE ===")
        await scrape_country(context, "USA", countries["USA"])

        # wait between pages as requested
        wait_seconds = 5
        logging.info(f"Waiting {wait_seconds} seconds before opening UK page...")
        await asyncio.sleep(wait_seconds)

        # 2) Open UK page and ensure region is selected
        logging.info("=== START: UK PAGE ===")
        await scrape_country(context, "UK", countries["UK"])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())



