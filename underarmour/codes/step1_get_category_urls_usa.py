#!/usr/bin/env python3
# get_product_data_under_uk.py
"""
Simplified Playwright scraper for Under Armour UK navigation.
Replace your existing file with this to remove Pylance 'try without except' errors.
"""
import time
import json
import logging
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# CONFIG
BASE_URL = "https://www.underarmour.com/en-us/"
COUNTRY = "USA"
TODAY = date.today().strftime("%Y-%m-%d")
OUT_DIR = Path(COUNTRY) / "Data" / TODAY / "Item_urls"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUT_DIR / "Category_urls.json"
HEADLESS = False
HOVER_DELAY = 0.25
NAV_TIMEOUT = 12000

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def apply_stealth(page):
    """Apply a small stealth script; ignore errors."""
    try:
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            """
        )
    except Exception:
        # intentionally silent — stealth is optional
        return


def click_if_locator_exists(page, selector, timeout=3000):
    """Click the first element matching selector if present. Returns True if clicked."""
    try:
        locator = page.locator(selector)
        if locator.count() > 0:
            locator.first.click(timeout=timeout)
            return True
    except Exception:
        # fallback: try evaluate click on first element
        try:
            el = page.query_selector(selector)
            if el:
                el.evaluate("el => el.click()")
                return True
        except Exception:
            return False
    return False


def select_uk(page):
    """Handle country selection dialog — attempt several strategies."""
    time.sleep(1.0)
    # Try title="gb"
    if click_if_locator_exists(page, 'a[title="gb"]'):
        time.sleep(0.8)
        return True
    # Try by visible text
    if click_if_locator_exists(page, 'text="United Kingdom"'):
        time.sleep(0.8)
        return True
    # Try anchors inside a known dialog wrapper
    if click_if_locator_exists(page, "div.Dialog_content-wrapper__MihtT a[title='gb']"):
        time.sleep(0.8)
        return True
    # Nothing clicked — continue
    return False


def accept_cookies(page):
    """Try common cookie/consent selectors."""
    time.sleep(0.6)
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button:has-text('Accept cookies')",
        "button:has-text('Accept Cookies')",
        "button:has-text(\"Yes, I'm in\")",
        "button:has-text('Continue')",
        "button[aria-label='Close']",
        "button[data-testid='consent-accept']",
    ]
    for sel in selectors:
        if click_if_locator_exists(page, sel):
            time.sleep(0.5)
            return True

    # Generic fallback: click first button that contains 'accept' or 'agree'
    try:
        btns = page.query_selector_all("button")
        for b in btns:
            try:
                txt = b.inner_text().lower()
            except Exception:
                txt = ""
            if "accept" in txt or "agree" in txt or "yes" in txt:
                try:
                    b.click()
                    time.sleep(0.4)
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def safe_text(el):
    """Return inner text for an element handle or ''."""
    if not el:
        return ""
    try:
        return el.inner_text().strip()
    except Exception:
        try:
            return el.text_content().strip()
        except Exception:
            return ""


def extract_mapping_from_li(li, base_url):
    """Given a top-level li handle, extract the mapping dict for that main category."""
    main_name = safe_text(li.query_selector("a")) or safe_text(li)
    if not main_name:
        return None, {}

    result = {}
    # find submenu wrapper
    sub_menu = li.query_selector("div.DesktopNav_nav__sub-menu__KQ69S") or li.query_selector("div")
    if not sub_menu:
        return main_name, {}

    # first-level ul
    sub_cat_ul = sub_menu.query_selector("ul.DesktopSubNav_sub-menu-category-list__lxB3e") or sub_menu.query_selector("ul")
    if not sub_cat_ul:
        return main_name, {}

    first_level_lis = sub_cat_ul.query_selector_all("li.DesktopSubNav_sub-menu-categories___CfbH") \
                      or sub_cat_ul.query_selector_all("li")
    for lvl1 in first_level_lis:
        sub1_tag = lvl1.query_selector(":scope > a, :scope > h2") or lvl1.query_selector("a, h2")
        sub1_name = safe_text(sub1_tag)
        if not sub1_name:
            continue
        grouping_ul = lvl1.query_selector("ul.DesktopSubNav_sub-menu-category-grouping__MarkK") or lvl1.query_selector("ul")
        if not grouping_ul:
            continue
        sub2_lis = grouping_ul.query_selector_all(":scope > li")
        for sub2 in sub2_lis:
            a = sub2.query_selector("a")
            if not a:
                continue
            data_disabled = ""
            try:
                data_disabled = a.get_attribute("data-disabled") or ""
            except Exception:
                data_disabled = ""
            if data_disabled.lower() == "true":
                continue
            sub2_name = safe_text(a)
            href = ""
            try:
                href = a.get_attribute("href") or ""
            except Exception:
                href = ""
            if not href:
                continue
            full = urljoin(base_url, href)
            key = f"{sub1_name}_{sub2_name}"
            # avoid clobbering keys
            if key in result:
                idx = 2
                while f"{key}_{idx}" in result:
                    idx += 1
                key = f"{key}_{idx}"
            result[key] = full
    return main_name, result


def run_scrape():
    """Main run function. Returns the mapping dict."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()
        apply_stealth(page)

        try:
            page.goto(BASE_URL, timeout=30000)
        except PlaywrightTimeoutError:
            logging.warning("Initial navigation timed out.")

        # handle dialogs
        select_uk(page)
        accept_cookies(page)

        # wait for nav
        try:
            page.wait_for_selector("header.no-print.fixed-header", timeout=NAV_TIMEOUT)
        except PlaywrightTimeoutError:
            logging.warning("Nav header not found within timeout; continuing with fallback selectors.")

        selector = (
            "header.no-print.fixed-header "
            "div.Header_navBar__YM_ii.Header_desktop-nav-bar__D3MxQ "
            "nav.DesktopNav_nav__menu__IW4NH "
            "ul.DesktopNav_nav__list__w_wGN "
            "li.DesktopNav_nav__list-item__KH2lQ"
        )
        li_items = page.query_selector_all(selector)
        if not li_items:
            li_items = page.query_selector_all("nav.DesktopNav_nav__menu__IW4NH ul li")

        logging.info(f"Top-level items found: {len(li_items)}")

        mapping = {}
        for i, li in enumerate(li_items, 1):
            # hover to reveal submenu
            try:
                li.hover()
            except Exception:
                a = li.query_selector("a")
                if a:
                    try:
                        a.hover()
                    except Exception:
                        pass
            time.sleep(HOVER_DELAY)
            main, submap = extract_mapping_from_li(li, BASE_URL)
            if main and submap:
                mapping.setdefault(main, {}).update(submap)
                logging.info(f"Collected {len(submap)} links under '{main}'")

        # close browser
        try:
            context.close()
            browser.close()
        except Exception:
            pass

        return mapping


def save_output(data):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved output: {OUTPUT_FILE}")
    except Exception:
        logging.exception("Failed to save output JSON.")


def main():
    mapping = run_scrape()
    if mapping:
        save_output(mapping)
    else:
        logging.warning("No mapping extracted.")


if __name__ == "__main__":
    main()
