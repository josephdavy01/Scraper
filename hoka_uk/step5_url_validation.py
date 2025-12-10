import os
import logging
import pandas as pd
from datetime import date

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_previous_dates(country, today_str):
    data_folder_path = f'{country}/Data'

    if os.path.exists(data_folder_path):
        previous_dates = list(set(os.listdir(data_folder_path)) - {today_str})
        previous_dates.sort(reverse=True)

        if not previous_dates:
            logging.info(f"No previous dates found for {country}.")
            return

        previous_data = None

        for date_str in previous_dates:
            previous_category_file_path = f'{data_folder_path}/{date_str}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(previous_category_file_path):
                logging.info(f"Previous category file found: {previous_category_file_path}")
                previous_data = pd.read_csv(previous_category_file_path)
                previous_date = date_str
                break

        if previous_data is not None:
            today_category_file_path = f'{data_folder_path}/{today_str}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(today_category_file_path):
                logging.info(f"Today's category file found: {today_category_file_path}")
                today_data = pd.read_csv(today_category_file_path)

                # Get Count for Gender == 'all' and Category == 'all'
                value_1 = previous_data.loc[
                    (previous_data['Gender'] == 'all') & (previous_data['Category'] == 'all'),
                    'Count'
                ].values
                value_2 = today_data.loc[
                    (today_data['Gender'] == 'all') & (today_data['Category'] == 'all'),
                    'Count'
                ].values

                count1 = value_1[0] if len(value_1) > 0 else 0
                count2 = value_2[0] if len(value_2) > 0 else 0

                change_percentage = ((count2 - count1) / count1 * 100) if count1 else 0
                logging.info(f"Count for {country} on {previous_date}: {count1}   and   {today_str}: {count2} - Change: {change_percentage:.2f}%")

                if abs(change_percentage) > 5:
                    logging.info(f"Significant change detected for {country} on {today_str}. Change: {change_percentage:.2f}%")
            else:
                logging.warning(f"Today's file not found for {country}: {today_category_file_path}")
        else:
            logging.warning(f"No previous data found for {country} with the file.")
    else:
        logging.error(f"Data folder does not exist: {data_folder_path}")


if __name__ == "__main__":
    # Manual input for today
    today_str = date.today().strftime('%Y-%m-%d')

    # You can manually define the list of countries here
    countries = ['UK']

    for country in countries:
        check_previous_dates(country, today_str)
