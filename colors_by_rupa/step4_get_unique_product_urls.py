import json
import logging
from datetime import date, datetime
import os

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def process_country_data(country, today_str):
    read_file_path = f'{country}/{today_str}/Item_urls/{country.lower()}_product_urls.json'
    write_file_path = f'{country}/{today_str}/Item_urls/{country.lower()}_unique_product_urls.json'

    # Check if input file exists
    if not os.path.exists(read_file_path):
        logging.error(f"File not found: {read_file_path}")
        return

    with open(read_file_path, encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    all_urls = set()
    
    def extract_urls(obj):
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, str) and item.startswith("http"):
                    all_urls.add(item)
        elif isinstance(obj, dict):
            for value in obj.values():
                extract_urls(value)

    extract_urls(url_dict)

    logging.info(f"Total unique urls found for {country}: {len(all_urls)}")

    seen = set()
    
    def filter_tree(obj):
        if isinstance(obj, list):
            unique_list = []
            for item in obj:
                if isinstance(item, str) and item.startswith("http"):
                    if item not in seen:
                        seen.add(item)
                        unique_list.append(item)
            return unique_list
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                filtered_val = filter_tree(v)
                if isinstance(filtered_val, list) or isinstance(filtered_val, dict):
                     if filtered_val: 
                        new_dict[k] = filtered_val
            return new_dict
        return obj

    temp = filter_tree(url_dict)


    os.makedirs(os.path.dirname(write_file_path), exist_ok=True)

    with open(write_file_path, "w", encoding="utf-8") as outfile:
        json.dump(temp, outfile, indent=4)

    logging.info(f"{country} unique product urls saved to {write_file_path}")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['India']

    for country in countries:
        process_country_data(country, today_str)   
