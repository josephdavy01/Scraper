import os
import json
import pandas as pd
from datetime import date,datetime

today_str = date.today().strftime('%Y-%m-%d')
today_str = '2025-11-22'
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday','Wednesday', 'Friday']:
    countries = ['INDIA']
else:        
    countries = ['UK','UAE']

for country in countries:
    # Define file paths
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_url-json_comparison.csv')

    temp = []

    with open(json_file_path, 'r') as jsonData:
        urljson = json.load(jsonData)

    for gender, categories in urljson.items():
        for category, urls in categories.items():
            # Construct the path to the category's JSON files directory
            json_category_path = os.path.join(json_base_path, gender, category)

            # Check if the directory exists and has product URLs
            if len(urls) != 0 and os.path.exists(json_category_path):
                # Count the number of JSON files in the directory
                cat_entries = [entry for entry in os.listdir(json_category_path) if entry.endswith('.json')]

                # Append the comparison data to the list
                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'URLs': len(urls),
                    'Jsons': len(cat_entries),
                    'Difference': len(urls) - len(cat_entries)
                })

    # Convert the list to a DataFrame and save it as a CSV file
    df = pd.DataFrame(temp)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved {output_csv_path}')