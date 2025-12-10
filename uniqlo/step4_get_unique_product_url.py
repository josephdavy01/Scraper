import json
import os
from datetime import date, datetime

def remove_global_duplicates(read_product_file_path, write_uproduct_file_path):
    with open(read_product_file_path, "r", encoding="utf-8") as f:
        urls_data = json.load(f)
    seen_urls = set()
    deduped_urls = {}
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
    os.makedirs(os.path.dirname(write_uproduct_file_path), exist_ok=True)
    with open(write_uproduct_file_path, "w", encoding="utf-8") as f:
        json.dump(deduped_urls, f, indent=2, ensure_ascii=False)
    print(f"Saved deduplicated URLs to {write_uproduct_file_path}")

if __name__ == "__main__":
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    weekday = today.weekday()  # 0 = Monday, 6 = Sunday

    # Define processing rules
    uk_usa_days = {0, 2, 4}       # Monday, Wednesday, Friday
    others_days = {1, 3, 5}       # Tuesday, Thursday, Saturday

    country_groups = {
        "group_uk_usa": ["UK", "USA","India"],
        "group_others": ["Australia", "Canada", "Spain"]
    }

    if weekday in uk_usa_days:
        selected_countries = country_groups["group_uk_usa"]
    elif weekday in others_days:
        selected_countries = country_groups["group_others"]
    else:
        print("No processing scheduled for Sunday.")
        selected_countries = []

    for country in selected_countries:
        base_dir = f'{country}/Data/{today_str}/Item_urls'
        os.makedirs(base_dir, exist_ok=True)
        read_path = f'{base_dir}/product_urls.json'
        write_path = f'{base_dir}/unique_product_url.json'
        if os.path.exists(read_path):
            remove_global_duplicates(read_product_file_path=read_path, write_uproduct_file_path=write_path)
        else:
            print(f"[{country}] Input file not found: {read_path}")
