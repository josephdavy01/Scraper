#!/usr/bin/env python3
"""
scrape_and_normalize.py

Usage:
    python scrape_and_normalize.py

Requirements:
    - playwright (pip install playwright)
    - playwright browsers installed (playwright install)
    - beautifulsoup4

This script:
  - opens each site (USA and UK),
  - waits a bit to allow popups to appear,
  - hovers top-level nav items to reveal submenus,
  - extracts submenu links,
  - normalizes collection links (slug, gender, sizes),
  - saves raw scrape and a single category_urls.json per country:
      { "women": { "subcategory": "url", ... }, "men": { ... }, "sale": { ... } }
"""

import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import os
from datetime import date
import re

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ---------------- Config ----------------
# how many seconds to wait after opening homepage to allow popups to appear
WAIT_FOR_POPUP_SECONDS = 10

# set to True to run headless
HEADLESS_MODE = False

# ---------------- Popup & hover helpers ----------------

def close_popups(page):
    """Try multiple strategies to close or remove popups that block interaction."""
    try:
        close_buttons = page.query_selector_all(
            "button.klaviyo-close-form, button[aria-label='Close dialog'], .klaviyo-close-form, button[aria-label='Close']"
        )
        for btn in close_buttons:
            try:
                if btn.is_visible():
                    btn.click()
                    logging.info("Closed a popup via close button.")
                    time.sleep(1)
                    return
            except Exception:
                # ignore per-button issues and continue trying others
                continue

        # Remove overlay popup if blocking clicks
        popup = page.query_selector("div[role='dialog'][aria-label*='POPUP']")
        if popup:
            page.evaluate("el => el.remove()", popup)
            logging.info("Removed popup overlay via JS.")
            time.sleep(0.5)
            return

        # generic remove known overlays
        page.evaluate(
            """() => {
                const els = document.querySelectorAll('.klaviyo-form, .overlay, [data-testid="modal"], .modal');
                els.forEach(e => e.remove());
            }"""
        )
    except Exception as e:
        logging.warning(f"Popup close attempt failed: {e}")


def hover_with_popup_handling(page, selector, retries=3):
    """Attempt to hover over an element, handling popups dynamically."""
    for attempt in range(1, retries + 1):
        try:
            close_popups(page)
            time.sleep(1)
            page.hover(selector, timeout=8000)
            logging.info(f"Hovered over {selector} successfully.")
            return True
        except Exception as e:
            logging.warning(f"Hover attempt {attempt} failed for {selector}: {e}")
            close_popups(page)
            time.sleep(2)

    # Fallback: use JS hover if all retries fail
    try:
        element = page.query_selector(selector)
        if element:
            page.evaluate(
                """el => el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))""",
                element,
            )
            logging.info(f"Triggered JS hover for {selector} as fallback.")
            return True
    except Exception as e:
        logging.error(f"JS hover fallback failed for {selector}: {e}")

    logging.error(f"Failed to hover over {selector} after {retries} attempts.")
    return False

# ---------------- Scraper ----------------

