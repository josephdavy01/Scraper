import os
import json
import pandas as pd
from datetime import date, datetime

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')
# today_str = '2025-11-21'

# Get the current day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
    countries = ['Saudi', 'UAE']
    for country in countries:
        # Define file paths
        json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
        json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
        output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_pid-json_comparison.csv')

        # Initialize a list to hold the comparison data
        temp = []

        # Load the product URLs JSON file
        with open(json_file_path, 'r') as jsonData:
            urljson = json.load(jsonData)

        for gender, pids in urljson.items():
            # Construct the path to the category's JSON files directory
            json_category_path = os.path.join(json_base_path, gender)

            # Check if the directory exists and has product URLs
            if len(pids) != 0 and os.path.exists(json_category_path):
                # Count the number of JSON files in the directory
                json_entries = [entry for entry in os.listdir(json_category_path) if entry.endswith('.json')]

                # Append the comparison data to the list
                temp.append({
                    'Gender': gender,
                    'URLs': len(pids),
                    'Jsons': len(json_entries),
                    'Json Difference': len(pids) - len(json_entries)
                })

        # Convert the list to a DataFrame and save it as a CSV file
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Successfully saved {output_csv_path}')

elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = ['India', 'UK']
    for country in countries:
        # Define file paths
        json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
        json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
        availability_base_path = os.path.join(country, 'Data', today_str, 'Availability')
        output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_url-json_comparison.csv')
        
        # Initialize a list to hold the comparison data
        temp = []

        # Load the product URLs JSON file
        with open(json_file_path, 'r') as jsonData:
            urljson = json.load(jsonData)

        for gender, pids in urljson.items():
            # Construct the path to the category's JSON files directory
            json_category_path = os.path.join(json_base_path, gender)
            availability_category_path = os.path.join(availability_base_path, gender)

            # Check if the directory exists and has product URLs
            if len(pids) != 0 and os.path.exists(json_category_path) and os.path.exists(availability_category_path):
                # Count the number of JSON files in the directory
                json_entries = [entry for entry in os.listdir(json_category_path) if entry.endswith('.json')]
                availability_entries = [entry for entry in os.listdir(availability_category_path) if entry.endswith('.json')]

                # Append the comparison data to the list
                temp.append({
                    'Gender': gender,
                    'URLs': len(pids),
                    'Jsons': len(json_entries),
                    'Json Difference': len(pids) - len(json_entries),
                    'Availability': len(availability_entries),
                    'Avail Difference': len(pids) - len(availability_entries)
                })

        # Convert the list to a DataFrame and save it as a CSV file
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Successfully saved {output_csv_path}')