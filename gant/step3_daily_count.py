import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_country_data(country, today_str):
    p_count_list = []
    try:
        file_path = f'{country}/{today_str}/Item_urls/{country}_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path) as json_file:
            pids_dict = json.load(json_file)

        for gender in pids_dict:
            for category, plist in pids_dict[gender].items():
                if len(plist) > 0:  # Filter out categories with zero count
                    p_count_list.append({'Gender': gender, 'Category': category, 'Count': len(plist)})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    # Convert the p_count_list to a DataFrame
    p_count_df = pd.DataFrame(p_count_list)

    # Save the DataFrame to a CSV file
    output_dir = Path(f'{country}/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_product_count.csv'
    p_count_df.to_csv(output_file, index=False)

    logging.info(f"{country} product count saved to {output_file}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    country = 'UAE'
    
    process_country_data(country, today_str)