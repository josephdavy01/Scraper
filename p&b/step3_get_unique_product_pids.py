import json
import logging
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_ids.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_ids.json'

    with open(read_file_path) as json_file:
        url_dict = json.load(json_file)

    all_ids = set()

    for gender, categories in url_dict.items():
        for category, ids in categories.items():
            for id in ids:
                all_ids.add(id)

    logging.info(f"Total unique IDs found for {country}: {len(all_ids)}")

    temp = {}

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for category, ids in categories.items():
            curls = all_ids.intersection(set(ids))
            all_ids = all_ids - set(ids)
            ids = list(curls)
            temp[gender][category] = ids

    with open(write_file_path, "w", encoding='utf-8') as outfile:
        json.dump(temp, outfile, indent=4)

    logging.info(f"{country} unique product ids saved to {write_file_path}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    # Assign countries based on the day
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['Australia', 'Saudi', 'Spain', 'Turkey']
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['UAE', 'UK', 'USA']
    else:
        countries = []

    for country in countries:
        get_unique_urls(country, today_str)