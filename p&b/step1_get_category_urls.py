import os
import json
import logging
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# GUI setup
root = tk.Tk()
root.withdraw()

# Date info
dt = datetime.now()
today_str = dt.strftime('%Y-%m-%d')
day = dt.strftime('%A')

# Define keywords to skip
pop_key = []

# Save data
def save_json(data, country):
    path = f"{country}/Data/{today_str}/Item_urls"
    os.makedirs(path, exist_ok=True)
    filename = f"{path}/{country}_category_links.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logging.info(f" {country} Saved to {filename}")

# Get country mapping based on weekday
def get_countries_by_day(day):
    if day in ['Monday', 'Wednesday', 'Friday']:
        return {
            "Australia": {
                'initial': 'https://www.pullandbear.com/au/',
                'cid': '24009414/20309455'
            },
            "Saudi": {
                'initial': 'https://www.pullandbear.com/sa/en/',
                'cid': '25009530/20309454'
            },
            "Spain": {
                'initial': 'https://www.pullandbear.com/es/en/',
                'cid': '24009400/20309449'
            },
            "Turkey": {
                'initial': 'https://www.pullandbear.com/tr/en/',
                'cid': '25009521/20309457'
            }
        }
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        return {
            "UAE": {
                'initial': 'https://www.pullandbear.com/ae/',
                'cid': '25009531/20309454'
            },
            "UK": {
                'initial': 'https://www.pullandbear.com/gb/',
                'cid': '24009406/20309455'
            },
            "USA": {
                'initial': 'https://www.pullandbear.com/us/',
                'cid': '24009477/20309455'
            }
        }
    return {}

# Fetch JSON directly via Playwright
async def fetch_category_json(page, url):
    logging.info(f"Fetching: {url}")
    response = await page.goto(url)
    text = await response.text()
    return json.loads(text)

# Extract category URLs recursively
def extract_category_urls(data, gender, url_dict=None):

    if url_dict is None:
        url_dict = {}
    
    if isinstance(data, dict):
        if "categoryUrl" in data and data["categoryUrl"]:
            cname = data.get('nameEn', '').lower().replace(' ', '-').replace('|', '&')
            if not any(keyword in cname for keyword in pop_key):
                url_dict[cname] = {
                    'id': data.get('id'),
                    'url': data['categoryUrl']
                }
        if "subcategories" in data:
            extract_category_urls(data["subcategories"], gender, url_dict)
        for value in data.values():
            if isinstance(value, (dict, list)):
                extract_category_urls(value, gender, url_dict)
    
    elif isinstance(data, list):
        for item in data:
            extract_category_urls(item, gender, url_dict)
    
    return url_dict

# Main Playwright logic
async def main():
    countries = get_countries_by_day(day)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        for country, cdict in countries.items():
            initial = cdict['initial']
            cid = cdict['cid']

            url = f'https://www.pullandbear.com/itxrest/2/catalog/store/{cid}/category?languageId=-1&typeCatalog=1&appId=1'
            if country == 'USA':
                url = f'https://www.pullandbear.com/itxrest/2/catalog/store/{cid}/category?languageId=-15&typeCatalog=1&appId=1'

            temp_json = {}
            logging.info(f"Fetching {country} category urls now...")

            json_data = await fetch_category_json(page, url)

            # Extract URLs for Woman and Man categories
            for i in json_data.get('categories', []):
                gender = i.get('nameEn')
                if gender in ['Woman', 'Man']:
                    temp_json[gender] = extract_category_urls(i, gender)
                    for cname, data in temp_json[gender].items():
                        data['url'] = initial + data['url']

            # Compare with previous data
            data_folder_path = f'{country}/Data'
            if os.path.exists(data_folder_path):
                previous_dates = sorted(
                    [d for d in os.listdir(data_folder_path) if d != today_str],
                    reverse=True
                )
                previous_data = None
                for prev_date in previous_dates:
                    prev_path = f'{data_folder_path}/{prev_date}/{country}_category_links.json'
                    if os.path.exists(prev_path):
                        with open(prev_path, 'r', encoding='utf-8') as f:
                            previous_data = json.load(f)
                        break

                if previous_data:
                    old_category_json = {k: set(v.keys()) for k, v in previous_data.items()}
                    new_category_json = {k: set(v.keys()) for k, v in temp_json.items()}

                    match = True
                    old_genders = set(old_category_json.keys())
                    new_genders = set(new_category_json.keys())

                    if old_genders == new_genders:
                        old_count, new_count = 0, 0
                        for gender in new_genders:
                            old_set = old_category_json[gender]
                            new_set = new_category_json[gender]
                            old_count += len(old_set)
                            new_count += len(new_set)

                            if old_set != new_set:
                                match = False
                                logging.info(f"[{country}] Gender: {gender}")
                                logging.info(f"Missing: {old_set - new_set}")
                                logging.info(f"New: {new_set - old_set}")

                        change_percentage = ((new_count - old_count) / old_count) * 100 if old_count else 0
                        if not match and change_percentage >= 5:
                            messagebox.showinfo("Alert", f"!!! pull&bear Halted at category URLs for {country} !!!")
                            input("Press Y/y to continue...\n")
                            root.destroy()
                    else:
                        match = False
                        logging.info(f"Gender mismatch: Old={old_genders}, New={new_genders}")
                        messagebox.showinfo("Alert", f"!!! pull&bear Halted at category URLs for {country} !!!")
                        input("Press Y/y to continue...\n")
                        root.destroy()

                    save_json(temp_json, country)
                else:
                    logging.info(f"No previous data found for {country}. Saving new data.")
                    save_json(temp_json, country)
            else:
                logging.info(f"No folder found for {country}. Creating and saving new data.")
                save_json(temp_json, country)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())