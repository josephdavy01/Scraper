import os
import json
from pathlib import Path
from datetime import datetime

# Define the base directory and date
today_str = datetime.today().strftime("%Y-%m-%d")   # e.g., "2025-09-26"
base_output = f"South_korea/Data/{today_str}/Json_data"

# Function to collect all colors from JSON files in a directory (without uniquing yet)
def collect_colors(directory):
    colors_list = []
    print(f"\nChecking directory: {directory}")
    # Check if directory exists
    if not os.path.exists(directory):
        print(f"Directory does not exist: {directory}")
        return colors_list
    # Get list of JSON files
    files = list(Path(directory).glob("*.json"))
    print(f"Found {len(files)} JSON files in {directory}")
    if not files:
        print("No JSON files found in the directory.")
    # Process each JSON file
    for file_path in files:
        print(f"Processing file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                found = False
                # Try extracting colors from json_data.product.options
                if "json_data" in data and "product" in data["json_data"] and "options" in data["json_data"]["product"]:
                    for option in data["json_data"]["product"]["options"]:
                        if option.get("name") == "Color":
                            colors_list.extend(option.get("values", []))
                            print(f"  Colors found in json_data: {option.get('values', [])}")
                            found = True
                # Try extracting colors from js_data.options
                if "js_data" in data and "options" in data["js_data"]:
                    for option in data["js_data"]["options"]:
                        if option.get("name") == "Color":
                            colors_list.extend(option.get("values", []))
                            print(f"  Colors found in js_data: {option.get('values', [])}")
                            found = True
                if not found:
                    print(f"  No colors found in {file_path}")
                    # Print available keys for debugging
                    print(f"  Available keys in JSON: {list(data.keys())}")
        except json.JSONDecodeError as e:
            print(f"  Error reading JSON file {file_path}: {e}")
        except PermissionError:
            print(f"  Permission denied for file: {file_path}")
        except Exception as e:
            print(f"  Error processing file {file_path}: {e}")
    return colors_list

# Normalization function
def normalize_color(color):
    color = color.strip().replace("_", " ")
    if color.lower() == "whtie":
        color = "White"
    return color.lower()

# Collect colors from all category directories
print("Starting color extraction...")
all_original_colors = []
category_dirs = [d for d in Path(base_output).iterdir() if d.is_dir()]  # Get all subdirectories
for category_dir in category_dirs:
    category_colors = collect_colors(category_dir)
    all_original_colors.extend(category_colors)

# Remove duplicates by converting to set (originals)
all_original_colors = list(set(all_original_colors))

# Normalize and merge
color_map = {}
for original in all_original_colors:
    norm = normalize_color(original)
    if norm not in color_map:
        color_map[norm] = norm.title()  # Standardize to title case

# Sort the normalized colors (case-insensitive)
all_colors = sorted(color_map.values(), key=str.lower)

# Generate color IDs (0001, 0002, 0003, etc.)
color_id_map = {color: f"{i+1:04d}" for i, color in enumerate(all_colors)}

# Print the color-to-ID mapping
print("\nColor ID Mapping:")
if color_id_map:
    for color, color_id in color_id_map.items():
        print(f"Color: {color}, ID: {color_id}")
else:
    print("No colors found. Color ID mapping is empty.")

# Optionally, save the mapping to a JSON file
output_file = f"color_id_mapping.json"

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(color_id_map, f, indent=4)
print(f"Color ID mapping saved to {output_file}")