import os
import json
import asyncio
import logging
from datetime import date, datetime
from playwright.async_api import async_playwright

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

pop_key = ['view-all', 'gift-card', 'join-life', '+-info', 'careers', 'stores', 'home']

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

async def get_category_ids(page, country, cid):
    url = f'https://www.zara.com/{cid}/en/categories?ajax=true'
    await page.goto(url)

    try:
        content = await page.text_content("pre")
        json_data = json.loads(content)
        return json_data
    except Exception as e:
        logging.error(f"Error processing the webpage for category in {country}: {e}")
        return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        for country, cid in countries.items():
            logging.info(f'Fetching {country} category URLs now...')
            json_data = await get_category_ids(page, country, cid)

            if json_data is None:
                continue

            temp_json = {}

            for i in json_data['categories']:
                if i['name'] in ['WOMAN', 'MAN']:
                    temp_json[i['name']] = {}
                    for j in i['subcategories']:
                        category_name = j['name']
                        category_prefix = ''
                        if category_name == 'SALE':
                            category_prefix = 'sale_'
                        elif category_name == 'PART SALE':
                            category_prefix = 'sale_'
                        elif category_name == 'NEW COLLECTION':
                            category_prefix = 'new_'
                        elif category_name == 'SPECIAL PROMOTION':
                            category_prefix = 'special_'

                        if category_prefix:
                            for k in j['subcategories']:
                                name = k['name'].lower().replace('|', '&').replace(' ', '-')
                                id_ = k.get('redirectCategoryId', k.get('id'))
                                if k.get('seo'):
                                    url = f"https://www.zara.com/{cid}/en/{k['seo']['keyword']}-l{k['seo']['seoCategoryId']}.html?v1={id_}"
                                    temp_json[i['name']][category_prefix + name] = {'id': id_, 'url': url}
                        else:
                            name = j['name'].lower().replace('|', '&').replace(' ', '-')
                            id_ = j.get('redirectCategoryId', j.get('id'))
                            if j.get('seo'):
                                if j.get('seo').get('keyword'):
                                    url = f"https://www.zara.com/{cid}/en/{j['seo']['keyword']}-l{j['seo']['seoCategoryId']}.html?v1={id_}"
                                    temp_json[i['name']][name] = {'id': id_, 'url': url}
                                else:
                                    url = ""
                                    temp_json[i['name']][name] = {'id': id_, 'url': url}

                elif i['name'] == 'KIDS':
                    temp_json[i['name']] = {}
                    for j in i['subcategories']:
                        group_name = j['name']
                        if group_name in ['1½ - 6 YEARS', '1½  - 6 YEARS', '6 - 14 YEARS', '0 - 6 MONTHS', '6 - 18 MONTHS', '1 - 6 YEARS', '6 - 14 years', '0 - 18 MONTHS']:
                            for k in j['subcategories']:
                                name = f"{j['seo']['keyword']}_{k['name'].lower().replace('|', '&').replace(' ', '-')}"
                                id_ = k.get('redirectCategoryId', k.get('id'))
                                if k.get('seo'):
                                    if k.get('seo').get('keyword'):
                                        url = f"https://www.zara.com/{cid}/en/{k['seo']['keyword']}-l{k['seo']['seoCategoryId']}.html?v1={id_}"
                                        temp_json[i['name']][name] = {'id': id_, 'url': url}
                                    else:
                                            url = ""
                                            temp_json[i['name']][name] = {'id': id_, 'url': url}

                        elif group_name in ['SALE', 'PART SALE', 'NEW COLLECTION', 'SPECIAL PROMOTION']:
                            prefix = {
                                'SALE': 'sale_',
                                'PART SALE': 'sale_',
                                'NEW COLLECTION': 'new_',
                                'SPECIAL PROMOTION': 'special_'
                            }[group_name]

                            for k in j['subcategories']:
                                name = f"{j['seo']['keyword']}_{k['name'].lower().replace('|', '&').replace(' ', '-')}"
                                if k['subcategories']:
                                    for l in k['subcategories']:
                                        if l.get('seo'):
                                            if l.get('seo').get('keyword'):
                                                name = l['seo']['keyword']
                                                id_ = l.get('redirectCategoryId', l.get('id'))
                                                url = f"https://www.zara.com/{cid}/en/{l['seo']['keyword']}-l{l['seo']['seoCategoryId']}.html?v1={id_}"
                                                temp_json[i['name']][prefix + name] = {'id': id_, 'url': url}
                                            else:
                                                id_ = l.get('redirectCategoryId', l.get('id'))
                                                url = f""
                                                temp_json[i['name']][prefix + name] = {'id': id_, 'url': url}

                                                

            output_path = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(output_path, exist_ok=True)
            output_file = f'{output_path}/{country}_category_urls.json'
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(temp_json, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved category URLs for {country} to {output_file}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
