import os
import logging
import pandas as pd
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_previous_dates(country, today_str):
    data_folder_path = f'{country}/Data'

    # Check data folder
    if os.path.exists(data_folder_path):
        # Ensure directory exists before saving JSON
        previous_dates = list(set(os.listdir(data_folder_path)) - {today_str})
        previous_dates.sort(reverse=True)

        if not previous_dates:
            logging.info(f"No previous dates found for {country}.")
            return
        
        previous_data = None

        # Iterate through previous dates to find the first available data
        for date in previous_dates:
            previous_category_file_path = f'{data_folder_path}/{date}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(previous_category_file_path):
                logging.info(f"Previous category file found: {previous_category_file_path}")
                previous_date = date
                previous_data = pd.read_csv(previous_category_file_path)
                break
            
        if previous_data is not None:
            # Compare with today's data
            today_category_file_path = f'{data_folder_path}/{today_str}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(today_category_file_path):
                logging.info(f"Today's category file found: {today_category_file_path}")
                today_data = pd.read_csv(today_category_file_path)

                # Filter for Gender == 'all' and Category == 'all'
                value_1 = previous_data.loc[
                    (previous_data['Gender'] == 'all') & (previous_data['Category'] == 'all'),
                    'Count'
                ].values

                # Filter for Gender == 'all' and Category == 'all'
                value_2 = today_data.loc[
                    (today_data['Gender'] == 'all') & (today_data['Category'] == 'all'),
                    'Count'
                ].values

                count1 = value_1[0] if value_1 else 0
                count2 = value_2[0] if value_2 else 0

                change_percentage = ((count1 - count2) / count2 * 100) if count2 else 0
                logging.info(f"Value for {country} on {previous_date}: {count2}   and   {today_str}: {count1} - Change: {change_percentage:.2f}%")

                if change_percentage > 5:
                    logging.info(f"Significant change detected for {country} on {today_str}. Change percentage: {change_percentage:.2f}%")
                    
    else:
        logging.error(f"Data folder for {country} does not exist: {data_folder_path}")
        return
    
if __name__ == "__main__":

    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-23'
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday','Thursday', 'Saturday']:
        countries = ['INDIA','UAE']
        for country in countries:
            check_previous_dates(country, today_str)
    else:        
        countries = ['UK','USA']
        for country in countries:
            check_previous_dates(country, today_str)