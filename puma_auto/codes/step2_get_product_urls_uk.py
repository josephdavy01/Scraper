import os
import json
import asyncio
import logging
from datetime import date
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm_asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# pop_keys = ['accessories_socks', 'accessories_hats_and_caps', 'accessories_bags_and_backpacks', 'accessories_fitness_equipment', 'accessories_sale_accessories', 'boys_clothing_accessories', 'girls_clothing_accessories', 'running_running_accessories', 'training_training_accessories', 'motorsport_motorsport_accessories', 'football_football_equipment']
pop_keys = []

countries = {
    'UK': "https://uk.puma.com/uk/en"
}

async def get_product_urls(page, url, base_url):
    purls = []
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=50000)
        await asyncio.sleep(4)
        await page.wait_for_selector("li[data-test-id='product-list-item']", timeout=30000)

        previous_count = 0
        no_change_count = 0
        max_no_change = 5
        current_position = 0

        while no_change_count < max_no_change:
            current_position += 3
            await page.evaluate(f"""window.scrollTo(0, window.innerHeight * {current_position}); """)
            await asyncio.sleep(5)

            load_more_button = await page.query_selector("button[data-test-id='product-list-load-more']")
            if load_more_button:
                try:
                    await load_more_button.click()
                    await asyncio.sleep(5)
                except:
                    pass

            current_products = await page.query_selector_all("li[data-test-id='product-list-item']")
            current_count = len(current_products)
            logging.info(f'Products found after scroll: {current_count}')

            if current_count == previous_count:
                no_change_count += 1
            else:
                no_change_count = 0

            previous_count = current_count
            if current_count > 3000:
                logging.warning(f'Reached maximum product limit: {current_count}')
                break

        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        products = soup.find_all("li", attrs={"data-test-id": "product-list-item"})

        seen_urls = set()
        for product in products:
            link_element = product.find('a', attrs={"data-test-id": "product-list-item-link"})
            if link_element:
                href = link_element.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if full_url not in seen_urls:
                        purls.append(full_url)
                        seen_urls.add(full_url)

        logging.info(f'Total unique product URLs extracted: {len(purls)}')
        return purls

    except Exception as e:
        logging.error(f'Error in get_product_urls: {e}')
        return []


async def fetch_product_urls(playwright, semaphore, gender, category, url, country):
    async with semaphore:
        logging.info(f'[{gender} - {category}] Processing: {url}')
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox','--disable-images']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        base_url = countries[country]

        try:
            result = await get_product_urls(page, url, base_url)
        except Exception as e:
            logging.error(f'Error fetching {gender} - {category}: {e}')
            result = []
        finally:
            await page.close()
            await context.close()
            await browser.close()
            logging.info(f'[{gender} - {category}] Browser closed. URLs found: {len(result)}')

        return gender, category, result


async def process_country(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json'
    if not os.path.exists(read_file_path):
        logging.error(f"Category URL file not found: {read_file_path}")
        return

    with open(read_file_path, encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    output_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(output_dir, exist_ok=True)
    file_path = f'{output_dir}/{country}_product_urls.json'

    purl_list = {}
    semaphore = asyncio.Semaphore(2)

    async with async_playwright() as p:
        all_tasks = []
        for gender, categories in url_dict.items():
            for category, url in categories.items():
                if category in pop_keys:
                    logging.info(f'Skipping pop_key category: [{gender} - {category}] {url}')
                    continue
                
                if category == "shop_all" or category.endswith("_shop_all") or category.startswith("shop_all_"):
                    logging.info(f'Skipping shop_all URL: [{gender} - {category}] {url}')
                    continue
                
                all_tasks.append(fetch_product_urls(p, semaphore, gender, category, url, country))

        results = await tqdm_asyncio.gather(*all_tasks, desc=f"Fetching product URLs ({country})", total=len(all_tasks))

        for gender, category, links in results:
            if gender not in purl_list:
                purl_list[gender] = {}
            purl_list[gender][category] = links
            logging.info(f'Added {len(links)} URLs for {gender} - {category}')

    with open(file_path, "w", encoding='utf-8') as outfile:
        json.dump(purl_list, outfile, ensure_ascii=False, indent=2)

    total_urls = sum(len(categories[cat]) for categories in purl_list.values() for cat in categories)
    print(f'{country} product URLs fetched and saved to {file_path}')
    print(f'Total URLs extracted: {total_urls}')

    for gender, categories in purl_list.items():
        print(f'\n{gender}:')
        for category, urls in categories.items():
            print(f'  {category}: {len(urls)} URLs')


async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    await asyncio.gather(*(process_country(country, today_str) for country in countries.keys()))

if __name__ == "__main__":
    asyncio.run(main())