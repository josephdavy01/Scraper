import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def count_urls(obj):
    if isinstance(obj, list):
        return len(obj)
    elif isinstance(obj, dict):
        return sum(count_urls(v) for v in obj.values())
    return 0

def process_country_data(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/{today_str}/Item_urls/{country.lower()}_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path, 'r', encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)

        if not isinstance(urls_dict, dict):
            logging.error(f"Error: Expected dictionary in {file_path}, but got {type(urls_dict).__name__}. Please re-run step2 to regenerate valid data.")
            return

        for gender, categories in urls_dict.items():
            if not isinstance(categories, dict):
                 continue
            for category, subcats in categories.items():
                count = count_urls(subcats)
                p_count_list.append({
                    'Gender': gender,
                    'Category': category,
                    'Count': count
                })

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    if not p_count_list:
        logging.warning(f"No data to write for {country}.")
        return

    p_count_df = pd.DataFrame(p_count_list)

    output_dir = Path(f'{country}/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_product_count.csv'
    p_count_df.to_csv(output_file, index=False)

    logging.info(f"{country} product count saved to {output_file}")

if __name__ == "__main__":
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    dt = datetime.now()
    day = dt.strftime('%A')

    countries = ["India"]

    for country in countries:
        process_country_data(country, today_str)
