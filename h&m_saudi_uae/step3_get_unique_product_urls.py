import os
import json
import logging
from pathlib import Path
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_pids_1(country, today_str):
    try:
        file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path) as json_file:
            urls_dict = json.load(json_file)

        unique_pids = {}

        for gender, categories in urls_dict.items():
            temp = [pid for pids in categories.values() for pid in pids]
            templist = sorted(set(pid[:-3] for pid in temp))
            unique_pids[gender] = [next(pid for pid in temp if pid.startswith(prefix)) for prefix in templist]
        
        # Save the data to a JSON file
        output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = f'{output_dir}/{country}_unique_product_urls.json'

        with open(output_file, "w") as outfile:
            json.dump(unique_pids, outfile, indent=4)

        logging.info(f"{country} product count saved to {output_file}")

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return
    
def get_unique_pids_2(country, today_str):
    try:
        file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
        if not os.path.exists(file_path):
            logging.error(f'Error: {file_path} file not found.')
            return

        with open(file_path) as json_file:
            urls_dict = json.load(json_file)

        unique_pids = {}

        for gender, categories in urls_dict.items():
            temp = [url for cdict in categories.values() for url in cdict.values()]
            unique_pids[gender] = list(set(temp))
        
        # Save the data to a JSON file
        output_dir = Path(f'{country}/Data/{today_str}/Item_urls')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = f'{output_dir}/{country}_unique_product_urls.json'

        with open(output_file, "w") as outfile:
            json.dump(unique_pids, outfile, indent=4)

        logging.info(f"{country} product count saved to {output_file}")

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-03'

    # Get the current day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    # Determine the scripts to run based on the day
    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['Saudi', 'UAE']
        for country in countries:
            get_unique_pids_2(country, today_str)
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['India', 'UK']
        for country in countries:
            get_unique_pids_1(country, today_str)