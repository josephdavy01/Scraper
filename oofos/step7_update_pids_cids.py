import os
import json
from datetime import date


def update_pid(pdict, product_title):
    """Update or create PID for a product title."""
    if product_title not in pdict:
        pno = len(pdict) + 1
        pid = f"oof{pno:07}"
        pdict[product_title] = pid
        print(f'New entry {pid}: {product_title}')


def update_cid(cdict, color):
    """Update color ID mapping."""
    if color not in cdict:
        cno = len(cdict) + 1
        cid = f"{cno:03}"
        cdict[color] = cid
        print(f'New color entry {cid}: {color}')


def process_pids_cids(cdict, pdict, main_folder):
    pop_keys = ["email Signature","Gift Card","Try Before You Buy"]
    genders = os.listdir(main_folder)
    for gender in genders:
        gender_folder = os.path.join(main_folder, gender)
        if not os.path.isdir(gender_folder):
            continue

        categories = os.listdir(gender_folder)
        for category in categories:
            category_folder = os.path.join(gender_folder, category)
            if not os.path.isdir(category_folder):
                continue

            files = os.listdir(category_folder)
            for file in files:
                file_path = os.path.join(category_folder, file)

                if not file.endswith(".json"):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    product_title = data.get('product', {}).get('title').split('-')[0].split('–')[0].split("+")[0].strip()
                    if product_title in pop_keys:
                        continue
                    update_pid(pdict, product_title)
                    # Extract color variants
                    variants = data.get('product', {}).get("variants", [])
                    if isinstance(variants, list):
                        for variant in variants:
                            color_name = variant.get("option2")
                            if color_name:
                                update_cid(cdict, color_name)

                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")


def safe_load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: {path} is invalid or empty. Resetting to empty JSON.")
        return {}
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return {}


if __name__ == "__main__":
    country_list = ['UK', 'USA']

    for country in country_list:
        data_folder = os.path.join(country, 'Data')
        if not os.path.exists(data_folder):
            print(f"No data folder found for {country}")
            continue

        dates = os.listdir(data_folder)
        for today_str in dates:
            main_folder = os.path.join(data_folder, today_str, 'Json_data')

            if os.path.exists(main_folder):
                cid_path = 'oofos_cid_remapping.json'
                pid_path = 'oofos_pid_remapping.json'

                # Safe load (no crash if file empty or invalid)
                cdict = safe_load_json(cid_path)
                pdict = safe_load_json(pid_path)

                #  Process all product data
                process_pids_cids(cdict, pdict, main_folder)

                # Always save updated data back to files
                with open(cid_path, 'w', encoding='utf-8') as f:
                    json.dump(cdict, f, indent=4, ensure_ascii=False)
                with open(pid_path, 'w', encoding='utf-8') as f:
                    json.dump(pdict, f, indent=4, ensure_ascii=False)

                print(f'CIDs and PIDs for {country} {today_str} are updated.')
            else:
                print(f'There is no data for {country} {today_str}')