import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_country_data(country, today_str):
    p_count_list_1 = []
    p_count_list_2 = []
    try:
        file_path_1 = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
        if not os.path.exists(file_path_1):
            logging.error(f'Error: {file_path_1} file not found.')
            return

        with open(file_path_1, 'r', encoding='utf-8') as json_file:
            purls_dict = json.load(json_file)

        for gender in purls_dict:
            for category, plist in purls_dict[gender].items():
                if len(plist) > 0:  # Filter out categories with zero count
                    p_count_list_1.append({'Gender': gender, 'Category': category, 'Count': len(plist)})
            
        file_path_2 = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'
        if not os.path.exists(file_path_2):
            logging.error(f'Error: {file_path_2} file not found.')
            return

        with open(file_path_2, 'r', encoding='utf-8') as json_file:
            purls_dict = json.load(json_file)

        for gender in purls_dict:
            for category, plist in purls_dict[gender].items():
                if len(plist) > 0:  # Filter out categories with zero count
                    p_count_list_2.append({'Gender': gender, 'Category': category, 'Count': len(plist)})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    # Convert the p_count_list_1 to a DataFrame
    p_count_df_1 = pd.DataFrame(p_count_list_1)
    p_count_df_2 = pd.DataFrame(p_count_list_2)

    # Save the DataFrame to a CSV file
    output_dir = Path(f'{country}/Data/{today_str}/Validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_1 = output_dir / f'{country}_product_count.csv'
    p_count_df_1.to_csv(output_file_1, index=False)
    output_file_2 = output_dir / f'{country}_unique_product_count.csv'
    p_count_df_2.to_csv(output_file_2, index=False)

    logging.info(f"{country} product count saved to {output_file_1}.")
    logging.info(f"{country} unique product count saved to {output_file_2}.")

def daily_count_main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['UK']
        for country in countries:
            process_country_data(country, today_str)
    else:
        logging.info(f"Today is {day}. No processing required.")
        return

if __name__ == "__main__":
    daily_count_main()
