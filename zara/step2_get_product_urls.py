import json
import asyncio
import logging
from pathlib import Path
from datetime import date, datetime
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def get_category_ids(page, code, cid):
    url = f'https://www.zara.com/{code}/en/category/{cid}/products?ajax=true'
    try:
        await page.goto(url,wait_until='domcontentloaded',)
        await page.wait_for_selector("pre", timeout=20000)
        json_content = await page.locator("pre").inner_text()
        json_data = json.loads(json_content)
        return json_data
    except Exception as e:
        logging.error(f"Failed to fetch data for category ID {cid} in {code}: {e}")
        return None

async def get_category_urls(page, country, today_str, code, cid):
    url_output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
    url_output_dir.mkdir(parents=True, exist_ok=True)

    json_data = await get_category_ids(page, code, cid)
    tset = set()

    if json_data:
        for i in json_data['productGroups']:
            for j in i['elements']:
                if 'commercialComponents' in j.keys():
                    if 'seo' in j['commercialComponents'][0].keys():
                        name = j['commercialComponents'][0]['seo']['keyword']
                        pid = j['commercialComponents'][0]['seo']['seoProductId'] 
                        if pid and 'M' not in pid and 'T' not in pid:
                            url = f'https://www.zara.com/{code}/en/{name}-p{pid}.html'
                            tset.add(url)
    else:
        logging.warning(f"No product groups found for category ID {cid} in {code}.")

    return list(tset)

async def fetch_country_data(playwright, country, code, today_str):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    logging.info(f'Fetching {country} products now...')
    try:
        with open(f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json', "r", encoding="utf-8") as json_file:
            cids_dict = json.load(json_file)
    except FileNotFoundError:
        logging.error(f"File not found: {country}/Data/{today_str}/Item_urls/{country}_category_urls.json")
        await browser.close()
        return

    p_dict = {}

    for gender, categories in cids_dict.items():
        p_dict[gender] = {}
        for category, cjson in categories.items():
            logging.info(f'Fetching {country} {gender} {category} products now...')
            try:
                p_dict[gender][category] = await get_category_urls(page, country, today_str, code, cjson['id'])
                logging.info(f'{country} {gender} {category} products fetched and saved.')
            except Exception as e:
                logging.error(f"Error fetching URLs for {country} {gender} {category}: {e}")

    # Save data
    output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = f'{output_dir}/{country}_product_urls.json'
    with open(output_path, "w", encoding='utf-8') as outfile:
        json.dump(p_dict, outfile, ensure_ascii=False, indent=4)

    logging.info(f'{country} products fetched and saved to {output_path}')
    await browser.close()


async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            'Australia': 'au',
            'Canada': 'ca',
            'India': 'in',
            'Saudi': 'sa',
            'Spain': 'es'
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            'Turkey': 'tr',
            'UAE': 'ae',
            'UK': 'uk',
            'USA': 'us'
        }
    else:
        countries = {}

    async with async_playwright() as playwright:
        tasks = [
            fetch_country_data(playwright, country, code, today_str)
            for country, code in countries.items()
        ]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())