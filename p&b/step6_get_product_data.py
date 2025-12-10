import os
import json
import asyncio
from tqdm import tqdm
from pathlib import Path
from datetime import date, datetime
from playwright.async_api import async_playwright

bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"

def save_json(gender, category, p_id, json_data, date_subfolder):
    json_file_path = date_subfolder / 'Json_data' / gender / category
    json_file_path.mkdir(parents=True, exist_ok=True)
    file_name = json_file_path / f'{p_id}.json'
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as final_error:
        tqdm.write(f"[ERROR] Failed to save JSON for {p_id}: {final_error}")

def check_file(gender, category, name, date_subfolder):
    file_path = Path(date_subfolder) / 'Json_data' / gender / category / f"{name}.json"
    return os.path.exists(file_path)

async def get_json(page, country, c_dict, gender, category, plist, date_subfolder):
    storeId = c_dict['storeId']
    cid = c_dict['countryid']
    pdlist = []

    with tqdm(total=len(plist), desc=f"{country}-{gender}-{category}", leave=False, bar_format=bar_format, ascii=(" ", "*")) as pbar:
        for pid in plist:
            if check_file(gender, category, pid, date_subfolder):
                pbar.update(1)
                continue

            url = f'https://www.pullandbear.com/itxrest/2/catalog/store/{storeId}/category/0/product/{pid}/detail?languageId=-1&appId=1'
            if country == 'USA':
                url = f'https://www.pullandbear.com/itxrest/2/catalog/store/{storeId}/category/0/product/{pid}/detail?languageId=-15&appId=1'

            try:
                response = await page.goto(url, timeout=20000)
                if response is None:
                    raise Exception("No response received")

                try:
                    json_data = await response.json()
                except Exception as je:
                    text = await response.text()
                    tqdm.write(f"[ERROR] JSON decode failed for {pid}: {je} | Response: {text}")
                    continue

                for i in json_data.get('bundleProductSummaries', [{}])[0].get('detail', {}).get('colors', []):
                    if json_data['id'] == i['catentryId']:
                        purl = f'https://www.pullandbear.com/{cid}/{json_data["name"].lower().replace("-","").replace(" ","-")}-l{json_data["bundleProductSummaries"][0]["detail"]["reference"].split("-")[0]}?cS={i["id"]}&pelement={i["catentryId"]}'
                        pdlist.append(purl)

                save_json(gender, category, pid, json_data, date_subfolder)

            except Exception as e:
                tqdm.write(f"[ERROR] Failed to fetch product {pid}: {e}")
            pbar.update(1)

    return pdlist

async def process_country(playwright, country, c_dict, date_subfolder):
    tqdm.write(f"[START] Processing {country}")

    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    purl_list = []

    try:
        file_path = Path(f'{country}/Data/{date_subfolder.name}/Item_urls/{country}_unique_product_ids.json')
        with open(file_path, 'r', encoding='utf-8') as json_file:
            pids_dict = json.load(json_file)

        for gender in tqdm(pids_dict, desc=f"{country} - Genders", leave=False, bar_format=bar_format, ascii=(" ", "*")):
            for category, plist in pids_dict[gender].items():
                tqdm.write(f"[INFO] {country}: {gender} {category}")
                urls = await get_json(page, country, c_dict, gender, category, plist, date_subfolder)
                purl_list.append({
                    "category_name": gender,
                    "subcategory": category,
                    "urls": urls
                })
                tqdm.write(f"[DONE] {country}: {gender} {category}")

        output_dir = Path(f'{country}/Data/{date_subfolder.name}/Item_urls')
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / f'{country}_product_urls.json', "w", encoding='utf-8') as outfile:
            json.dump(purl_list, outfile, ensure_ascii=False, indent=4)

    except Exception as e:
        tqdm.write(f"[ERROR] Error in {country}: {e}")
    finally:
        await browser.close()

async def run():
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = {
            "Australia": {"countryid": "au", "storeId": "24009414/20309455"},
            "Saudi": {"countryid": "sa/en", "storeId": "25009530/20309454"},
            "Spain": {"countryid": "es/en", "storeId": "24009400/20309449"},
            "Turkey": {"countryid": "tr/en", "storeId": "25009521/20309457"}
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = {
            "UAE": {"countryid": "ae", "storeId": "25009531/20309454"},
            "UK": {"countryid": "gb", "storeId": "24009406/20309455"},
            "USA": {"countryid": "us", "storeId": "24009477/20309455"}
        }
    else:
        tqdm.write("[SKIP] No country scheduled for today.")
        return

    async with async_playwright() as playwright:
        tasks = []

        for country, c_dict in countries.items():
            date_subfolder = Path(country) / 'Data' / today_str
            tasks.append(process_country(playwright, country, c_dict, date_subfolder))

        await asyncio.gather(*tasks)

# Run the script
asyncio.run(run())
