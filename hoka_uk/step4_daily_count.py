import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_file(file_path):
    """Handles both dict and list JSON structures and returns a summary list."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            count_list = []
            total = 0
            for gender in data:
                if isinstance(data[gender], dict):
                    for category, plist in data[gender].items():
                        if plist:
                            count = len(plist)
                            total += count
                            count_list.append({'Gender': gender, 'Category': category, 'Count': count})
            count_list.append({'Gender': 'all', 'Category': 'all', 'Count': total})
            return count_list, total

        elif isinstance(data, list):
            df = pd.DataFrame(data)
            total = df['Count'].sum() if 'Count' in df.columns else 0
            df.loc[len(df.index)] = {'Gender': 'all', 'Category': 'all', 'Count': total}
            return df.to_dict(orient='records'), total

        else:
            logging.error(f"Unsupported data format in {file_path}")
            return [], 0

    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return [], 0

def process_country_data(country, date_str):
    try:
        base_dir = Path(f'{country}/Data/{date_str}/Item_urls')
        file_path_1 = base_dir / f'{country}_product_ids.json'
        file_path_2 = base_dir / f'{country}_variant_product_ids.json'

        if not file_path_1.exists():
            logging.error(f'File not found: {file_path_1}')
            return
        if not file_path_2.exists():
            logging.error(f'File not found: {file_path_2}')
            return

        count_list_1, total_1 = process_file(file_path_1)
        count_list_2, total_2 = process_file(file_path_2)

        df_1 = pd.DataFrame(count_list_1)
        df_2 = pd.DataFrame(count_list_2)

        output_dir = Path(f'{country}/Data/{date_str}/Validation')
        output_dir.mkdir(parents=True, exist_ok=True)

        df_1.to_csv(output_dir / f'{country}_product_count.csv', index=False)
        df_2.to_csv(output_dir / f'{country}_unique_product_count.csv', index=False)

        logging.info(f" {country}: product count saved to {output_dir}/{country}_product_count.csv")
        logging.info(f" {country}: unique product count saved to {output_dir}/{country}_unique_product_count.csv")
        logging.info(f" {country} total products: {total_1}")
        logging.info(f" {country} unique products: {total_2}")

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")

if __name__ == "__main__":
    countries = ['UK']
    today_str = datetime.now().strftime('%Y-%m-%d')

    for country in countries:
        process_country_data(country, today_str)
