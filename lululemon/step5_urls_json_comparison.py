import os
import json
import pandas as pd
from datetime import date



def json_url_comparison(countries, today_str):
    """
    Compare product URLs with JSON data for each country and save the results to a CSV file.
    
    :param countries: List of country names.
    :param today_str: Today's date as a string in 'YYYY-MM-DD' format.
    """
    for country in countries:
        # Define file paths
        json_file_path = os.path.join(country, today_str, 'Item_urls', f'{country}_product_urls.json')
        json_base_path = os.path.join(country, today_str, 'Json_data')
        output_csv_path = os.path.join(country, today_str, 'Validation', f'{country}_url-json_comparison.csv')

        # Initialize a list to hold the comparison data
        temp = []

        # Load the product URLs JSON file
        with open(json_file_path, 'r',) as jsonData:
            urljson = json.load(jsonData)

        for gender, categories in urljson.items():
            for category, urls in categories.items():
                # Construct the path to the category's JSON files directory
                json_category_path = os.path.join(json_base_path, gender, category)

                # Check if the directory exists and has product URLs
                if len(urls) != 0 and os.path.exists(json_category_path):
                    # Count the number of JSON files in the directory
                    cat_entries = [entry for entry in os.listdir(json_category_path) if entry.endswith('.json')]

                    # Append the comparison data to the list
                    temp.append({
                        'Gender': gender,
                        'Category': category,
                        'URLs': len(urls),
                        'Jsons': len(cat_entries),
                        'Difference': len(urls) - len(cat_entries)
                    })

        # Convert the list to a DataFrame and save it as a CSV file
        df = pd.DataFrame(temp)
        df.to_csv(output_csv_path, index=False)
        print(f'Successfully saved {output_csv_path}')