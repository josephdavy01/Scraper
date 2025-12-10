import os
import json
import logging
import pandas as pd
from datetime import date

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def compare_pid_json(countries=['India'], today_str=None):
    if not today_str:
        today_str = date.today().strftime('%Y-%m-%d')

    for country in countries:
        try:
            # Define file paths
            json_file_path = f'{country}/{today_str}/Item_urls/{country}_product_links.json'
            
            # Check if product links file exists
            if not os.path.exists(json_file_path):
                logging.warning(f"Product links file not found for {country}: {json_file_path}")
                continue

            # Load product links
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Count URLs
            url_counts = {}
            for gender, categories in json_data.items():
                for category, urls in categories.items():
                    url_counts[f"{gender}_{category}"] = len(urls)

            # Count JSON files
            json_counts = {}
            json_dir = f'{country}/{today_str}/Json_data'
            if os.path.exists(json_dir):
                for gender in os.listdir(json_dir):
                    gender_path = os.path.join(json_dir, gender)
                    if os.path.isdir(gender_path):
                        for category in os.listdir(gender_path):
                            category_path = os.path.join(gender_path, category)
                            if os.path.isdir(category_path):
                                count = len([f for f in os.listdir(category_path) if f.endswith('.json')])
                                json_counts[f"{gender}_{category}"] = count
            
            # Compare and create DataFrame
            comparison_list = []
            for key, url_count in url_counts.items():
                json_count = json_counts.get(key, 0)
                comparison_list.append({
                    'Category': key,
                    'URLs': url_count,
                    'JSON Count': json_count,
                    'Difference': url_count - json_count
                })

            df = pd.DataFrame(comparison_list)
            
            # Save comparison report
            output_dir = f'{country}/{today_str}/Validation'
            os.makedirs(output_dir, exist_ok=True)
            output_file = f'{output_dir}/{country}_url_json_comparison.csv'
            df.to_csv(output_file, index=False)
            logging.info(f"Comparison report saved for {country}: {output_file}")

        except Exception as e:
            logging.error(f"Error in comparison for {country}: {e}")

if __name__ == "__main__":
    compare_pid_json()