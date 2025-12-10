import os
import json
from pathlib import Path

# Define root directory and geographies
ROOT_DIR = Path(".")  # Change if needed
GEOGRAPHIES = ["India", "Saudi", "UAE", "UK", "USA"]

# Recursive function to extract all "label" fields from JSON objects
def extract_labels(obj):
    labels = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "label" and isinstance(value, str):
                labels.add(value)
            else:
                labels.update(extract_labels(value))
    elif isinstance(obj, list):
        for item in obj:
            labels.update(extract_labels(item))
    return labels


# Main logic
def collect_all_labels():
    all_results = {}

    for geo in GEOGRAPHIES:
        print(f"\n--- Processing geography: {geo} ---")
        geo_path = ROOT_DIR / geo / "Data"
        geo_labels = set()

        if not geo_path.exists():
            print(f"Skipping {geo}: 'Data' directory not found.")
            continue

        # Iterate through each date folder
        for date_folder in geo_path.iterdir():
            if not date_folder.is_dir():
                continue

            print(f"Checking date folder: {date_folder.name}")
            json_data_path = date_folder / "Json_data"
            if not json_data_path.exists():
                print(f"No 'Json_data' folder found in {date_folder}")
                continue

            # Traverse maincategory/subcategory folders
            for main_cat in json_data_path.glob("*"):
                if not main_cat.is_dir():
                    continue
                print(f"  Main category: {main_cat.name}")

                for sub_cat in main_cat.glob("*"):
                    if not sub_cat.is_dir():
                        continue
                    print(f"    Subcategory: {sub_cat.name}")

                    json_files = list(sub_cat.glob("*.json"))
                    print(f"    Found {len(json_files)} JSON files in {sub_cat.name}")

                    for json_file in json_files:
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            labels = extract_labels(data)
                            if labels:
                                geo_labels.update(labels)
                        except Exception as e:
                            print(f"    Error reading {json_file}: {e}")

        print(f"Finished processing {geo}. Total unique labels found: {len(geo_labels)}")
        all_results[geo] = sorted(geo_labels)

    # Save results
    output_path = ROOT_DIR / "all_labels_by_geography.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)

    print("\nAll geographies processed successfully.")
    print(f"Labels extracted and saved to: {output_path}")


if __name__ == "__main__":
    collect_all_labels()
