import json
import os
from datetime import date

def remove_global_duplicates(read_product_file_path, write_uproduct_file_path):
    # Load the original product URL data
    with open(read_product_file_path, "r", encoding="utf-8") as f:
        urls_data = json.load(f)

    seen_urls = set()
    deduped_urls = {}

    # Iterate through main categories and subcategories
    for main_cat, subcats in urls_data.items():
        deduped_urls[main_cat] = {}
        for subcat_name, urls in subcats.items():
            before_url_count = len(urls)
            unique_urls = []

            for url in urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_urls.append(url)

            after_url_count = len(unique_urls)
            print(f"{main_cat} -> {subcat_name}: URLs before={before_url_count}, after={after_url_count}")

            deduped_urls[main_cat][subcat_name] = unique_urls

    # Write deduplicated data to new JSON file
    with open(write_uproduct_file_path, "w", encoding="utf-8") as f:
        json.dump(deduped_urls, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved deduplicated URLs to: {write_uproduct_file_path}")

if __name__ == "__main__":
    today_str = '2025-10-30'
    # country = 'India'
    brand='levis'
    countries = ['UK']
    for country in countries:
        brand_name=f'{brand}_{country}'
    base_dir = os.path.join(countries, 'data', today_str, 'item_urls')
    os.makedirs(base_dir, exist_ok=True)

    read_path = os.path.join(base_dir, 'All_Product_URLs_by_Category.json')
    write_path = os.path.join(base_dir, 'unique_product_url.json')

    remove_global_duplicates(
        read_product_file_path=read_path,
        write_uproduct_file_path=write_path,
    )
