import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_product_count(country, today_str):
    p_count_list = []
    try:
        if country == "India":
            file_path = f'{country}/Data/{today_str}/Item_urls/unique_product_ids.json'
        else:
            file_path = f'{country}/Data/{today_str}/Item_urls/unique_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return
        with open(file_path, encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)
        if not urls_dict:
            logging.warning(f'{file_path} is empty.')
            return
        for gender, categories in urls_dict.items():
            if isinstance(categories, dict):
                for category, urls in categories.items():
                    if isinstance(urls, list):
                        p_count_list.append({
                            'Gender': gender,
                            'Category': category,
                            'Count': len(urls)
                        })
            elif isinstance(categories, list):
                p_count_list.append({
                    'Gender': gender,
                    'Category': "All",
                    'Count': len(categories)
                })
    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return
    p_count_df = pd.DataFrame(p_count_list)
    output_dir = Path(f'{country}/Data/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'unique_product_count.csv'
    p_count_df.to_csv(output_file, index=False)

    logging.info(f"{country} unique product count saved to {output_file}")


def get_product_count(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/Data/{today_str}/Item_urls/product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return
        with open(file_path, encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)
        for gender, categories in urls_dict.items():
            for category, pids in categories.items():
                p_count_list.append({'Gender': gender, 'Category': category, 'Count': len(pids)})
    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return
    p_count_df = pd.DataFrame(p_count_list)
    output_dir = Path(f'{country}/Data/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_product_count.csv'
    p_count_df.to_csv(output_file, index=False)
    logging.info(f"{country} product count saved to {output_file}")

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['India', 'UAE']
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['UK', 'USA']
    else:
        countries = []
    for country in countries:
        get_product_count(country, today_str)
        get_unique_product_count(country, today_str)
