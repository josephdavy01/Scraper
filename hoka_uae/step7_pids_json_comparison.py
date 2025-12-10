import os
import json
import pandas as pd
from datetime import date

# Get today's date in string format
today_str = date.today().strftime('%Y-%m-%d')

#  Set your list of countries manually
countries = ['UAE']  # ← change this list to include any countries you're working with

for country in countries:
    # File paths
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_variant_product_ids.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_pid-json_comparison.csv')

    temp = []

    # Read the unique product IDs
    with open(json_file_path, 'r') as f:
        urljson = json.load(f)

    # Compare with the JSON files actually present
    for gender, categories in urljson.items():
        for category, pids in categories.items():
            if len(pids) != 0:
                json_category_path = os.path.join(json_base_path, gender, category)

                # Check if the path exists to avoid FileNotFoundError
                if os.path.exists(json_category_path):
                    cat_entries = [f for f in os.listdir(json_category_path) if f.endswith('.json')]
                else:
                    cat_entries = []

                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'Pids': len(pids),
                    'Jsons': len(cat_entries),
                    'Difference': len(pids) - len(cat_entries)
                })

    # Create and save the dataframe
    df = pd.DataFrame(temp)
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved {output_csv_path}')
