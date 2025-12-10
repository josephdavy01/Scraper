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
    """
    Compares the number of URLs from a JSON file with the number of
    JSON files in a directory and optionally checks availability data.
    """
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
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

    for gender, pids in urljson.items():
        json_category_path = os.path.join(json_base_path, gender)
        
        if not pids:
            continue

        json_entries_count = count_json_files(json_category_path)
        
        data = {
            'Gender': gender,
            'URLs': len(pids),
            'Jsons': json_entries_count,
            'Json Difference': len(pids) - json_entries_count
        }

        if availability:
            availability_base_path = os.path.join(country, 'Data', today_str, 'Availability')
            availability_category_path = os.path.join(availability_base_path, gender)
            availability_entries_count = count_json_files(availability_category_path)
            data['Availability'] = availability_entries_count
            data['Avail Difference'] = len(pids) - availability_entries_count
        
        temp.append(data)

    if temp:
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Successfully saved {output_csv_path}')

def main():
    """
    Main function to run the script.
    """
    today_str = '2025-11-19'
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['UK','USA']
        for country in countries:
            compare_urls_and_jsons(country, today_str)
    elif day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['India']
        for country in countries:
            compare_urls_and_jsons(country, today_str, availability=True)

if __name__ == "__main__":
    main()