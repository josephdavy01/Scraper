import os
import json
import logging
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

BASE_URL = "https://paige.com"
COUNTRY = "USA"
HEADLESS = False  # Set to True for headless scraping

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def handle_popups(page):
    """Close cookie banners, Klaviyo, and other pop-ups if visible."""
    popup_selectors = [
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button.needsclick.klaviyo-close-form",
        "div.needsclick button[aria-label='Close dialog']",
        "button[aria-label='Close']",
        "button:has-text('No Thanks')",
        ".popup-close",
        ".close-button",
        ".close"
    ]

    for sel in popup_selectors:
        try:
            locator = page.locator(sel)
            if locator.is_visible():
                locator.click(timeout=2000)
                logging.info(f"Closed popup: {sel}")
                page.wait_for_timeout(1000)
        except Exception:
            continue

def scroll_to_bottom(page, scroll_pause_time=1.0, max_scrolls=20):
    """Scroll to bottom of page to load dynamic content."""
    for _ in range(max_scrolls):
        page.evaluate("window.scrollBy(0, window.innerHeight);")
        page.wait_for_timeout(int(scroll_pause_time * 1000))

def scrape_product_urls_from_html(html_content):
    """Extract product URLs from the given HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    product_grid = soup.find("div", {"id": "searchResults"})
    if not product_grid:
        logging.warning("No product grid found on the page.")
        return []

    product_containers = product_grid.find_all("div", class_=lambda x: x and "product-card-module" in x)
    urls = []
    for container in product_containers:
        a_tag = container.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            if not href.startswith("http"):
                href = BASE_URL + href
            urls.append(href)
    return urls

def scrape_paginated(base_category_url, page, country="US"):
    all_urls = set()

    # First page
    logging.info(f"Loading first page: {base_category_url}")
    page.goto(base_category_url, wait_until="domcontentloaded", timeout=70000)
    page.wait_for_timeout(2000)
    handle_popups(page)

    scroll_to_bottom(page)
    page.wait_for_timeout(2000)

    html_content = page.content()
    urls = scrape_product_urls_from_html(html_content)
    if not urls:
        logging.warning("No products found on the first page.")
    else:
        all_urls.update(urls)
        logging.info(f"Found {len(urls)} products on the first page.")

    # Pagination
    page_number = 1
    while True:
        paginated_url = f"{base_category_url}?country={country}&page={page_number}"

        if paginated_url == base_category_url or paginated_url == f"{base_category_url}?country={country}":
            page_number += 1
            continue

        logging.info(f"Loading paginated URL: {paginated_url}")
        try:
            page.goto(paginated_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            handle_popups(page)
        except TimeoutError:
            logging.warning(f"Timeout loading page {page_number}. Stopping pagination.")
            break

        html_content = page.content()
        urls = scrape_product_urls_from_html(html_content)
        if not urls:
            logging.info(f"No products found on page {page_number}. Assuming last page reached.")
            break

        all_urls.update(urls)
        logging.info(f"Page {page_number}: Found {len(urls)} products, total {len(all_urls)}.")
        page_number += 1

    return list(all_urls)

def main():
    today_str = date.today().strftime("%Y-%m-%d")
    base_dir = os.path.join(COUNTRY, "Data", today_str, "Item_urls")
    os.makedirs(base_dir, exist_ok=True)

    input_file = os.path.join(base_dir, f"{COUNTRY}_category_urls.json")
    output_file = os.path.join(base_dir, f"{COUNTRY}_product_urls.json")

    if not os.path.exists(input_file):
        logging.error(f"Category URL file not found: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        category_data = json.load(f)

    # Load existing progress if available
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            result_json = json.load(f)
        logging.info(f"Resuming from existing progress file: {output_file}")
    else:
        result_json = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context()
        page = context.new_page()

        for gender, categories in category_data.items():
            if gender not in result_json:
                result_json[gender] = {}

            for category_name, url in categories.items():
                if category_name in result_json[gender]:
                    logging.info(f"Skipping already scraped: [{gender}] - {category_name}")
                    continue

                logging.info(f"Scraping [{gender}] - {category_name}")
                urls = scrape_paginated(url, page, country="US")
                result_json[gender][category_name] = urls

                # Save progress after each category
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result_json, f, indent=4, ensure_ascii=False)
                logging.info(f"Saved progress after [{gender}] - {category_name}")

        browser.close()

    print(f" All product URLs saved to: {output_file}")

if __name__ == "__main__":
    main()
