import os
import json
import pandas as pd
from datetime import date, datetime

# Define the country
country = 'India'  

# Get today's date and format it
today = date.today()
today_str = today.strftime('%Y-%m-%d')

# Get the day of the week (optional use)
day = today.strftime('%A')

# Define file paths
json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_product_urls.json')
json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_pid-json_comparison.csv')

# Initialize list to hold data
temp = []

# Check if input JSON file exists
if not os.path.exists(json_file_path):
    print(f"Error: JSON file not found at {json_file_path}")
else:
    with open(json_file_path, 'r') as jsonData:
        urljson = json.load(jsonData)

    for gender, categories in urljson.items():
        for category, pids in categories.items():
            if pids:
                json_category_path = os.path.join(json_base_path, gender, category)
                if os.path.exists(json_category_path):
                    cat_entries = os.listdir(json_category_path)
                    json_count = len(cat_entries)
                else:
                    json_count = 0

                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'Pids': len(pids),
                    'Jsons': json_count,
                    'Difference': len(pids) - json_count
                })

    # Create and save DataFrame
    df = pd.DataFrame(temp)
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved: {output_csv_path}')
