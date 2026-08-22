import os
import logging
import pandas as pd
from datetime import date

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def data_validation(country, today_str):
    # Compare with today's data
    today_pids_comparison_file_path = f'{country}/Data/{today_str}/Validation/{country}_url-json_comparison.csv'
    if os.path.exists(today_pids_comparison_file_path):
        logging.info(f"Today's category file found: {today_pids_comparison_file_path}")
        today_data = pd.read_csv(today_pids_comparison_file_path)

        # Pids total count for today
        pid_count = today_data['Pids'].sum() if 'Pids' in today_data.columns else 0
        Json_count = today_data['Jsons'].sum() if 'Jsons' in today_data.columns else 0
        logging.info(f"Total Pids for {country} on {today_str}: {pid_count}")
        logging.info(f"Total Jsons for {country} on {today_str}: {Json_count}")

        change_percentage = ((pid_count - Json_count) / Json_count * 100) if Json_count else 0
        logging.info(f"Difference percentage for {country} on {today_str}: {change_percentage:.2f}%")

        if change_percentage > 5:
            logging.info(f"Significant change detected for {country} on {today_str}. Change percentage: {change_percentage:.2f}%")
            
    else:
        logging.error(f"Data file for {country} on {today_str} not found: {today_pids_comparison_file_path}")
        return
    
if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    countries = ['USA']

    for country in countries:
        data_validation(country, today_str)