def get_category_urls(country: str, base_url: str, headless: bool = False):
    """
    Scrape top-level category submenu links for a given country/site.
    country: 'USA' or 'UK' (case-insensitive)
    base_url: homepage (used to resolve relative URLs)
    headless: if True, run browser headless
    """
    target_categories_usa = {
        "women": "#menu-item-1",
        "men": "#menu-item-2",
        "sale": "#menu-item-3",
    }

    target_categories_uk = {
        "women": "#menu-item-0",
        "men": "#menu-item-1",
        "sale": "#menu-item-3",
    }

    # choose mapping based on country name
    country_key = (country or "").strip().lower()
    if country_key in ("usa", "us", "united states"):
        target_categories = target_categories_usa
    elif country_key in ("uk", "united kingdom", "gb", "great britain"):
        target_categories = target_categories_uk
    else:
        logging.warning(
            f"Unknown country '{country}'. Defaulting to USA selectors. Provide 'USA' or 'UK'."
        )
        target_categories = target_categories_usa

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            logging.info(f"Opening {base_url}")
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            logging.warning("Page load timed out; continuing with what is available.")
        except Exception as e:
            logging.error(f"Failed to open {base_url}: {e}")
            context.close()
            browser.close()
            return results

        # WAIT so popups have a chance to appear before we attempt to close them / scrape
        logging.info(f"Waiting {WAIT_FOR_POPUP_SECONDS}s for popups to appear (if any)...")
        time.sleep(WAIT_FOR_POPUP_SECONDS)

        # Try once to close popups after waiting
        close_popups(page)

        # try to ensure the nav is present but don't hard-fail
        try:
            page.wait_for_selector("ul.navbar-linklist", timeout=10000)
        except PlaywrightTimeoutError:
            logging.info("Navbar not found within timeout — continuing (submenu parsing may fail).")

        for category, selector in target_categories.items():
            logging.info(f"Processing category '{category}' using selector '{selector}'")
            # attempt to hover and open submenu
            hovered = hover_with_popup_handling(page, selector)
            if not hovered:
                logging.warning(f"Could not open submenu for {category}. Skipping.")
                results[category] = {}
                continue

            # small wait to allow submenu DOM to render
            time.sleep(4)
            close_popups(page)
            time.sleep(1)

            # get current page html and parse
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            all_links = {}
            seen_hrefs = set()

            # find probable submenu container(s)
            all_subnavs = soup.find_all("div", class_="navbar-subnav")
            if not all_subnavs:
                logging.info(f"No submenu found for {category}")
                results[category] = all_links
                # move mouse away to collapse menu, attempt to continue
                try:
                    page.mouse.move(0, 0)
                except Exception:
                    pass
                time.sleep(1)
                continue

            # heuristic: the last navbar-subnav is often the active one after hover
            navbar_subnav = all_subnavs[-1]

            # keys to skip (example)
            pop_keys = ["holiday-gift-card", "gift-card", "promo"]

            links = navbar_subnav.find_all("a", href=True)
            for link in links:
                href = link.get("href")
                text = link.get_text(strip=True)

                if not href:
                    logging.info(f"Skipped link with no href: text='{text}'")
                    continue

                if any(key in href for key in pop_keys):
                    logging.info(f"Skipped popup/gift link: {href}")
                    continue

                # normalize and avoid duplicates
                if href not in seen_hrefs:
                    seen_hrefs.add(href)
                    key = text.lower().replace(" ", "_") if text else href
                    absolute_url = urljoin(base_url, href)
                    all_links[key] = absolute_url
                    logging.info(f"Added: {text} -> {absolute_url}")
                else:
                    logging.info(f"Duplicate href skipped: {href}")

            results[category] = all_links

            # move mouse off menu to collapse it before next category
            try:
                page.mouse.move(0, 0)
            except Exception:
                pass
            time.sleep(1)

        context.close()
        browser.close()

    return results

# ---------------- Normalization helpers ----------------

def extract_slug_and_params_from_href(href: str):
    """
    Given an href (absolute or relative), extract collection slug (first segment after /collections/)
    and parse gender/sizes if available.
    Returns: dict { 'slug': str or None, 'gender': str or None, 'sizes': str or None, 'raw_query': dict }
    """
    if not href:
        return {"slug": None, "gender": None, "sizes": None, "raw_query": {}}

    # Ensure we only work with the path+query
    parsed = urlparse(href)
    path = parsed.path or ""
    query = parsed.query or ""

    # path might be like /collections/sale or /collections/womens-sandals
    slug = None
    m = re.search(r"/collections/([^/?#]+)", path, flags=re.IGNORECASE)
    if m:
        slug = m.group(1).strip().lower()

    # parse query params
    q = parse_qs(query, keep_blank_values=True)
    # simplify values (take first)
    q_simple = {k: (v[0] if isinstance(v, list) else v) for k, v in q.items()}

    # try extracting gender from typical encoded pattern like:
    # gender=data--gender%3AMen%27s  -> decode -> "data--gender:Men's"
    gender = None
    if "gender" in q_simple:
        decoded = unquote(q_simple["gender"])
        # look for patterns like data--gender:Men's  or data--gender%3AMen%27s
        mg = re.search(r"data--gender[:=](.+)", decoded, flags=re.IGNORECASE)
        if mg:
            gender_val = mg.group(1).strip()
            # normalize common forms like "Men's" -> "men"
            gender_val = gender_val.replace("%27", "'")
            # remove non-alpha and make lower
            gender = re.sub(r"[^A-Za-z]+", "", gender_val).lower()
        else:
            # fallback: try to directly infer male/female/unisex
            fallback = re.sub(r"[^A-Za-z]+", "", decoded).lower()
            if fallback in ("men", "mens", "male"):
                gender = "men"
            elif fallback in ("women", "womens", "female"):
                gender = "women"
            elif fallback:
                gender = fallback

    # sometimes size is passed as sizes=13
    sizes = None
    if "sizes" in q_simple:
        sizes = q_simple["sizes"]

    # also check path for explicit gender-like segments (e.g., /collections/men)
    if not gender and slug in ("men", "women", "mens", "womens"):
        gender = "men" if slug.startswith("men") else "women"

    return {"slug": slug, "gender": gender, "sizes": sizes, "raw_query": q_simple}


