import os
import json
import pandas as pd
from datetime import date, datetime

# Get today's date and format it
today_str = date.today().strftime('%Y-%m-%d')

# Get the day of the week
day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

if day in ['Monday', 'Wednesday', 'Friday']:
    countries = ['UK']
elif day in ['Tuesday', 'Thursday', 'Saturday']:
    countries = ['USA']
else:
    countries = []

for country in countries:
    # Define file paths
    json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
    json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
    output_csv_path = os.path.join(country, 'Data', today_str, 'Validation', f'{country}_urls-json_comparison.csv')

    # Initialize dictionaries
    temp = []

    with open(json_file_path, 'r') as jsonData:
        urljson = json.load(jsonData)

    for gender ,categories in urljson.items():
        for category, urls in categories.items():
            if len(urls)!= 0:
                json_category_path = os.path.join(json_base_path, gender, category)
                if os.path.exists(json_category_path):
                    cat_entries = os.listdir(json_category_path)
                    temp.append({'Gender' : gender, 'Category' : category, 'Pids' : len(urls), 'Jsons' : len(cat_entries), 'Difference' : len(urls)-len(cat_entries)})

    df = pd.DataFrame(temp)
    df.to_csv(output_csv_path, index=False)
    print(f'Successfully saved {output_csv_path}')