import json
import logging
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/variant_urls.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/unique_variant_urls.json'

    with open(read_file_path) as json_file:
        url_dict = json.load(json_file)

    temp = {}

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for category, pids in categories.items():
            # Remove duplicates *within this category only*
            unique_pids = list(set(pids))
            temp[gender][category] = unique_pids

    with open(write_file_path, "w", encoding='utf-8') as outfile:
        json.dump(temp, outfile, indent=4)
    
    logging.info(f"{country} unique product urls (per category) saved to {write_file_path}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-21'
    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['USA', 'UK']

    for country in countries:
        get_unique_urls(country, today_str)
