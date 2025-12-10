import os
import json
import logging
import pandas as pd
from datetime import date

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def compare_urls_with_json(json_base_path, url_file_path, brand, today_str):
    # Initialize a list to hold the comparison data
    temp = []

    with open(url_file_path) as json_file:
        urls_dict = json.load(json_file)

    for category, urls in urls_dict.items():
        # Only process if there are product URLs for this category
        if len(urls) != 0:
            # Construct the path to the category's JSON files directory
            json_category_path = os.path.join(json_base_path, category)

            # Count JSON files if directory exists, otherwise set to 0
            if os.path.exists(json_category_path):
                json_entries = [entry for entry in os.listdir(json_category_path) if entry.endswith('.json')]
                json_count = len(json_entries)
            else:
                json_count = 0

            # Append the comparison data to the list
            temp.append({
                'Category': category,
                'URLs': len(urls),
                'Jsons': json_count,
                'Json Difference': len(urls) - json_count,
            })

    # Convert the list to a DataFrame and save it as a CSV file
    df = pd.DataFrame(temp)
    
    # Save the DataFrame to a CSV file
    output_dir = f'Data/{today_str}/Validation'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{brand}_product_url_json_comparison.csv')
    df.to_csv(output_file, index=False)

    logging.info(f"{brand} product count saved to {output_file}")

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    brand = 'amazon_damensch'

    # Define base paths
    json_base_path = f'Data/{today_str}/Json_data'
    if not os.path.exists(json_base_path):
        logging.error(f'Error: {json_base_path} directory not found.')
        exit()

    url_file_path = f'Data/{today_str}/Item_urls/{brand}_product_urls.json'
    if not os.path.exists(url_file_path):
        logging.error(f'Error: {url_file_path} file not found.')
        exit()

    compare_urls_with_json(json_base_path, url_file_path, brand, today_str)