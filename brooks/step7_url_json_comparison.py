import os
import json
import pandas as pd
from datetime import date

today_str = date.today().strftime("%Y-%m-%d")
# today_str = '2025-09-27'
countries = ['UK', 'USA']
for country in countries:
    print(f"\nProcessing: {country}")
    json_file_path = os.path.join(country, 'data', today_str, 'Item_urls', 'unique_variant_urls.json')
    json_base_path = os.path.join(country, 'data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'data', today_str, 'Validation', 'pid-json_comparison.csv')
    temp = []
    if not os.path.exists(json_file_path):
        print(f"variant_urls.json not found for {country}. Skipping.")
        continue
    with open(json_file_path, 'r', encoding='utf-8') as f:
        urljson = json.load(f)
    for gender, categories in urljson.items():
        gender_path = os.path.join(json_base_path, gender)
        for category, pids in categories.items():
            if not pids:
                continue
            if country == "India":
                normalized_category = category.replace(" ", "_")
            else:
                normalized_category = category
            json_category_path = os.path.join(gender_path, normalized_category)
            if os.path.exists(json_category_path):
                cat_entries = [f for f in os.listdir(json_category_path) if f.endswith('.json')]
            else:
                cat_entries = []
                print(f"Missing folder: {json_category_path}")
            temp.append({
                'Gender': gender,
                'Category': category,
                'Pids': len(pids),
                'Jsons': len(cat_entries),
                'Difference': len(pids) - len(cat_entries)
            })
    df = pd.DataFrame(temp)
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    df.to_csv(output_csv_path, index=False)
    print(f"Saved: {output_csv_path}")
