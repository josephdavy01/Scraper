import os
import json
from datetime import date


def get_color_size(color, size):
    """Fix swapped color/size conditions and return corrected color."""
    color = color.replace("'", "").strip()

    swap_values = [
        '100/40', '100X40', '105/42', '105X42', '110/116', '110/44', '110X44', '115/46', '115x46', '120/48', '122/128',
        '134/140', '146/152', '158/164', '170', '25', '25/30', '25/32', '25/34', '26', '26/30', '26/32', '26/34',
        '27', '27/30', '27/32', '27/34', '27x32', '28', '28/30', '28/32', '28/34', '28X32', '29', '29/30', '29/32',
        '29/34', '29/36', '29X32', '29X34', '2XL', '30', '30/30', '30/32', '30/34', '30/36', '30X32', '30X34', '31',
        '31/30', '31/32', '31/34', '31/36', '31X32', '31X34', '32', '32/30', '32/32', '32/34', '32/36', '32X30',
        '32X32', '32X34', '33', '33/30', '33/32', '33/34', '33/36', '33X32', '33X34', '34', '34/30', '34/32',
        '34/34', '34/36', '34X30', '34X32', '34X34', '35', '35/30', '35/32', '35/34', '35/36', '35X32', '35X34',
        '36', '36/30', '36/32', '36/34', '36/36', '36X30', '36X32', '36X34', '37', '38', '38/30', '38/32', '38/34',
        '38/36', '38X32', '38X34', '3XL', '40', '40 30', '40-42', '40/30', '40/32', '40/34', '40/36', '40X32',
        '40X34', '41', '42', '42/30', '42/32', '42/34', '42/36', '42X32', '42X34', '43', '43-45', '44', '44 30',
        '44/30', '44/32', '44/34', '44/36', '44X32', '44X32-GAN', '44X34', '45', '46', '46 30', '46 36', '46/32',
        '46/34', '46/36', '46X32', '46X34', '46x32', '46x34', '48', '48 36', '48/34', '4XL', '50', '52', '54', '56',
        '58', '5XL', '60', '62', '64', '66', '6XL', '75/30', '80/32', '80X32', '85/34', '85X34', '90/36', '90X36',
        '92', '95/38', '95X38', '98/104', 'L', 'L-XL', 'M', 'M-L', 'ONESIZE', 'OS', 'One Size', 'Onesize', 'S',
        'S-M', 'XL', 'XS', 'XS-S', 'XXL', 'XXS', 'XXXL'
    ]

    if color in swap_values:
        return size.lower().strip()

    return color.lower().strip()


def process_pids(cdict, main_folder):
    """Scan all json files and map new color IDs."""
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
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                variants = data.get("variants", [])
                if not variants:
                    continue

                variant = variants[0]
                color = variant.get("option1")
                size = variant.get("option2")

                if not color:
                    continue

                color = get_color_size(color, size)

                if color not in cdict:
                    cid = f"{len(cdict) + 1:03}"
                    cdict[color] = cid


def run_cid_mapping(country, today_date):
    main_folder = f"{country}/{today_date}/Json_data"

    cid_path = "gant_cid_remapping.json"

    
    # Load old mapping
    cdict = {}
    if os.path.exists(cid_path):
        with open(cid_path, "r") as f:
            cdict = json.load(f)

    # Process JSON → update CIDs
    process_pids(cdict, main_folder)

    # Save updated CID map
    with open(cid_path, "w") as f:
        json.dump(cdict, f, indent=4)

    print(f"CIDs updated successfully for {country} on {today_date}")


if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    run_cid_mapping("UAE", today_str)
