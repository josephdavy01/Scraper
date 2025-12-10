from datetime import date
import json
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(name, json_data, date_subfolder, category_path):
    """Save JSON file in gender/category-specific folder"""
    try:
        json_path = date_subfolder / 'Json_data' / category_path
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved JSON for {name} in {category_path}")
    except Exception as e:
        logging.error(f"Error saving JSON for {name}: {e}")

def check_file(name, date_subfolder, category_path):
    return (date_subfolder / 'Json_data' / category_path / f'{name}.json').exists()

def extract_urls_by_category(data):
    """Extract URLs organized by gender and category"""
    urls_by_gender_category = {'women': {}, 'men': {}}

    if isinstance(data, dict):
        for gender in ['women', 'men']:
            if gender in data:
                if isinstance(data[gender], dict):
                    for category, urls in data[gender].items():
                        if isinstance(urls, list):
                            urls_by_gender_category[gender][category] = [url for url in urls if isinstance(url, str)]
                elif isinstance(data[gender], list):
                    urls_by_gender_category[gender]['all'] = [url for url in data[gender] if isinstance(url, str)]

        for key, value in data.items():
            if key.lower() not in ['women', 'men']:
                if isinstance(value, list):
                    for url in value:
                        if isinstance(url, str):
                            url_lower = url.lower()
                            if 'women' in url_lower or 'wmns' in url_lower:
                                urls_by_gender_category['women'].setdefault('others', []).append(url)
                            elif 'men' in url_lower or 'mens' in url_lower:
                                urls_by_gender_category['men'].setdefault('others', []).append(url)

    cleaned = {}
    for gender, categories in urls_by_gender_category.items():
        clean_cats = {}
        for cat, urls in categories.items():
            unique_urls = list(dict.fromkeys(urls))
            if unique_urls:
                clean_cats[cat] = unique_urls
        if clean_cats:
            cleaned[gender] = clean_cats
    return cleaned

def fetch_full_product_json(urls_by_gender_category, date_subfolder, base_url="https://www.oofos.co.uk"):
    for gender, categories in urls_by_gender_category.items():
        for category, urls in categories.items():
            for url in urls:
                try:
                    handle = urlparse(url).path.split('/')[-1]
                    json_url = f"{base_url}/products/{handle}.json"

                    if check_file(handle, date_subfolder, f"{gender}/{category}"):
                        logging.info(f"Skipping (already exists): {handle}")
                        continue

                    response = requests.get(json_url, timeout=15)
                    response.raise_for_status()
                    # The response content might be a JSON string itself.
                    # We first get the text and then parse it with json.loads()
                    # to ensure we have a Python object (dict).
                    data_text = response.text
                    data = json.loads(data_text)

                    # Save JSON in gender/category folder
                    save_json(handle, data, date_subfolder, f"{gender}/{category}")

                except Exception as e:
                    logging.error(f"Failed to fetch {url}: {e}")


country = "UK"
today = date.today().strftime('%Y-%m-%d')
date_subfolder = Path(country) / "Data" / today
input_file_path = date_subfolder / "Item_urls" / f"unique_product_urls.json"

if not input_file_path.exists():
    raise FileNotFoundError(f"Input file not found: {input_file_path}")

with open(input_file_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Extract URLs organized by gender & category
urls_by_gender_category = extract_urls_by_category(raw_data)

# Count total URLs
total_urls = sum(len(urls) for cats in urls_by_gender_category.values() for urls in cats.values())
if total_urls == 0:
    raise ValueError("No URLs found in the input file.")

logging.info(f"\nFound URLs:")
for gender, categories in urls_by_gender_category.items():
    for category, urls in categories.items():
        logging.info(f"  - {gender.capitalize()}/{category}: {len(urls)} products")

# Fetch JSONs and save them
fetch_full_product_json(urls_by_gender_category, date_subfolder)

logging.info(f"\nCompleted fetching JSONs for {total_urls} products across all genders and categories.")
