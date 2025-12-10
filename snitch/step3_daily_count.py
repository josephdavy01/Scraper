import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date
from alert import raise_ticket

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_country_data(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/{today_str}/Item_urls/{country}_product_links.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            raise_ticket("Step 3", "process_country_data", f"Product links file not found for {country}", country)
            return False

        with open(file_path, 'r', encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)

        for gender, categories in urls_dict.items():
            for category, urls in categories.items():
                p_count_list.append({'Gender': gender, 'Category': category, 'Count': len(urls)})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        raise_ticket("Step 3", "process_country_data", f"Error processing data for {country}: {e}", country)
        return

    # Convert the p_count_list to a DataFrame
    try:
        p_count_df = pd.DataFrame(p_count_list)

        # Save the DataFrame to a CSV file
        output_dir = Path(f'{country}/{today_str}/Validation')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f'{country}_product_count.csv'
        p_count_df.to_csv(output_file, index=False)

        logging.info(f"{country} product count saved to {output_file}")
    except Exception as e:
        logging.error(f"Error saving CSV for {country}: {e}")
        raise_ticket("Step 3", "process_country_data", f"Error saving CSV for {country}: {e}", country)
