import json
import os
import threading
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

BASE_URL = "https://www.kooding.com"

# Output file paths
today_str = datetime.today().strftime("%Y-%m-%d")

women_urls_file = f"Korea/Data/{today_str}/Item_urls/women_product_urls.json"
men_urls_file = f"Korea/Data/{today_str}/Item_urls/men_product_urls.json"

# Thread-safe dictionary update
results = {}
lock = threading.Lock()


def set_korea_krw(page):
    try:
        page.click('div.flag-wrap[data-gpid="countrySelect"]', timeout=5000)
        print("Clicked flag/country selector")
    except TimeoutError:
        print("⚠️Flag selector not found, assuming already open or set")

    try:
        page.wait_for_selector("select[name='country']", timeout=5000)
        page.select_option("select[name='country']", value="KR")
        print(" Selected Korea as country")
    except TimeoutError:
        print("⚠️ Country dropdown not found, assuming already set")

    try:
        page.wait_for_selector("select[name='currency']", timeout=5000)
        page.select_option("select[name='currency']", value="KRW")
        print(" Selected KRW as currency")
    except TimeoutError:
        print("⚠️ Currency dropdown not found, assuming already set")

    try:
        page.click("button:has-text('Apply'), button:has-text('Save')", timeout=2000)
        page.wait_for_load_state("networkidle")
        print(" Clicked Apply/Save and waited for reload")
    except TimeoutError:
        print("⚠️ Apply/Save button not found or not needed")


def scrape_product_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    product_container = soup.select_one("div.products-wrapper.main")

    a_tags = product_container.select("div.product.real a[href]") if product_container else soup.select("div.product.real a[href]")

    for a_tag in a_tags:
        href = a_tag.get("href", "").strip()
        if href.startswith("/"):
            href = BASE_URL + href
        if href:
            links.append(href)

    return links


def scrape_category(category_tag_id, brand_category_id, category_name):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Change to headless=False if you want to see it
        page = browser.new_page()

        # Go to the base brand category page
        start_url = f"https://www.kooding.com/8seconds/b/1026?idCategory={brand_category_id}&curpagenum=1"
        page.goto(start_url, wait_until="networkidle")
        print(f"[{category_name}] Landed on brand category page: {start_url}")

        # Set country and currency
        set_korea_krw(page)

        # Click clothing category tab
        print(f"[{category_name}] Clicking Clothing category tag with data-id={category_tag_id}...")
        page.click(f'div.category-tag[data-id="{category_tag_id}"]')
        page.wait_for_load_state("networkidle")

        base_url = f"https://www.kooding.com/8seconds/b/1026?idCategory={category_tag_id}&curpagenum="
        all_products = []

        page_num = 1
        while True:
            url = base_url + str(page_num)
            print(f"[{category_name}] Visiting page {page_num}: {url}")
            page.goto(url, wait_until="networkidle")

            html = page.content()
            products = scrape_product_links(html)
            if not products:
                print(f"[{category_name}] No products found on page {page_num}, stopping.")
                break

            print(f"[{category_name}] Found {len(products)} products on page {page_num}")
            all_products.extend(products)
            page_num += 1

        browser.close()

        # Thread-safe result storage
        with lock:
            results[category_name] = all_products


def save_json_file(filepath, category_name, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({category_name: {"clothing": data}}, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(data)} items to {filepath}")


def main():
    threads = []

    # Thread for women clothing (tag=84, brand category=1)
    t1 = threading.Thread(target=scrape_category, args=(84, 1, "women"))
    threads.append(t1)

    # Thread for men clothing (tag=197, brand category=2)
    t2 = threading.Thread(target=scrape_category, args=(197, 2, "men"))
    threads.append(t2)

    # Start threads
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Save output
    save_json_file(women_urls_file, "women", results.get("women", []))
    save_json_file(men_urls_file, "men", results.get("men", []))


if __name__ == "__main__":
    main()
