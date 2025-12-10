import os
import json
import pandas as pd
from datetime import date

def compare_url_json_counts(countries, base_date=None, execution_config=None):
    # Use provided date or today's date
    today_str = base_date if base_date else date.today().strftime('%Y-%m-%d')

    for country in countries:

        # Define file paths
        json_file_path = os.path.join(country, today_str, 'Items_urls',
                                      f'{country}_unique_product_urls.json')

        json_base_path = os.path.join(country, today_str, 'Json_data')

        output_csv_path = os.path.join(country, today_str, 'Validation',
                                       f'{country}_url_json_comparison.csv')

        # Ensure validation folder exists
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

        # Initialize comparison list
        temp = []

        # Check if JSON file exists
        if not os.path.exists(json_file_path):
            print(f'Error: JSON file not found: {json_file_path}')
            continue

        # Load the JSON with URLs
        try:
            with open(json_file_path, 'r') as jsonData:
                urljson = json.load(jsonData)
        except Exception as e:
            print(f'Error loading JSON file {json_file_path}: {e}')
            continue

        # Walk through gender → category → url list
        for gender, categories in urljson.items():
            for category, urls in categories.items():

                # Path for the category JSON files
                json_category_path = os.path.join(json_base_path, gender, category)

                if len(urls) != 0 and os.path.exists(json_category_path):

                    # Count JSON files inside category folder
                    cat_entries = [
                        entry for entry in os.listdir(json_category_path)
                        if entry.endswith('.json')
                    ]

                    # Append comparison row
                    temp.append({
                        'Gender': gender,
                        'Category': category,
                        'URLs': len(urls),
                        'Jsons': len(cat_entries),
                        'Difference': len(urls) - len(cat_entries)
                    })

        # Convert to DataFrame & save
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Successfully saved comparison CSV: {output_csv_path}')

    return True

if __name__ == '__main__':
    compare_url_json_counts(['India'])  
