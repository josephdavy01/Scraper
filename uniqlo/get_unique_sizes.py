import os
import json
import pandas as pd

countries = ["UK", "USA", "Australia", "Spain", "Canada","India"]

EXCLUDED_KEYWORDS = [
    "toy", "cap", "sock", "footsie", "backpack", "scarf", "beanie", "glove",
    "mitten", "umbrella", "bag", "hat", "belt", "sneaker", "shoe", "boot"
]

def extract_kids_baby_sizes(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = set()
    gender = data.get('gender', '').lower()
    title = str(data.get('title', '')).lower()

    if any(keyword in title for keyword in EXCLUDED_KEYWORDS):
        return results

    if gender in ['kids', 'baby']:
        sizes = data.get('sizes', [])
        for size in sizes:
            size_name = size.get('size_name')
            if size_name:
                results.add(size_name)
    return results
all_sizes = set()
skipped_count = 0

for country in countries:
    base_path = os.path.join(country, "data")
    if not os.path.exists(base_path):
        print(f"Country folder missing: {base_path}")
        continue

    print(f"\nProcessing country: {country}")

    # Find all available date folders under /data/
    date_folders = [
        d for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d)) and d.isdigit() == False
    ]

    if not date_folders:
        print(f" No date folders found for {country}")
        continue

    for date_folder in sorted(date_folders):
        date_path = os.path.join(base_path, date_folder, "Json_data")
        if not os.path.exists(date_path):
            continue

        print(f"\n Date folder: {date_folder}")

        # Traverse gender and subcategories
        for gender_folder in os.listdir(date_path):
            gender_path = os.path.join(date_path, gender_folder)
            if not os.path.isdir(gender_path):
                continue
            print(f"  Gender: {gender_folder}")

            for subcategory_folder in os.listdir(gender_path):
                subcategory_path = os.path.join(gender_path, subcategory_folder)
                if not os.path.isdir(subcategory_path):
                    continue

                for file_name in os.listdir(subcategory_path):
                    if not file_name.endswith(".json"):
                        continue
                    file_path = os.path.join(subcategory_path, file_name)

                    try:
                        sizes = extract_kids_baby_sizes(file_path)
                        if sizes:
                            all_sizes.update(sizes)
                        else:
                            skipped_count += 1
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
output_path = "kids_baby_sizes.csv"
df = pd.DataFrame(sorted(all_sizes), columns=['size_name'])
df.to_csv(output_path, index=False)

print(f"\nExtracted {len(all_sizes)} unique sizes for kids/baby products.")
print(f"Skipped {skipped_count} files (excluded or irrelevant).")
print(f"Saved to: {output_path}")
