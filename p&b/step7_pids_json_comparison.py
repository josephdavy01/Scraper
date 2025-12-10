import os
import json
import pandas as pd
from datetime import date, datetime

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

# Assign countries based on the day
if day in ['Monday', 'Wednesday', 'Friday']:
    countries = ['Australia', 'Saudi', 'Spain', 'Turkey']
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = ['UAE', 'UK', 'USA']
else:
    countries = []

# Process for each country
for country in countries:
    # Define file paths
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_ids.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_pid-json_comparison.csv')

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

    # Initialize data collector
    temp = []

    # Read the product IDs JSON
    with open(json_file_path, 'r', encoding='utf-8') as jsonData:
        urljson = json.load(jsonData)

    # Compare counts
    for gender, categories in urljson.items():
        for category, pids in categories.items():
            json_category_path = os.path.join(json_base_path, gender, category)
            if len(pids) != 0 and os.path.exists(json_category_path):
                cat_entries = os.listdir(json_category_path)
                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'Pids': len(pids),
                    'Jsons': len(cat_entries),
                    'Difference': len(pids) - len(cat_entries)
                })

    # Save results to CSV
    df = pd.DataFrame(temp)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved {output_csv_path}')
