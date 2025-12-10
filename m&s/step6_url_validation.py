import os
import logging
import pandas as pd
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def check_previous_dates(country, today_str):
    data_folder_path = f'{country}/Data'
    if not os.path.exists(data_folder_path):
        logging.error(f"Data folder for {country} does not exist: {data_folder_path}")
        return
    previous_dates = list(set(os.listdir(data_folder_path)) - {today_str})
    previous_dates.sort(reverse=True)
    if not previous_dates:
        logging.info(f"No previous dates found for {country}.")
        return
    previous_data = None
    previous_date = None
    for prev_date in previous_dates:
        previous_category_file_path = f'{data_folder_path}/{prev_date}/Validation/{country}_unique_product_count.csv'
        if os.path.exists(previous_category_file_path):
            logging.info(f"Previous category file found: {previous_category_file_path}")
            previous_date = prev_date
            previous_data = pd.read_csv(previous_category_file_path)
            break
    if previous_data is None:
        logging.info(f"No previous category file found for {country}.")
        return
    today_category_file_path = f'{data_folder_path}/{today_str}/Validation/{country}_unique_product_count.csv'
    if not os.path.exists(today_category_file_path):
        logging.info(f"Today's category file not found for {country}: {today_category_file_path}")
        return
    logging.info(f"Today's category file found: {today_category_file_path}")
    today_data = pd.read_csv(today_category_file_path)
    prev_count_val = previous_data.loc[
        (previous_data['Gender'] == 'all') & (previous_data['Category'] == 'all'),
        'Count'
    ].values
    today_count_val = today_data.loc[
        (today_data['Gender'] == 'all') & (today_data['Category'] == 'all'),
        'Count'
    ].values
    prev_count = prev_count_val[0] if prev_count_val.size > 0 else 0
    today_count = today_count_val[0] if today_count_val.size > 0 else 0
    change_percentage = ((today_count - prev_count) / prev_count * 100) if prev_count else 0
    logging.info(
        f"Value for {country} on {previous_date}: {prev_count}   "
        f"and {today_str}: {today_count} - Change: {change_percentage:.2f}%"
    )
    if abs(change_percentage) > 5:
        logging.info(
            f"Significant change detected for {country} on {today_str}. "
            f"Change percentage: {change_percentage:.2f}%"
        )

if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
    countries = ['UK', 'India','USA']
    for country in countries:
        check_previous_dates(country, today_str)
