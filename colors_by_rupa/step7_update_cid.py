import os
import json
from datetime import date, datetime


def run_cid_mapping_tts():

    # ------------------ DATE CHECK ------------------ #
    today_str = date.today().strftime('%Y-%m-%d')
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    countries = ['india']

    # ------------------ Helper Function ------------------ #

    def process_cids(cdict, main_folder):
        if not os.path.exists(main_folder):
            print(f"Folder not found: {main_folder}")
            return

        genders = os.listdir(main_folder)

        for gender in genders:
            gender_folder = f"{main_folder}/{gender}"
            if not os.path.isdir(gender_folder):
                continue

            categories = os.listdir(gender_folder)
            for category in categories:
                category_folder = f"{gender_folder}/{category}"
                if not os.path.isdir(category_folder):
                    continue

                for file in os.listdir(category_folder):
                    if not file.endswith(".json"):
                        continue

                    file_path = f"{category_folder}/{file}"

                    try:
                        with open(file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)

                        # ---------- CID mapping ----------
                        variants = data.get("variants")
                        if variants:
                            for variant in variants:
                                color = variant.get("color").replace("      ","").replace("\n","")  
                                if color:
                                    color_key = color.lower()
                                    if color_key not in cdict:
                                        cid = f"{len(cdict) + 1:03}"
                                        cdict[color_key] = cid

                    except Exception as e:
                        print(f"Error reading JSON → {file_path} | {e}")

    # ------------------ MAIN EXECUTION ------------------ #

    cid_path = 'colors_cid_remapping.json'
    # Load CID mapping
    cdict = {}
    if os.path.exists(cid_path):
        try:
            with open(cid_path, 'r') as f:
                cdict = json.load(f)
        except json.JSONDecodeError:
            cdict = {}

    # Process each country
    for country in countries:
        print(f"Processing CIDs for {country}...")

        main_folder = f"{country}/{today_str}/Json_data"
        process_cids(cdict, main_folder)

        print(f"CIDs for {country} {today_str} updated.")

    # Save updated CID mapping
    with open(cid_path, 'w') as f:
        json.dump(cdict, f, indent=4)

    print("CID remapping completed for all valid countries.")


# Optional direct run
if __name__ == "__main__":
    run_cid_mapping_tts()
