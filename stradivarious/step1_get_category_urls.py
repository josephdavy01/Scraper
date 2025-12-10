import os
import json
import logging
import asyncio
from datetime import date, datetime
from playwright.async_api import async_playwright

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Country setup
if day in ['Monday', 'Wednesday', 'Friday']:
    countries = {
        'Canada': {'storeId': '54009628/50331143', 'initial': 'https://www.stradivarius.com/ca/'},
        'Saudi': {'storeId': '55009580/50331096', 'initial': 'https://www.stradivarius.com/sa/en/'},
        'Spain': {'storeId': '54009550/50109552', 'initial': 'https://www.stradivarius.com/es/en/'},
        'Turkey': {'storeId': '54009571/50331081', 'initial': 'https://www.stradivarius.com/tr/en/'}
    }
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = {
        'UAE': {'storeId': '55009581/50331096', 'initial': 'https://www.stradivarius.com/ae/'},
        'UK': {'storeId': '54109556/50331064', 'initial': 'https://www.stradivarius.com/gb/'},
        'USA': {'storeId': '54009627/50331143', 'initial': 'https://www.stradivarius.com/us/'}
    }
else:
    countries = {}

async def get_category_ids(page, country, storeId):
    if not storeId:
        logging.warning(f"No storeId for {country}")
        return None

    url = f'https://www.stradivarius.com/itxrest/2/catalog/store/{storeId}/category?languageId=-1&typeCatalog=1&appId=1'
    await page.goto(url)
    
    try:
        pre = await page.wait_for_selector('pre', timeout=10000)
        content = await pre.inner_text()
        return json.loads(content)
    except Exception as e:
        logging.error(f"Error getting category for {country}: {e}")
        return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        for country, cdict in countries.items():
            logging.info(f"Fetching {country} category URLs...")
            json_data = await get_category_ids(page, country, cdict['storeId'])

            if json_data is None:
                continue

            temp_json = {}

            categories = json_data.get('categories', [])
            if not categories:
                continue

            for i in categories[0].get('subcategories', []):
                nameEn = i.get('nameEn', '')
                if nameEn in ['Clothing', 'STR Teen']:
                    gender = 'Women' if nameEn == 'Clothing' else 'Teen'
                    temp_json.setdefault(gender, {})

                    sub_subs = i.get('subcategories', [])
                    if sub_subs:
                        for j in sub_subs[0].get('subcategories', []):
                            name = j.get('nameEn', '').lower().replace(' ', '-')
                            url_part = j.get('categoryUrl')
                            if url_part:
                                cid = j.get('viewCategoryId') or j.get('id')
                                full_url = f"{cdict['initial']}{url_part}"
                                temp_json[gender][name] = {'cid': cid, 'url': full_url}

                elif nameEn in ['Part Sale', 'Sale']:
                    for sale_sub in i.get('subcategories', []):
                        if sale_sub.get('nameEn') == 'Clothing':
                            gender = 'Women'
                            sub_subs = sale_sub.get('subcategories', [])
                            if sub_subs:
                                for k in sub_subs[0].get('subcategories', []):
                                    name = f"sale-{k.get('nameEn', '').lower().replace(' ', '-')}"
                                    url_part = k.get('categoryUrl')
                                    if url_part:
                                        cid = k.get('viewCategoryId') or k.get('id')
                                        full_url = f"{cdict['initial']}{url_part}"
                                        temp_json.setdefault(gender, {})[name] = {'cid': cid, 'url': full_url}

                elif nameEn in ['LAST PRICES']:
                    for sale_sub in i.get('subcategories', []):
                        if sale_sub.get('nameEn') == 'Clothing':
                            gender = 'Women'
                            sub_subs = sale_sub.get('subcategories', [])
                            if sub_subs:
                                for k in sub_subs[0].get('subcategories', []):
                                    name = f"last-{k.get('nameEn', '').lower().replace(' ', '-')}"
                                    url_part = k.get('categoryUrl')
                                    if url_part:
                                        cid = k.get('viewCategoryId') or k.get('id')
                                        full_url = f"{cdict['initial']}{url_part}"
                                        temp_json.setdefault(gender, {})[name] = {'cid': cid, 'url': full_url}
                
                elif nameEn in ['Just In']:
                    for sale_sub in i.get('subcategories', []):
                        if sale_sub.get('nameEn') == 'Clothing':
                            gender = 'Women'
                            sub_subs = sale_sub.get('subcategories', [])
                            if sub_subs:
                                for k in sub_subs[0].get('subcategories', []):
                                    name = f"new-{k.get('nameEn', '').lower().replace(' ', '-')}"
                                    url_part = k.get('categoryUrl')
                                    if url_part:
                                        cid = k.get('viewCategoryId') or k.get('id')
                                        full_url = f"{cdict['initial']}{url_part}"
                                        temp_json.setdefault(gender, {})[name] = {'cid': cid, 'url': full_url}

            output_path = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_path, exist_ok=True)
            output_file = f'{output_path}/{country}_category_urls.json'
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(temp_json, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved category URLs for {country} to {output_file}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())