def normalize_category_links(raw_category_map: dict):
    """
    Accepts the per-category raw mapping (like your JSON input)
    and returns two structures:
      - detailed: { normalized_key: { 'url', 'slug', 'gender', 'sizes', 'raw_key' } }
      - simple:   { normalized_key: url }
    The script will ultimately save the 'simple' mapping as category_urls.json
    """
    detailed = {}
    simple = {}

    for raw_key, url in raw_category_map.items():
        # raw_key may be the text like '/collections/womens-sandals' or 'new_arrivals' or absolute URL
        href = url
        info = extract_slug_and_params_from_href(href)

        slug = info["slug"]
        gender = info["gender"]
        sizes = info["sizes"]

        # Build a normalized base name
        if slug:
            base = slug
        else:
            # fallback to sanitized raw_key if no slug present
            base = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_key.strip().lower())

        # attach params to create unique keys if necessary
        parts = [base]
        if gender:
            parts.append(f"gender_{gender}")
        if sizes:
            parts.append(f"size_{sizes}")

        normalized_key = "__".join(parts)

        # ensure uniqueness: if already exists, append a counter
        counter = 1
        candidate = normalized_key
        while candidate in simple:
            counter += 1
            candidate = f"{normalized_key}__{counter}"
        normalized_key = candidate

        detailed[normalized_key] = {
            "url": href,
            "slug": slug,
            "gender": gender,
            "sizes": sizes,
            "raw_key": raw_key,
        }
        simple[normalized_key] = href

    return detailed, simple

# ---------------- Save outputs ----------------

def save_category_urls_file(country: str, jsondata: dict, out_dir_base: str = "."):
    """
    Save:
      - raw scraped result (country/.../country_category_urls_raw.json)
      - a single category_urls.json with structure:
            { "women": { "subcategory_name": "url", ... }, "men": {...}, "sale": {...} }
    """
    today_str = date.today().strftime("%Y-%m-%d")
    output_path = os.path.join(out_dir_base, country, "Data", today_str, "Item_urls")
    os.makedirs(output_path, exist_ok=True)

    simple_all = {}

    for category, mapping in (jsondata or {}).items():
        logging.info(f"Normalizing {category} with {len(mapping)} items")
        _, simple = normalize_category_links(mapping)
        # add category mapping (subcat -> url)
        simple_all[category] = simple

    # write single category_urls.json
    category_urls_file = os.path.join(output_path, f"{country}_category_urls.json")
    with open(category_urls_file, "w", encoding="utf-8") as f:
        json.dump(simple_all, f, indent=4, ensure_ascii=False)

    logging.info(f"Saved category URLs -> {category_urls_file}")
    return simple_all

# ---------------- Main ----------------

def main():
    today_str = date.today().strftime("%Y-%m-%d")

    countries = {
        "USA": "https://www.oofos.com",
        "UK": "https://www.oofos.co.uk",
    }

    for country, url in countries.items():
        logging.info(f"Fetching {country} category URLs now from {url}")
        jsondata = get_category_urls(country, url, headless=HEADLESS_MODE)

        # save raw scraped result for reference
        raw_output_path = os.path.join(country, "Data", today_str, "Item_urls")
        os.makedirs(raw_output_path, exist_ok=True)
        raw_output_file = os.path.join(raw_output_path, f"{country}_category_urls_raw.json")
        with open(raw_output_file, "w", encoding="utf-8") as f:
            json.dump(jsondata, f, indent=4, ensure_ascii=False)
        logging.info(f"Saved raw scrape -> {raw_output_file}")

        # normalize & save a single category_urls.json
        save_category_urls_file(country, jsondata, out_dir_base=".")

        logging.info(f"{country} category URLs fetched and normalized.")

if __name__ == "__main__":
    main()
