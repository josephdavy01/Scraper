import os
import json
from datetime import date

def get_colors(data, file_path):
    color_list = []
    found = False
    # Try extracting colors from json_data.product.options
    if "json_data" in data and "product" in data["json_data"] and "options" in data["json_data"]["product"]:
        for option in data["json_data"]["product"]["options"]:
            if option.get("name") == "Color":
                color_list.extend(option.get("values", []))
                print(f"  Colors found in json_data: {option.get('values', [])}")
                found = True
    # Try extracting colors from js_data.options
    if "js_data" in data and "options" in data["js_data"]:
        for option in data["js_data"]["options"]:
            if option.get("name") == "Color":
                color_list.extend(option.get("values", []))
                print(f"  Colors found in js_data: {option.get('values', [])}")
                found = True
    if not found:
        print(f"  No colors found in {file_path}")
        # Print available keys for debugging
        print(f"  Available keys in JSON: {list(data.keys())}")
        return []
    return color_list

def process_cids(cdict, main_folder):
    categories = os.listdir(main_folder)
    for category in categories:
        category_folder = f'{main_folder}/{category}'
        files = os.listdir(category_folder)
        for file in files:
            file_path = f'{category_folder}/{file}'
            with open(file_path, 'r', encoding='utf-8') as json_file:
                try:
                    content = json_file.read().strip()
                    if not content:
                        print(f"⚠️ Empty JSON file skipped: {file_path}")
                        continue
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error in file: {file_path}")
                    print(f"   Error: {str(e)}")
                    continue

            
            colors = get_colors(data, file_path)
            for color in colors:
                if color.lower() not in cdict.keys():
                    cno = len(cdict) + 1
                    cid = f"{cno:04}"
                    cdict[color.lower()] = cid

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-06'
    country = 'South_korea'
    
    main_folder = f'{country}/Data/{today_str}/Json_data'

    if os.path.exists(main_folder):
        cid_path = 'lewkin_cid_remapping.json'

        if os.path.exists(cid_path):
            with open(cid_path, 'r') as json_file:
                cdict = json.load(json_file)
        else:
            cdict = {}

        process_cids(cdict, main_folder)

        with open(cid_path, 'w') as f:
            json.dump(cdict, f, indent=4)

        print(f'CIDs for {country} {today_str} are updated.')
    else:
        print(f'There is no data for {today_str}')