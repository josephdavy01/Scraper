import logging
import os
import json
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_data_format(countries, date_str):
    # Handle both dict and list input for countries
    country_list = countries.keys() if isinstance(countries, dict) else countries

    for country in country_list:
        geography = country.lower()
        
        # Define file path
        final_json_dir = os.path.join(country, date_str, 'Final_json')
        if not os.path.exists(final_json_dir):
             logging.error(f"Final_json directory not found for {geography} at {final_json_dir}")
             continue
             
        # Check all JSON files in the directory, excluding error logs and duplicate logs
        files_to_check = [f for f in os.listdir(final_json_dir) if f.endswith('.json') and 'duplicate' not in f and 'error' not in f]
        
        if not files_to_check:
            logging.warning(f"No data files found in {final_json_dir}")
            continue
            
        for file_name in files_to_check:
            file_path = os.path.join(final_json_dir, file_name)
            logging.info(f"Checking format for file: {file_path}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logging.error(f"Error reading data file {file_path}: {e}")
                continue

            if not data:
                 logging.warning(f"Data file is empty: {file_path}")
                 continue

            # Extract fields for validation
            product_ids = [item.get('product_id') for item in data]
            genders = [item.get('gender') for item in data]
            titles = [item.get('title') for item in data]
            colors = [item.get('color_name') for item in data]
            skus = [item.get('sku') for item in data]
            prices = [item.get('price') for item in data]
            launch_prices = [item.get('launch_price') for item in data]
            availabilities = [item.get('availability') for item in data]
            
            # Flatten lists for age_group and age_range
            all_age_groups = []
            for item in data:
                ag = item.get('age_group')
                if isinstance(ag, list):
                    all_age_groups.extend(ag)
                elif ag is not None:
                    all_age_groups.append(ag)
                else:
                    all_age_groups.append(None)

            all_age_ranges = []
            for item in data:
                ar = item.get('age_range')
                if isinstance(ar, list):
                    all_age_ranges.extend(ar)
                elif ar is not None:
                    all_age_ranges.append(ar)
                else:
                    all_age_ranges.append(None)

            format_check = 0
            
            # Check for None
            if any(x is None for x in product_ids):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'product_id' contains None.")
            if any(x is None for x in prices):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'price' contains None.")
            if any(x is None for x in launch_prices):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'launch_price' contains None.")
            if any(x is None for x in availabilities):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'availability' contains None.")
            if any(x is None for x in colors):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'color_name' contains None.")
            if any(x is None for x in skus):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'sku' contains None.")
            if any(x is None for x in genders):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'gender' contains None.")
            if any(x is None for x in titles):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'title' contains None.")
            if any(x is None for x in all_age_groups):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'age_group' contains None.")
            if any(x is None for x in all_age_ranges):
                 format_check = 1
                 logging.error(f"Data format error in {file_name}: 'age_range' contains None.")

            # Check for invalid values
            valid_genders = ['male', 'female', 'unisex']
            if any(g not in valid_genders for g in genders if g is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'gender' contains invalid values.")

            valid_availabilities = ['in_stock', 'out_of_stock', 'low_on_stock', 'back_soon', 'coming_soon']
            if any(a not in valid_availabilities for a in availabilities if a is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'availability' contains invalid values.")

            if any(not isinstance(p, (int, float)) for p in prices if p is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'price' contains non-numeric values.")

            if any(not isinstance(lp, (int, float)) for lp in launch_prices if lp is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'launch_price' contains non-numeric values.")

            if any(not isinstance(s, str) for s in skus if s is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'sku' contains non-string values.")

            if any(not isinstance(t, str) for t in titles if t is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'title' contains non-string values.")

            if any(not isinstance(c, str) for c in colors if c is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'color_name' contains non-string values.")

            valid_age_groups = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']
            if any(ag not in valid_age_groups for ag in all_age_groups if ag is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'age_group' contains invalid values.")

            valid_age_ranges = ['1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y', '11y', '12y', '13y', '14y', '15y', '16y', '17y', '18y']
            if any(ar not in valid_age_ranges for ar in all_age_ranges if ar is not None):
                format_check = 1
                logging.error(f"Data format error in {file_name}: 'age_range' contains invalid values.")

            if format_check == 0:
                logging.info(f"Data format check passed for {file_name}. All fields are correctly formatted.")
            else:
                logging.error(f"Data format check failed for {file_name}. Please review the errors above.")

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    countries = {'UK': 'https://uk.anta.com','USA':'https://www.anta.com'}
    check_data_format(countries, today_str)