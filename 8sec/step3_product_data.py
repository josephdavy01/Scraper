import json
import os
import re
from datetime import datetime
from threading import Thread
from playwright.sync_api import sync_playwright, TimeoutError


def set_korea_krw(page):
    try:
        page.click('div.flag-wrap[data-gpid="countrySelect"]', timeout=5000)
    except TimeoutError:
        pass
    try:
        page.wait_for_selector("select[name='country']", timeout=5000)
        page.select_option("select[name='country']", value="KR")
    except TimeoutError:
        pass
    try:
        page.wait_for_selector("select[name='currency']", timeout=5000)
        page.select_option("select[name='currency']", value="KRW")
    except TimeoutError:
        pass
    try:
        page.click("button:has-text('Apply'), button:has-text('Save')", timeout=2000)
        page.wait_for_load_state("domcontentloaded")
    except TimeoutError:
        pass


def extract_product_id(url):
    m = re.search(r'/p/(\d+)', url)
    return m.group(1) if m else None


def scrape_product_details(page, product_url, output_dir, save_path, gender):
    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        set_korea_krw(page)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"⚠️ Failed to load {product_url}: {e}")
        return

    product_json = {}

    product_id = extract_product_id(product_url)
    product_json["product_id"] = product_id

    try:
        script_handle = page.query_selector('script#eci-product[type="application/ld+json"]')
        if script_handle:
            json_text = script_handle.inner_text()
            product_json.update(json.loads(json_text))
    except Exception:
        pass

    colors, sizes = [], []
    try:
        for elem in page.query_selector_all('div.pd-color li.os-opt'):
            label = elem.query_selector('span.lab')
            if label:
                colors.append(label.inner_text().strip())
        for elem in page.query_selector_all('div.pd-size li.os-opt'):
            label = elem.query_selector('span.lab')
            if label:
                sizes.append(label.inner_text().strip())
    except Exception:
        pass

    prices, currency_code = {}, None
    currency_map = {"₩": "KRW", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
    try:
        sale_elem = page.query_selector("div.sale-price")
        default_elem = page.query_selector("div.default-price")
        percent_elem = page.query_selector("div.percent-off span.number")

        def parse_price(elem):
            nonlocal currency_code
            if not elem:
                return None
            cur = elem.query_selector("span.currency")
            num = elem.query_selector("span.number")
            if not num:
                return None
            if cur and not currency_code:
                cur_symbol = cur.inner_text().strip()
                currency_code = currency_map.get(cur_symbol, cur_symbol)
            return num.inner_text().strip()

        sale_price = parse_price(sale_elem)
        default_price = parse_price(default_elem)
        if sale_price:
            prices["sale_price"] = sale_price
        if default_price:
            prices["default_price"] = default_price
        if percent_elem:
            prices["percent_off"] = percent_elem.inner_text().strip() + "%"
    except Exception:
        pass

    images = []
    try:
        seen = set()
        for img in page.query_selector_all("div.pd-thumbs img[data-src]"):
            src = img.get_attribute("data-src")
            if src and src not in seen:
                seen.add(src)
                images.append(src)
    except Exception:
        pass

    product_json.update({
        "gender": gender,
        "currency": currency_code if currency_code else "",
        "available_colors": colors,
        "available_sizes": sizes,
        "prices": prices,
        "images": images,
    })

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(product_json, f, indent=2, ensure_ascii=False)
    print(f"Saved {save_path}")


def scrape_urls_in_browser_instance(gender, urls, output_dir):
    with sync_playwright() as p:
        # Launch separate Chrome browser instance using channel="chrome"
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_page()
        for url in urls:
            product_id = extract_product_id(url)
            if not product_id:
                print(f"⚠️ Could not extract product ID from {url}")
                continue
            save_path = os.path.join(output_dir, f"{product_id}.json")
            if os.path.exists(save_path):
                print(f" Skipping {product_id}, already exists")
                continue
            scrape_product_details(page, url, output_dir, save_path, gender)
        browser.close()


def scrape_all(urls_file, output_dir, instances=3):
    with open(urls_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "women" in data:
        gender = "women"
        urls = data["women"].get("clothing", [])
    elif "men" in data:
        gender = "men"
        urls = data["men"].get("clothing", [])
    else:
        gender = "unknown"
        urls = []

    os.makedirs(output_dir, exist_ok=True)

    # Divide URLs evenly per browser instance
    chunk_size = (len(urls) + instances - 1) // instances
    url_chunks = [urls[i * chunk_size:(i + 1) * chunk_size] for i in range(instances)]

    threads = []
    for i in range(instances):
        t = Thread(target=scrape_urls_in_browser_instance, args=(gender, url_chunks[i], output_dir))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


def main():
    today_str = datetime.today().strftime("%Y-%m-%d")
    # today_str="2025-12-09"
    women_urls_file = f"Korea/Data/{today_str}/Item_urls/women_product_urls.json"
    men_urls_file = f"Korea/Data/{today_str}/Item_urls/men_product_urls.json"

    women_output = f"Korea/Data/{today_str}/Json_data/women/clothing"
    men_output = f"Korea/Data/{today_str}/Json_data/men/clothing"

    # Launch multiple browser instances concurrently, 3 per gender
    threads = []

    t_women = Thread(target=scrape_all, args=(women_urls_file, women_output, 5))
    t_men = Thread(target=scrape_all, args=(men_urls_file, men_output, 5))

    t_women.start()
    t_men.start()

    threads.append(t_women)
    threads.append(t_men)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
