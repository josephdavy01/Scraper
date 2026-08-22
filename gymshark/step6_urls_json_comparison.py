import os
import json
import pandas as pd
from datetime import date, datetime

def compare_urls_json_comparisons():

    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['UK']

    for country in countries:
        # Define file paths
        json_file_path = os.path.join(country, 'Data', today_str, 'Item_urls', f'{country}_unique_product_urls.json')
        json_base_path = os.path.join(country, 'Data', today_str, 'Json_data')
        output_dir = os.path.join(country, 'Data', today_str, 'Validation')
        os.makedirs(output_dir, exist_ok=True)
        output_csv_path = os.path.join(output_dir, f'{country}_url-json_comparison.csv')

        # Initialize a list to hold the comparison data
        temp = []

        # Load the product URLs JSON file
        if not os.path.exists(json_file_path):
            print(f"Missing product urls JSON: {json_file_path}")
            continue

        with open(json_file_path, 'r', encoding='utf-8') as jsonData:
            urljson = json.load(jsonData)

        for gender, categories in urljson.items():
            json_gender_path = os.path.join(json_base_path, gender)

            if not os.path.exists(json_gender_path):
                print(f"Missing JSON folder for {gender} at {json_gender_path}")
                continue

            for category, urls in categories.items():
                json_category_path = os.path.join(json_gender_path, category)

                json_count = 0
                if os.path.exists(json_category_path):
                    json_count = len([
                        f for f in os.listdir(json_category_path)
                        if f.endswith('.json') and os.path.isfile(os.path.join(json_category_path, f))
                    ])

                temp.append({
                    'Gender': gender,
                    'Category': category,
                    'URLs': len(urls),
                    'Jsons': json_count,
                    'Difference': len(urls) - json_count
                })

        # Convert the list to a DataFrame and save it as a CSV file
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Comparison successfully saved to {output_csv_path}')
