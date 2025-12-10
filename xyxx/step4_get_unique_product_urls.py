import json
import logging
from datetime import date, datetime
import os

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def process_country_data(country, today_str):
    read_file_path = f'{country}/{today_str}/Items_urls/{country}_product_urls.json'
    write_file_path = f'{country}/{today_str}/Items_urls/{country}_unique_product_urls.json'

    # Check if input file exists
    if not os.path.exists(read_file_path):
        logging.error(f"File not found: {read_file_path}")
        return

    # Read JSON file
    with open(read_file_path, encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    # Collect all URLs in a set (to ensure global uniqueness)
    all_urls = set()
    for gender, categories in url_dict.items():
        for cat, urls in categories.items():
            all_urls.update(urls)

    logging.info(f"Total unique urls found for {country}: {len(all_urls)}")

    # Now create filtered structure keeping only unique URLs per gender/category
    seen = set()
    temp = {}

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for cat, urls in categories.items():
            unique_urls = []
            for url in urls:
                if url not in seen:  # add only if not already used anywhere
                    seen.add(url)
                    unique_urls.append(url)
            if unique_urls:
                temp[gender][cat] = unique_urls

    # Ensure output directory exists
    os.makedirs(os.path.dirname(write_file_path), exist_ok=True)

    # Write final JSON with unique URLs
    with open(write_file_path, "w", encoding="utf-8") as outfile:
        json.dump(temp, outfile, indent=4)

    logging.info(f"{country} unique product urls saved to {write_file_path}")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['India']

    for country in countries:
        process_country_data(country, today_str)   # ✅ FIXED FUNCTION CALL
