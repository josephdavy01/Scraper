import os
import json
from pathlib import Path
from datetime import datetime

# Define the paths
today_str = datetime.today().strftime("%Y-%m-%d")  # Replace if needed
women_output = f"Korea/Data/{today_str}/Json_data/women/clothing"
men_output = f"Korea/Data/{today_str}/Json_data/men/clothing"

# File to persist color-ID mapping
output_file = "color_id_mapping.json"

# Load existing color ID mapping if it exists
if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        color_id_map = json.load(f)
else:
    color_id_map = {}

# Reverse map to track used IDs (optional, but good for validation)
used_ids = set(color_id_map.values())

# Function to collect distinct colors from JSON files
def get_distinct_colors(directory):
    colors = set()
    print(f"\nChecking directory: {directory}")
    if not os.path.exists(directory):
        print(f"Directory does not exist: {directory}")
        return colors
    files = list(Path(directory).glob("*.json"))
    print(f"Found {len(files)} JSON files in {directory}")
    for file_path in files:
        print(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if "available_colors" in data:
                    if data["available_colors"]:
                        colors.update(data["available_colors"])
                        print(f"  Colors found: {data['available_colors']}")
                    else:
                        print(f"  'available_colors' is empty in {file_path}")
                else:
                    print(f"  No 'available_colors' field in {file_path}")
                    print(f"  Available keys in JSON: {list(data.keys())}")
        except json.JSONDecodeError as e:
            print(f"  Error reading JSON file {file_path}: {e}")
        except PermissionError:
            print(f"  Permission denied for file: {file_path}")
        except Exception as e:
            print(f"  Error processing file {file_path}: {e}")
    return colors

# Start processing
print("Starting color extraction...")
women_colors = get_distinct_colors(women_output)
men_colors = get_distinct_colors(men_output)

# Combine all colors found today
all_colors_today = women_colors.union(men_colors)

# Assign new IDs only to new colors
next_id = max([int(v) for v in color_id_map.values()], default=0) + 1

for color in sorted(all_colors_today):  # Sorted to ensure consistency
    if color not in color_id_map:
        new_id = f"{next_id:03d}"
        color_id_map[color] = new_id
        print(f"New color added: {color} => {new_id}")
        next_id += 1
    else:
        print(f"Existing color found: {color} => {color_id_map[color]}")

# Save updated color ID mapping
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(color_id_map, f, indent=4, ensure_ascii=False)

print(f"\nColor ID mapping saved to {output_file}")

# Optional: Print full mapping
print("\nFinal Color ID Mapping:")
for color, color_id in sorted(color_id_map.items(), key=lambda x: int(x[1])):
    print(f"Color: {color}, ID: {color_id}")
