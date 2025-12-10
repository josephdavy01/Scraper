import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import date, datetime
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

# Save JSON with fallbacks
def save_json(gender, category, p_id, json_data, date_subfolder):
    json_file_path = date_subfolder / 'Json_data' / gender / category
    json_file_path.mkdir(parents=True, exist_ok=True)
    file_name = json_file_path / f'{p_id}.json'
    try:
        with open(file_name, 'w') as f:
            json.dump(json_data, f, indent=4)
    except Exception:
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
        except Exception:
            with open(file_name, 'w', encoding='utf-8', errors='surrogateescape') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)

def check_file(gender, category, name, date_subfolder):
    return os.path.exists(f'{date_subfolder}/Json_data/{gender}/{category}/{name}.json')

async def get_json(playwright, browser, c_dict, gender, category, plist, date_subfolder):
    storeId = c_dict['storeId']
    cid = c_dict['countryid']
    pdlist = []

    context = await browser.new_context()
    page = await context.new_page()

    for pid in tqdm_asyncio(plist, desc="Products", bar_format=bar_format, ascii=(' ', '*')):
        if not check_file(gender, category, pid, date_subfolder):
            url = f'https://www.stradivarius.com/itxrest/2/catalog/store/{storeId}/category/0/product/{pid}/detail?languageId=-1&appId=1'
            try:
                await page.goto(url)
                pre_tag = await page.locator("pre").text_content(timeout=10000)
                json_content = pre_tag.replace('null', 'None').replace('true', 'True').replace('false', 'False')
                json_data = eval(json_content)
                for i in json_data.get('bundleProductSummaries', [{}])[0].get('detail', {}).get('colors', []):
                    if json_data['id'] == i['catentryId']:
                        purl = f'https://www.stradivarius.com/{cid}/{json_data["name"].lower().replace("-", "").replace(" ", "-")}-l{json_data["bundleProductSummaries"][0]["detail"]["reference"].split("-")[0]}?cS={i["id"]}&pelement={i["catentryId"]}'
                        pdlist.append(purl)
                save_json(gender, category, pid, json_data, date_subfolder)
            except Exception as e:
                logging.error(f"Error processing the webpage for product {url}: {e}")

    await context.close()
    return pdlist

async def process_country(country, c_dict, today_str):
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)
    purl_list = []
    file_path = Path(f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_ids.json')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        with open(file_path) as json_file:
            pids_dict = json.load(json_file)

        for gender in tqdm_asyncio(pids_dict, desc="Genders", bar_format=bar_format, ascii=(' ', '*')):
            for category, plist in tqdm_asyncio(pids_dict[gender].items(), desc=f"{gender}", leave=False, bar_format=bar_format, ascii=(' ', '*')):
                logging.info(f'Now starting {gender} {category} products...')
                urls = await get_json(p, browser, c_dict, gender, category, plist, date_subfolder)
                purl_list.append({"category_name": gender, "subcategory": category, "urls": urls})
                logging.info(f'{gender} {category} section completed.')

        await browser.close()

    output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(f'{output_dir}/{country}_product_urls.json', "w", encoding='utf-8') as outfile:
        json.dump(purl_list, outfile, ensure_ascii=False, indent=4)

async def main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            "Canada": {"countryid": "ca", "storeId": "54009628/50331143"},
            "Saudi": {"countryid": "sa/en", "storeId": "55009580/50331096"},
            "Spain": {"countryid": "es/en", "storeId": "54009550/50109552"},
            "Turkey": {"countryid": "tr/en", "storeId": "54009571/50331081"}
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            "UAE": {"countryid": "ae", "storeId": "55009581/50331096"},
            "UK": {"countryid": "gb", "storeId": "54109556/50331064"},
            "USA": {"countryid": "us", "storeId": "54009627/50331143"}
        }
    else:
        countries = {}

    await asyncio.gather(*(process_country(country, c_dict, today_str) for country, c_dict in countries.items()))

if __name__ == "__main__":
    asyncio.run(main())