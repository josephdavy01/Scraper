import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_product_count(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path) as json_file:
            urls_dict = json.load(json_file)

        for gender, pids in urls_dict.items():
            p_count_list.append({'Gender': gender, 'Count': len(pids)})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    # Convert the p_count_list to a DataFrame
    p_count_df = pd.DataFrame(p_count_list)

    # Save the DataFrame to a CSV file
    output_dir = Path(f'{country}/Data/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_unique_product_count.csv'
    p_count_df.to_csv(output_file, index=False)

    logging.info(f"{country} product count saved to {output_file}")

def get_product_count(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path) as json_file:
            urls_dict = json.load(json_file)

        for gender, categories in urls_dict.items():
            for category, pids in categories.items():
                p_count_list.append({'Gender': gender, 'Category': category, 'Count': len(pids)})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    # Convert the p_count_list to a DataFrame
    p_count_df = pd.DataFrame(p_count_list)

    # Save the DataFrame to a CSV file
    output_dir = Path(f'{country}/Data/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_product_count.csv'
    p_count_df.to_csv(output_file, index=False)

    logging.info(f"{country} product count saved to {output_file}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    
    # Get the current day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday']:
        countries = ['India']
    elif day in ['Thursday']:
        countries = ['UK']
    else:
        countries = []

    for country in countries:
        get_product_count(country, today_str)
        get_unique_product_count(country, today_str)