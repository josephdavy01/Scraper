import os
import json
import pandas as pd
from datetime import date, datetime

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# List of countries to process
countries = ['UK', 'India','USA']

for country in countries:
    print(f"\nProcessing: {country}")

    # Define file paths
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_pid-json_comparison.csv')

    # Prepare results list
    rows = []

    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        print(f"Input file missing: {json_file_path}")
        continue

    with open(json_file_path, 'r', encoding='utf-8') as fh:
        urljson = json.load(fh)

    for gender, second_level in urljson.items():
        sample_val = None
        if isinstance(second_level, dict) and len(second_level) > 0:
            sample_val = next(iter(second_level.values()))

        if isinstance(sample_val, list):
            for category, pids in second_level.items():
                pids_count = len(pids) if isinstance(pids, list) else 0
                json_category_path = os.path.join(json_base_path, gender, category)
                json_count = len([f for f in os.listdir(json_category_path) if f.lower().endswith('.json')]) if os.path.exists(json_category_path) else 0
                rows.append({
                    'Gender': gender,
                    'Brand': '',
                    'Category': category,
                    'Pids': pids_count,
                    'Jsons': json_count,
                    'Difference': pids_count - json_count
                })

        elif isinstance(sample_val, dict):
            for brand, categories in second_level.items():
                if not isinstance(categories, dict):
                    continue
                for category, pids in categories.items():
                    pids_count = len(pids) if isinstance(pids, list) else 0
                    json_category_path = os.path.join(json_base_path, gender, brand, category)
                    json_count = len([f for f in os.listdir(json_category_path) if f.lower().endswith('.json')]) if os.path.exists(json_category_path) else 0
                    rows.append({
                        'Gender': gender,
                        'Brand': brand,
                        'Category': category,
                        'Pids': pids_count,
                        'Jsons': json_count,
                        'Difference': pids_count - json_count
                    })

        else:
            # Handle unexpected or empty structure
            if isinstance(second_level, dict):
                for category, pids in second_level.items():
                    pids_count = len(pids) if isinstance(pids, list) else 0
                    json_category_path = os.path.join(json_base_path, gender, category)
                    json_count = len([f for f in os.listdir(json_category_path) if f.lower().endswith('.json')]) if os.path.exists(json_category_path) else 0
                    rows.append({
                        'Gender': gender,
                        'Brand': '',
                        'Category': category,
                        'Pids': pids_count,
                        'Jsons': json_count,
                        'Difference': pids_count - json_count
                    })

    # Save results
    if rows:
        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
        df.to_csv(output_csv_path, index=False)
        print(f"Successfully saved: {output_csv_path}")
    else:
        print("No rows to write. Check the JSON structure.")
