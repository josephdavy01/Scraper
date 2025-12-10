import os
import json
import logging
from pathlib import Path
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_ids(country, today_str):
    pids = []

    json_dir = f'{country}/Data/{today_str}/Json_data'
    genders = os.listdir(json_dir)
    for gender in genders:
        gender_dir = f'{json_dir}/{gender}'
        categories = os.listdir(gender_dir)
        for category in categories:
            category_dir = f'{gender_dir}/{category}'
            files = os.listdir(category_dir)
            for file in files:
                file_path = f'{category_dir}/{file}'
                logging.info(file_path)
                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    if data:
                        for pid in data['product']['detail']['colors']:
                            pids.append(pid['productId'])
                except:
                    logging.error('Error processing json file.')
    return list(set(pids))

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['Australia', 'Canada', 'India', 'Saudi', 'Spain']
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['Turkey', 'UAE', 'UK', 'USA']
    else:
        countries = []

    for country in countries:
        ids = get_ids(country, today_str)
        output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(f'{output_dir}/{country}_product_ids.json', "w") as outfile:
            json.dump(ids, outfile, indent=4)