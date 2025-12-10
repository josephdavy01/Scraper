import os
import json
import logging
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(gender, category, json_data, pid, date_subfolder):
    try:
        json_file_path = date_subfolder / 'Json_data' / gender / category
        json_file_path.mkdir(parents=True, exist_ok=True)
        with open(json_file_path / f'{pid}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for category '{pid}': {e}")

def get_json(page, url):
    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state('domcontentloaded')
        html_content = page.content()

        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')

        for script in scripts:
            data = str(script.get_text())

            if 'self.__next_f.push([1,"5:[\\"$\\"' in data:
                stext = '{\\"productData\\":'
                etext = ',\\"categoryExists\\"'

                spoint = data.find(stext)
                epoint = data.find(etext)

                if spoint != -1:
                    spoint += len(stext)

                if spoint < epoint:
                    stext = '\\"productData\\":'
                    etext = ',\\"translations\\"'

                    spoint = data.find(stext)
                    epoint = spoint + data[spoint:].find(etext)

                    if spoint != -1:
                        spoint += len(stext)

                if spoint != -1 and epoint != -1 and epoint > spoint:
                    extracted_data = data[spoint:epoint].strip()

                    try:
                        extracted_data = extracted_data.encode().decode("unicode_escape")
                        product_data = json.loads(extracted_data)
                        return product_data
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON Decode Error at {url}: {e}")
                        return None

        logging.warning(f"No valid productData found in script at {url}")
        return None
    except Exception as e:
        logging.error(f"Error opening the URL {url}: {e}")
        return None
    

# Footwear filter function
def fliter(html):
    soup = BeautifulSoup(html, "html.parser")
    category = soup.find("main", {"class": "MuiBox-root mui-0", "role": "main"})
    if not category:
        return False
    
    category_sub = category.find("div", {"class": "MuiBox-root mui-x0m7sa", "data-testautomation-id": "pdp-page"})
    if not category_sub:
        return False
    
    script_tag = soup.find("script", {"type": "application/ld+json"})
    if not script_tag or not script_tag.string:
        return False
    
    try:
        data = json.loads(script_tag.string)
    except json.JSONDecodeError:
        return False
    
    items = data.get("itemListElement", [])
    for item in items:
        if item.get("name") in ["Clothing", "Shoes"]:
            return item.get("name")
    return False  

def check_file(gender, category, pid, date_subfolder):
    file_path = date_subfolder / 'Json_data' / gender / category / f'{pid}.json'
    return os.path.exists(file_path)

def process_category(page, gender, category, urls, date_subfolder):
    for url in urls:
        pid = url.split('-')[-1]
        if not check_file(gender, category, pid, date_subfolder):
            json_data = get_json(page, url)
            if json_data:
                html_content = page.content()
                shoe_value = fliter(html_content)
                if shoe_value:
                    json_data["category"] = shoe_value
                save_json(gender, category, json_data, pid, date_subfolder)
            else:
                logging.warning(f"Skipping saving JSON for {url} due to previous errors.")

def main():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    countries = ['USA']

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for country in countries:
            date_subfolder = Path(country) / 'Data' / today_str
            date_subfolder.mkdir(parents=True, exist_ok=True)

            json_file_path = date_subfolder / 'Item_urls'
            try:
                with open(json_file_path / f'{country}_unique_product_urls.json', 'r', encoding='utf-8') as jsonfile:
                    urldata = json.load(jsonfile)
            except FileNotFoundError:
                logging.error(f"unique_product_urls.json not found for {country}.")
                continue
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from product links file: {e}")
                continue

            categories = urldata 
            for gender, gender_data in categories.items():
                for category, urls in gender_data.items():
                    logging.info(f"Processing {country} {gender} {category}...")
                    process_category(page, gender, category, urls, date_subfolder)
                    logging.info(f"Completed {country} {gender} {category}")

        browser.close()

if __name__ == "__main__":
    main()
