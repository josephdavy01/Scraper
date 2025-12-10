import os
import json
from datetime import date

def extract_unique_titles(country, today_date):
    """
    Extract unique product titles from JSON files and assign stable unique IDs.
    New titles get the next available number; existing titles keep their ID.
    Output file is saved in the current working directory (where the script runs).
    """
    json_folder = os.path.join(country, "Data", today_date, "Json_data")
    output_path = "unique_titles_with_ids.json"  # Save in current directory

    # Load existing IDs if the file exists
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            unique_titles = json.load(f)
        existing_ids = [int(v) for v in unique_titles.values()]
        counter = max(existing_ids) + 1 if existing_ids else 1
    else:
        unique_titles = {}
        counter = 1

    if not os.path.exists(json_folder):
        print("❌ ERROR: Folder not found:", json_folder)
        return

    # Walk through JSON files
    for root, dirs, files in os.walk(json_folder):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    structured_data = data.get("structured_data", {})
                    main_title = structured_data.get("name")
                    if main_title and main_title not in unique_titles:
                        unique_titles[main_title] = f"{counter:05d}"
                        counter += 1

                    variants = structured_data.get("variants", [])
                    for variant in variants:
                        variant_title = variant.get("name")
                        if variant_title and variant_title not in unique_titles:
                            unique_titles[variant_title] = f"{counter:05d}"
                            counter += 1

                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")

    # Save updated titles in the current working directory
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_titles, f, indent=4, ensure_ascii=False)

    print("✅ Saved unique titles to:", os.path.abspath(output_path))
    return unique_titles
today_str = date.today().strftime('%Y-%m-%d')
# today_str ='2025-12-09'
# Example run
extract_unique_titles("India", today_str)
