import os
import json
import logging
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def remove_global_duplicates(data):
    seen_urls = set()
    cleaned_data = {}
    for gender, categories in data.items():
        cleaned_data[gender] = {}
        for category, urls in categories.items():
            unique_urls = []
            for url in urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_urls.append(url)
            cleaned_data[gender][category] = unique_urls
    return cleaned_data

def process_country(country, today_str):
    read_file_path = f"{country}/Data/{today_str}/Item_urls/{country}_product_urls.json"
    write_file_path = f"{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json"

    if not os.path.exists(read_file_path):
        logging.warning(f"File not found: {read_file_path}")
        return

    with open(read_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Deduplicate using unified logic
    cleaned_data = remove_global_duplicates(data)

    with open(write_file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4)

    total_links = sum(len(urls) for categories in cleaned_data.values() for urls in categories.values())
    logging.info(f"{country}: {total_links} unique product URLs saved to {write_file_path}")

if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    countries = ["UK", "India", "USA"]
    for country in countries:
        process_country(country, today_str)
