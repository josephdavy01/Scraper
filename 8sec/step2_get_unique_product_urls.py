import json
import logging
import os
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'

    # Check if file exists
    if not os.path.exists(read_file_path):
        print(f"Error: File or folder not found - '{read_file_path}'")
        return

    with open(read_file_path, 'r', encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    # Track all URLs globally to identify duplicates
    global_url_tracker = {}  # url -> list of (gender, category, subcategory)

    # First pass: collect all URLs and their locations
    for gender, categories in url_dict.items():
        if isinstance(categories, dict):
            for category, subcontent in categories.items():
                if isinstance(subcontent, dict):
                    # Further nested structure
                    for subcategory, urls in subcontent.items():
                        if isinstance(urls, list):
                            for url in urls:
                                if url not in global_url_tracker:
                                    global_url_tracker[url] = []
                                global_url_tracker[url].append((gender, category, subcategory))
                elif isinstance(subcontent, list):
                    for url in subcontent:
                        if url not in global_url_tracker:
                            global_url_tracker[url] = []
                        global_url_tracker[url].append((gender, category, None))
        elif isinstance(categories, list):
            for url in categories:
                if url not in global_url_tracker:
                    global_url_tracker[url] = []
                global_url_tracker[url].append((gender, None, None))

    # Count duplicates
    total_urls = sum(len(locations) for locations in global_url_tracker.values())
    unique_urls = len(global_url_tracker)
    duplicates = total_urls - unique_urls

    logging.info(f"Total URLs found for {country}: {total_urls}")
    logging.info(f"Unique URLs found for {country}: {unique_urls}")
    logging.info(f"Duplicate URLs found: {duplicates}")

    # Second pass: rebuild structure with only unique URLs
    # Keep URL in the FIRST location it appears (based on iteration order)
    result = {}
    used_urls = set()

    for gender, categories in url_dict.items():
        if isinstance(categories, dict):
            result[gender] = {}
            for category, subcontent in categories.items():
                if isinstance(subcontent, dict):
                    # Further nested structure
                    result[gender][category] = {}
                    for subcategory, urls in subcontent.items():
                        if isinstance(urls, list):
                            unique_list = []
                            for url in urls:
                                if url not in used_urls:
                                    unique_list.append(url)
                                    used_urls.add(url)
                            result[gender][category][subcategory] = unique_list
                        else:
                            result[gender][category][subcategory] = urls
                elif isinstance(subcontent, list):
                    unique_list = []
                    for url in subcontent:
                        if url not in used_urls:
                            unique_list.append(url)
                            used_urls.add(url)
                    result[gender][category] = unique_list
                else:
                    result[gender][category] = subcontent
        elif isinstance(categories, list):
            unique_list = []
            for url in categories:
                if url not in used_urls:
                    unique_list.append(url)
                    used_urls.add(url)
            result[gender] = unique_list
        else:
            result[gender] = categories

    # Save the deduplicated data
    with open(write_file_path, "w", encoding='utf-8') as outfile:
        json.dump(result, outfile, indent=4, ensure_ascii=False)

    logging.info(f"Unique URLs saved: {len(used_urls)}")
    logging.info(f"{country} unique product urls saved to {write_file_path}")

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['India', 'Spain']

    for country in countries:
        get_unique_urls(country, today_str)
