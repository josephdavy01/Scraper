import os
import json
from datetime import date

def extract_unique_colors_stable_4digit(country, today_date):
    """
    Extract unique colors from JSON files in a folder and assign stable 4-digit IDs.
    Existing colors keep their ID. New colors get the next available ID.
    Output is saved in the main folder (where the script is run).
    """
    base_folder = os.path.join(country, "Data", today_date, "Json_data")
    if not os.path.exists(base_folder):
        print("❌ ERROR: Folder not found:", base_folder)
        return

    # Output in the main folder
    output_path = os.path.join(os.getcwd(), "unique_colors_with_ids.json")

    # Load existing colors if file exists
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            unique_colors = json.load(f)
        counter = max(int(v) for v in unique_colors.values()) + 1 if unique_colors else 1
    else:
        unique_colors = {}
        counter = 1

    # Walk recursively through all subfolders
    for root, dirs, files in os.walk(base_folder):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract colors from variants
                    variants = data.get("structured_data", {}).get("variants", [])
                    for variant in variants:
                        color = variant.get("color")
                        if color and color not in unique_colors:
                            unique_colors[color] = f"{counter:04d}"  # 4-digit ID
                            counter += 1

                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")

    # Save updated colors
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_colors, f, indent=4, ensure_ascii=False)

    print("✅ Saved unique colors to:", output_path)
    return unique_colors
today_str = date.today().strftime('%Y-%m-%d')
# today_str ='2025-12-09'
# Example run
extract_unique_colors_stable_4digit("India", today_str)
