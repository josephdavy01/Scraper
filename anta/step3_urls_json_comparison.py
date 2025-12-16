import os
import json
import pandas as pd
from datetime import date, datetime
from pathlib import Path


def compare_urls_json_comparisons():
    """Compares product URL counts vs saved JSON product data for India."""

    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['USA', 'UK']
    result_frames = {}

    for country in countries:

        # File paths
        if country == 'UK':
            json_file_path = Path(country) / today_str / "Category" / f"{country}_category_urls.json"
            json_base_path = Path(country) / today_str / "Json_data"
            output_csv_path = Path(country) / today_str / "Validation" / f"{country}_url_json_comparison.csv"
        else:
            json_file_path = Path(country) / today_str / "Item_urls" / f"{country}_product_urls.json"
            json_base_path = Path(country) / today_str / "Json_data"
            output_csv_path = Path(country) / today_str / "Validation" / f"{country}_url_json_comparison.csv"

        # Create Validation directory
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Check URL file exists
        if not json_file_path.exists():
            print(f"Missing URL file: {json_file_path}, skipping {country}.")
            continue

        # Load product URLs JSON
        with open(json_file_path, "r", encoding="utf-8") as f:
            urljson = json.load(f)

        temp = []

        # Compare JSON count vs URL count
        for gender, categories in urljson.items():
            gender_clean = str(gender).strip()

            for category, urls in categories.items():
                category_clean = str(category).strip()

                json_category_path = json_base_path / gender_clean / category_clean

                if len(urls) != 0 and json_category_path.exists():

                    json_files = [
                        f for f in os.listdir(json_category_path)
                        if f.endswith(".json")
                    ]

                    temp.append({
                        "Gender": gender_clean,
                        "Category": category_clean,
                        "URLs": len(urls),
                        "Jsons": len(json_files),
                        "Difference": len(urls) - len(json_files)
                    })

        # Convert list to DataFrame
        df = pd.DataFrame(temp)

        # Save as CSV
        df.to_csv(output_csv_path, index=False)
        result_frames[country] = df

        print(f"Successfully saved {output_csv_path}")

    return result_frames


if __name__ == "__main__":
    compare_urls_json_comparisons()
