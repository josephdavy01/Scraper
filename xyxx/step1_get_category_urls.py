import json
import re
import asyncio
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def fetch_category_urls():
    url = "https://xyxxcrew.com/"
    
    # Import COUNTRY_MAPPING from master
    from master import COUNTRY_MAPPING
    
    # Use the mapping to get proper capitalization
    country_key = 'india'  # lowercase key from COUNTRIES dict
    country = COUNTRY_MAPPING.get(country_key, 'India')  # Get capitalized name
    
    headless = False

    # ---------------- HELPERS ---------------- #
    def slugify(s: str) -> str:
        s = s or ""
        s = s.strip().lower()
        s = re.sub(r"[ \t/]+", "_", s)
        s = re.sub(r"[^a-z0-9_\-]", "", s)
        s = re.sub(r"_+", "_", s)
        return s

    def safe_get_text(el):
        return el.get_text(strip=True) if el else ""

    def make_absolute(href: str, base: Optional[str]):
        if not href:
            return ""
        if base and (href.startswith("/") or not href.startswith("http")):
            return urljoin(base, href)
        return href

    def extract_categories_from_soup(soup: BeautifulSoup, base_url: Optional[str] = None):
        out = {}
        parent = soup.find("div", class_="hb_header") or soup
        level = parent.find("div", class_="header-sticky-wrapper")
        if level: level = level.find("div", class_="header-wrapper")
        if level: level = level.find("div", id="StickyHeaderWrap")
        if level: level = level.find("div", class_="site-header")
        if level: level = level.find("div", class_="page-width")
        if level: level = level.find("div", class_="header-layout header-layout--left-center")
        if level: level = level.find("div", class_="header-item header-item--navigation text-center")

        ul = level.find("ul", class_="site-nav site-navigation small--hide") if level else None
        if not ul:
            ul = soup.find("ul", class_=re.compile(r"(site-nav|site-navigation)"))
            if not ul:
                return out

        all_lis = ul.find_all("li", recursive=False)

        for li in all_lis:
            cls_str = " ".join(li.get("class") or [])
            has_megamenu = "site-nav--is-megamenu" in cls_str
            base_item = "site-nav__item" in cls_str and "site-nav__expanded-item" in cls_str
            if not base_item:
                continue

            a_main = li.find("a")
            main_text = safe_get_text(a_main)
            main_href = make_absolute(a_main.get("href") if a_main else "", base_url)
            main_key = slugify(main_text) or "unknown_main"

            if main_key not in out:
                out[main_key] = {}

            if has_megamenu:
                dropdown = li.find("div", class_="site-nav__dropdown") or li
                cols = dropdown.find_all("div", class_="megamenu__col")

                for col in cols:
                    title_div = col.find("div", class_="megamenu__col-title")
                    if not title_div:
                        continue

                    second_level = safe_get_text(title_div.find("a")) or safe_get_text(title_div)
                    second_slug = slugify(second_level) or "unknown_second"

                    links = col.find_all("a")
                    added = False

                    for a in links:
                        if title_div.find("a") is a:
                            continue

                        third_text = safe_get_text(a)
                        third_href = make_absolute(a.get("href"), base_url)

                        if not third_text:
                            continue

                        key = f"{second_slug}_{slugify(third_text)}"
                        out[main_key][key] = third_href
                        added = True

                    if not added:
                        out[main_key][f"{second_slug}_{second_slug}"] = main_href
            else:
                out[main_key][f"{main_key}_{main_key}"] = main_href

        return out

    async def try_close_cookie_banner(page):
        cookie_selectors = [
            "button[id*='accept']",
            "button[class*='accept']",
            "button[aria-label*='accept']",
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Allow')",
            "button:has-text('Got it')",
            "button:has-text('Close')",
            "div.cookie-banner button"
        ]
        for sel in cookie_selectors:
            try:
                handle = await page.query_selector(sel)
                if handle:
                    await handle.click(timeout=3000)
                    await page.wait_for_timeout(300)
                    return True
            except Exception:
                pass
        return False

    async def fetch_with_playwright(url: str, headless: bool = True) -> Tuple[str, Optional[str]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                logger.info("Loading %s", url)
                await page.goto(url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_timeout(1000)
            await try_close_cookie_banner(page)

            li_handles = await page.query_selector_all("nav li, header li, ul li")
            for li in li_handles[:40]:
                try:
                    await li.hover(timeout=2000)
                    await page.wait_for_timeout(300)
                except:
                    pass

            html = await page.content()
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

            await browser.close()
            return html, base

    # ---------------- MAIN EXECUTION ---------------- #
    today = datetime.now().strftime("%Y-%m-%d")
    save_dir = Path(f"{country}/{today}/Category")
    save_dir.mkdir(parents=True, exist_ok=True)
    output_file = save_dir / f"{country}_category_urls.json"

    html, base = await fetch_with_playwright(url, headless=headless)
    soup = BeautifulSoup(html, "html.parser")
    data = extract_categories_from_soup(soup, base_url=base)

    data.pop("accessories", None)
    data.pop("accessory", None)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved: %s", output_file)
    return output_file, data


# ---------------- CALL ---------------- #
if __name__ == "__main__":
    asyncio.run(fetch_category_urls())
