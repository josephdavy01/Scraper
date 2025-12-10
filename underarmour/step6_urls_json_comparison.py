import os
import json
import pandas as pd
from datetime import date, datetime

def count_json_files(path):
    """Counts the number of JSON files in a directory and its subdirectories."""
    count = 0
    if os.path.exists(path):
        for _, _, files in os.walk(path):
            for file in files:
                if file.endswith('.json'):
                    count += 1
    return count

def compare_urls_and_jsons(country, today_str, availability=False):
    if country == 'India':
        json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'unique_product_ids.json')
    else:
        json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'unique_product_urls.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_url_json_comparison.csv')

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

    temp = []

    try:
        with open(json_file_path, 'r') as jsonData:
            urljson = json.load(jsonData)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading {json_file_path}: {e}")
        return

    for gender, categories in urljson.items():
        for category, purls in categories.items():
            if len(purls) != 0:
                json_category_path = os.path.join(json_base_path, gender, category)

                if os.path.exists(json_category_path):
                    cat_entries = os.listdir(json_category_path)
                    json_count = len(cat_entries)
                else:
                    print(f"Warning: Missing JSON directory: {json_category_path}")
                    json_count = 0

                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'Purls': len(purls),
                    'Jsons': json_count,
                    'Difference': len(purls) - json_count
                })

    df = pd.DataFrame(temp)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved {output_csv_path}')

def main():
    """
    Main function to run the script.
    """
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['India', 'UAE']
        for country in countries:
            compare_urls_and_jsons(country, today_str)
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['UK', 'USA']
        for country in countries:
            compare_urls_and_jsons(country, today_str, availability=True)

if __name__ == "__main__":
    main()