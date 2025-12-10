import os
import json
import html
import asyncio
import random
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.async_api import async_playwright

async def random_delay(min_seconds=2, max_seconds=5):
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)

async def manage_cookies(page):
    try:
        await page.wait_for_selector("button:has-text('Accept all cookies')", timeout=3000)
        await page.click("button:has-text('Accept all cookies')")
        print("Cookies accepted.")
    except:
        print("No cookie banner found.")

def read_json_urls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def scroll_page_to_load_products(page, max_scrolls=300000):
    print("Scrolling current page to load products...")
    last_height = await page.evaluate("document.body.scrollHeight")
    scroll_count = 0
    while scroll_count < max_scrolls:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await random_delay(2, 4)
        new_height = await page.evaluate("document.body.scrollHeight")
        scroll_count += 1
        if new_height == last_height:
            break
        last_height = new_height
    await page.evaluate("window.scrollTo(0, 0)")
    await random_delay(1, 2)
    print("Scrolling completed!")

def check_brand_exists(soup, brand_name):
    brand_lower = brand_name.lower()
    page_text = html.unescape(soup.get_text()).lower()
    if brand_lower in page_text:
        return True
    breadcrumbs = soup.find_all(['span', 'li'], {'class': lambda x: x and ('breadbox' in x or 'breadcrumb' in x)})
    for breadcrumb in breadcrumbs:
        title = breadcrumb.get('title', '')
        text = breadcrumb.get_text()
        if brand_lower in html.unescape(title).lower() or brand_lower in html.unescape(text).lower():
            return True
    product_cards = soup.find_all('div', {'class': 'product-card_rootBox__BcM9P'})
    for card in product_cards:
        if brand_lower in html.unescape(card.get_text()).lower():
            return True
    filters = soup.find_all(['label', 'div', 'span', 'li'], string=True)
    for filter_elem in filters:
        if filter_elem.string and brand_lower in html.unescape(filter_elem.string).lower():
            return True
    return False

async def scrape_uk_products(page, category_data, output_file):
    results = {}
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                results = json.load(f)
            except:
                results = {}
    for gender, brands in category_data.items():
        if gender not in results:
            results[gender] = {}
        for brand_name, all_categories in brands.items():
            for subcategory, url in all_categories.items():
                key = f"{brand_name}_{subcategory}"
                if key in results[gender]:
                    print(f"Skipping {gender} -> {brand_name} -> {subcategory}, already scraped.")
                    continue
                print(f"[UK] {gender} -> {brand_name} -> {subcategory}")
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await manage_cookies(page)
                    await random_delay(3, 6)
                    soup = BeautifulSoup(await page.content(), 'html.parser')
                    if not check_brand_exists(soup, brand_name):
                        print(f"Brand '{brand_name}' not found on page. Skipping.")
                        continue
                    all_links = []
                    page_num = 1
                    while True:
                        await scroll_page_to_load_products(page)
                        await manage_cookies(page)
                        soup = BeautifulSoup(await page.content(), 'html.parser')
                        for card in soup.find_all('div', {'class': 'product-card_rootBox__BcM9P'}):
                            a_tag = card.find('a', {'class': 'product-card_cardWrapper__GVSTY'})
                            if a_tag:
                                link = a_tag['href']
                                if not link.startswith('http'):
                                    link = 'https://www.marksandspencer.com' + link
                                all_links.append(link)
                        try:
                            next_button = await page.query_selector(
                                "//a[@aria-label='Next page' and @class='pagination_trigger__YEwyN']"
                            )
                            if next_button:
                                await next_button.click()
                                page_num += 1
                                print(f"Moving to page {page_num}...")
                                await random_delay(4, 7)
                                await manage_cookies(page)
                            else:
                                print(f"No more pages after {page_num}.")
                                break
                        except:
                            print("Next button not found or error during pagination.")
                            break
                    results[gender][key] = list(set(all_links))
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=4)
                    print(f"Saved {len(all_links)} URLs for {gender} -> {brand_name} -> {subcategory}")
                except Exception as e:
                    print(f"Error processing {gender} -> {brand_name} -> {subcategory}: {e}")
                    continue
    return results

async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    file_path = f"UK/Data/{today}/Item_urls/Brand_name_product_url.json"
    output_file = os.path.join(os.path.dirname(file_path), "UK_product_urls.json")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    category_data = read_json_urls(file_path)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        results = await scrape_uk_products(page, category_data, output_file)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"Finished scraping. Final data saved to: {output_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
