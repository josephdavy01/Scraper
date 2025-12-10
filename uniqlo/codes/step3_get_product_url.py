import os
import json
import time
from datetime import date, datetime
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from multiprocessing import Process

today = date.today().strftime("%Y-%m-%d")

def normalize_product_url(href: str, referer_url: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        parsed = urlparse(referer_url)
        return f"{parsed.scheme}:{href}"
    if href.startswith("http://") or href.startswith("https://"):
        return href
    parsed = urlparse(referer_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(origin, href)

def accept_cookies(page):
    try:
        print("Waiting for cookies popup...")
        page.wait_for_selector("button#onetrust-accept-btn-handler", timeout=15000)
        page.click("button#onetrust-accept-btn-handler")
        print("Cookies accepted")
    except PlaywrightTimeoutError:
        print("No cookies popup found")

def slow_two_pass_scroll(page, step=800, delay_ms=2000, max_rounds=200, stable_checks=3, wait_for_selector=None):
    if wait_for_selector:
        try:
            page.wait_for_selector(wait_for_selector, timeout=10000)
            print(f"Found product container selector: {wait_for_selector}")
        except PlaywrightTimeoutError:
            print(f"Product container {wait_for_selector} not found before scroll — continuing anyway.")

    selector = "div.fr-ec-product-collection a[href]"
    prod_locator = page.locator(selector)
    def get_count():
        try:
            return prod_locator.count()
        except Exception:
            return 0
    print("Starting scroll (incremental, 1s between steps)...")
    prev_count = -1
    stable = 0
    rounds = 0
    while rounds < max_rounds:
        page.evaluate(f"window.scrollBy(0, {step});")
        page.wait_for_timeout(delay_ms)
        rounds += 1
        count = get_count()
        print(f"  Scroll {rounds}: {count} products visible")
        if count == prev_count:
            stable += 1
        else:
            stable = 0
        prev_count = count
        at_bottom = page.evaluate("window.innerHeight + window.scrollY >= document.body.scrollHeight - 50")
        if at_bottom and stable >= stable_checks:
            print(f"Scroll finished: reached bottom and stable ({count} products).")
            break
    page.wait_for_timeout(1000)
    print("Scrolling complete.")

def scrape_products(page, category_url: str, base_url: str, geo: str, category_name: str):
    print(f"   → Scraping category: {category_url} for {geo.upper()} ({category_name})")
    try:
        page.goto(category_url, timeout=60000)
        page.wait_for_timeout(1000)
        accept_cookies(page)

        probable_container_selectors = [
            "div.fr-ec-product-collection",
            "div.product-collection",
            "div.ec-product-tile",
            "div.ec-product-tile__link"
        ]
        wait_selector = None
        for s in probable_container_selectors:
            try:
                if page.query_selector(s):
                    wait_selector = s
                    break
            except Exception:
                continue

        slow_two_pass_scroll(page, step=800, delay_ms=2000, max_rounds=200, stable_checks=3, wait_for_selector=wait_selector)

        # KEEP duplicates and original order
        product_urls = []

        # 1) AU/CA structure
        if geo in ["canada", "australia"]:
            print("  → Using AU/CA selectors for product tiles.")
            els = page.query_selector_all("div.ec-product-tile a.ec-product-tile__link[href]")
            print(f"  → Found {len(els)} ec-product-tile links.")
            for el in els:
                href = el.get_attribute("href")
                if href:
                    product_urls.append(normalize_product_url(href, category_url))
            if not product_urls:
                alt = page.query_selector_all("a[href*='/products/']")
                print(f"  → AU/CA fallback found {len(alt)} links containing /products/.")
                for el in alt:
                    href = el.get_attribute("href")
                    if href and "/products/" in href:
                        product_urls.append(normalize_product_url(href, category_url))

        # 2) Single-grid fr-ec-product-collection
        if not product_urls:
            container = page.query_selector("div.fr-ec-product-collection")
            if container:
                candidates = container.query_selector_all(
                    "a.link.ito-padding-horizontal-0.ito-padding-vertical-0.ec-link.product-tile__link, a.ec-link.product-tile__link, a.product-tile__link"
                )
                print(f"  → fr-ec-product-collection present, found {len(candidates)} product links inside it.")
                for el in candidates:
                    href = el.get_attribute("href")
                    if href:
                        product_urls.append(normalize_product_url(href, category_url))

        # 3) Nested product-collection blocks
        if not product_urls:
            product_collection_blocks = page.query_selector_all("div.product-collection, div.product-collection--type-grid")
            found_count = 0
            for block in product_collection_blocks:
                verticals = block.query_selector_all("[variant='vertical'] a.link.ito-padding-horizontal-0.ito-padding-vertical-0.ec-link.product-tile__link, [variant='vertical'] a.product-tile__link")
                if verticals:
                    found_count += len(verticals)
                    for el in verticals:
                        href = el.get_attribute("href")
                        if href:
                            product_urls.append(normalize_product_url(href, category_url))
                else:
                    fallback_tiles = block.query_selector_all("a.link.ito-padding-horizontal-0.ito-padding-vertical-0.ec-link.product-tile__link, a.product-tile__link")
                    if fallback_tiles:
                        found_count += len(fallback_tiles)
                        for el in fallback_tiles:
                            href = el.get_attribute("href")
                            if href:
                                product_urls.append(normalize_product_url(href, category_url))
            if found_count:
                print(f"  → product-collection parsing found {found_count} links.")

        # 4) Additional nested path
        if not product_urls:
            try:
                nested_candidates = page.query_selector_all(
                    "div.layout-container.layout div[data-testid='ITOLayout'] div.contentsCard div[id^='feature_'] a.product-tile__link, "
                    "div.layout-container div.contentsCard a.product-tile__link"
                )
                print(f"  → Nested layout search found {len(nested_candidates)} links.")
                for el in nested_candidates:
                    href = el.get_attribute("href")
                    if href:
                        product_urls.append(normalize_product_url(href, category_url))
            except Exception as e_nested:
                print("  → Nested layout search error:", e_nested)

        # 5) Generic fallback
        if not product_urls:
            print("  → Using generic fallback")
            generic = page.query_selector_all("a[href*='/products/'], a[href*='/product/'], a.product-tile__link")
            print(f"  → Generic fallback found {len(generic)} anchors.")
            for el in generic:
                href = el.get_attribute("href")
                if href:
                    product_urls.append(normalize_product_url(href, category_url))

        result = [u for u in product_urls if u]
        print(f"Found {len(result)} products for category {category_name}")
        return result
    except Exception as e:
        print(f"Error scraping {category_url} for {geo.upper()} ({category_name}): {str(e)}")
        return []

def safe_load_json(path):
    """Load JSON, if it's corrupt rename and return None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        ts = int(time.time())
        corrupt_name = f"{path}.corrupt.{ts}"
        try:
            os.replace(path, corrupt_name)
            print(f"Warning: JSON decode failed for {path}. Renamed to {corrupt_name} and starting fresh.")
        except Exception as ex:
            print(f"Warning: failed to rename corrupt file {path}: {ex}")
        return None
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
        return None

def atomic_write_json(path, obj):
    """Write JSON atomically via tmp file and os.replace."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as e:
        print(f"Error writing {path} atomically: {e}")
        # cleanup tmp if exists
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise

def scrape_geo(geo: str):
    with sync_playwright() as p:
        print(f"\nStarting browser for {geo.upper()}")
        browser = p.chromium.launch(headless=False)

        base_url = f"https://www.uniqlo.com/{geo}/en/"
        category_file = os.path.join(geo, "data", today, "Item_urls", "category_url.json")

        if not os.path.exists(category_file):
            print(f"No category file found for {geo} at {category_file}")
            browser.close()
            return

        with open(category_file, "r", encoding="utf-8") as f:
            categories = json.load(f)

        page = browser.new_page()

        output_dir = os.path.join(geo, "data", today, "Item_urls")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "product_urls.json")

        # Load previous progress if exists (resume support) with recovery
        all_products = None
        if os.path.exists(output_file):
            loaded = safe_load_json(output_file)
            if loaded is None:
                # corrupted or unreadable => start fresh
                all_products = {"women": {}, "men": {}, "kids": {}, "baby": {}}
            else:
                all_products = loaded
        else:
            all_products = {"women": {}, "men": {}, "kids": {}, "baby": {}}

        for gender, cat_dict in categories.items():
            for cat_name, cat_url in cat_dict.items():
                print(f"\n==== Scraping → {geo.upper()} / {gender} / {cat_name} ====")
                product_urls = scrape_products(page, cat_url, base_url, geo, cat_name)
                product_urls = [u for u in product_urls if u]  # keep duplicates & order
                all_products.setdefault(gender, {})[cat_name] = product_urls

                # SAVE IMMEDIATELY to the common file (atomic)
                try:
                    atomic_write_json(output_file, all_products)
                    print(f"✔ Saved progress → {output_file} ({len(product_urls)} URLs)")
                except Exception as e:
                    print(f"Failed to save progress to {output_file}: {e}")

        page.close()
        browser.close()
        print(f"Finished scraping for {geo.upper()}")

def main():
    day = datetime.today().strftime('%A')
    if day in ["Monday", "Wednesday", "Friday"]:
        geos = ["uk", "usa", "india"]      # india included here
    elif day in ["Tuesday", "Thursday", "Saturday"]:
        geos = ["canada", "spain", "australia"]
    else:
        print(f"Today is {day}. No scraping scheduled.")
        return

    processes = []
    for geo in geos:
        p = Process(target=scrape_geo, args=(geo,))
        processes.append(p)
        p.start()
    for p in processes:
        p.join()
    print("All geographies processed.")

if __name__ == "__main__":
    main()
