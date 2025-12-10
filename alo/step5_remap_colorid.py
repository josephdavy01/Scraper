import os
import json

def extract_colors_from_file(file_path, color_map, counter):
    new_colors = {} 
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return color_map, counter, new_colors
        edges = data.get("data", {}).get("products", {}).get("edges")
        if not edges or not isinstance(edges, list):
            return color_map, counter, new_colors
        for edge in edges:
            node = edge.get("node")
            if not node or not isinstance(node, dict):
                continue
            variants = node.get("variants", {}).get("edges", [])
            if isinstance(variants, list):
                for v in variants:
                    v_node = v.get("node", {})
                    if not isinstance(v_node, dict):
                        continue
                    options = v_node.get("selectedOptions", [])
                    if not isinstance(options, list):
                        continue
                    for opt in options:
                        if isinstance(opt, dict) and opt.get("name", "").lower() == "color":
                            cname = opt.get("value", "").strip().lower()
                            if cname and cname not in color_map:
                                color_map[cname] = f"{counter:03d}"
                                new_colors[cname] = color_map[cname]
                                counter += 1
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return color_map, counter, new_colors

def generate_color_ids_for_all_geographies(countries, date, base_path=".", output_file="alo_color_ids.json"):
    color_map = {}
    counter = 1
    
    # Load existing color map
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    color_map = json.loads(content)
                    if color_map:
                        max_id = max(int(v) for v in color_map.values())
                        counter = max_id + 1
                        print(f"Loaded {len(color_map)} existing colors. Continuing from ID {counter:03d}")
        except json.JSONDecodeError:
            print(f"Warning: {output_file} is invalid JSON. Starting fresh.")
            color_map = {}

    total_new_colors = 0
    
    # Iterate through provided countries and the specific date
    for country in countries:
        # Assuming country keys in COUNTRIES dict match directory names (e.g., 'USA', 'UK', 'Canada')
        # If countries is a dict (like in master.py), we iterate keys. If list, iterate items.
        country_name = country if isinstance(countries, list) else country
        
        geo_path = os.path.join(base_path, country_name)
        date_folder = os.path.join(geo_path, date)
        
        if not os.path.exists(date_folder):
            print(f"Directory not found: {date_folder}")
            continue
            
        json_data_path = os.path.join(date_folder, 'Json_data')
        if not os.path.exists(json_data_path):
            print(f"Json_data directory not found in: {date_folder}")
            continue

        new_colors_in_folder = {}
        for root, _, files in os.walk(json_data_path):
            for file in files:
                if not file.endswith(".json"):
                    continue
                file_path = os.path.join(root, file)
                color_map, counter, new_colors_in_file = extract_colors_from_file(file_path, color_map, counter)
                new_colors_in_folder.update(new_colors_in_file)
        
        if new_colors_in_folder:
            print(f"\nNew colors added from {country_name}/{date}:")
            for cname, cid in new_colors_in_folder.items():
                print(f"  {cname} -> {cid}")
            total_new_colors += len(new_colors_in_folder)

    # Save updated color map
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(color_map, f, indent=4)

    print(f"\nSaved {len(color_map)} total colors to {output_file}")
    if total_new_colors > 0:
        print(f"{total_new_colors} new colors added in this run.")
    else:
        print("No new colors found in this run.")
