import os
import logging
import pandas as pd
from datetime import date, datetime

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

        for date in previous_dates:
            previous_category_file_path = f'{data_folder_path}/{date}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(previous_category_file_path):
                logging.info(f"Previous category file found: {previous_category_file_path}")
                previous_date = date
                previous_data = pd.read_csv(previous_category_file_path)
                break

        if previous_data is not None:
            today_category_file_path = f'{data_folder_path}/{today_str}/Validation/{country}_unique_product_count.csv'
            if os.path.exists(today_category_file_path):
                logging.info(f"Today's category file found: {today_category_file_path}")
                today_data = pd.read_csv(today_category_file_path)

                # Clean column names
                previous_data.columns = previous_data.columns.str.strip()
                today_data.columns = today_data.columns.str.strip()

                # Check if 'Category' column exists
                required_cols = ['Gender', 'Count']
                has_category = 'Category' in previous_data.columns and 'Category' in today_data.columns
                if has_category:
                    required_cols.append('Category')

                # Check for missing columns
                for df_name, df in [('Previous', previous_data), ('Today', today_data)]:
                    missing = [col for col in required_cols if col not in df.columns]
                    if missing:
                        logging.error(f"{df_name} data for {country} is missing columns: {missing}")
                        return

                # Determine values
                if has_category:
                    # Use 'all' filter if both Gender and Category columns exist
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
                else:
                    # Fallback: sum total count if 'Category' not present
                    count1 = previous_data['Count'].sum()
                    count2 = today_data['Count'].sum()

                change_percentage = ((count1 - count2) / count2 * 100) if count2 else 0
                logging.info(f"Value for {country} on {previous_date}: {count2}   and   {today_str}: {count1} - Change: {change_percentage:.2f}%")

                if change_percentage > 5:
                    logging.info(f"Significant change detected for {country} on {today_str}. Change percentage: {change_percentage:.2f}%")
            else:
                logging.warning(f"Today's category file not found: {today_category_file_path}")
    else:
        logging.error(f"Data folder for {country} does not exist: {data_folder_path}")
        return


if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
   
    # Get the current day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday']:
        countries = ['India']
    elif day in ['Thursday']:
        countries = ['UK']
    else:
        countries = []

    for country in countries:
        check_previous_dates(country, today_str)
