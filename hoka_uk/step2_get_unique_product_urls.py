import json
import logging
from datetime import date
import os

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def normalize_url(url: str) -> str:
    """Return base product URL (strip off color variant)."""
    if "?dwvar_" in url and "_color=" in url:
        return url.split("?")[0]   # base URL only
    return url

def get_unique_urls(country, today_str):
    base_path = f"{country}/Data/{today_str}/Item_urls"
    read_file_path = os.path.join(base_path, f"{country}_product_ids.json")
    write_file_path = os.path.join(base_path, f"{country}_unique_product_ids.json")

    try:
        with open(read_file_path, "r", encoding="utf-8") as f:
            url_dict = json.load(f)
    except FileNotFoundError:
        logging.warning(f"No product file found for {country} at {read_file_path}")
        return

    seen = set()      # base URLs we've already taken
    unique_data = {}  # rebuilt structure with deduplicated URLs

    for main_cat, subcats in url_dict.items():
        if isinstance(subcats, list):
            unique_list = []
            for url in subcats:
                base = normalize_url(url)
                if base not in seen:
                    seen.add(base)
                    unique_list.append(url)  # keep one representative
            unique_data[main_cat] = unique_list

        elif isinstance(subcats, dict):
            unique_data[main_cat] = {}
            for subcat, urls in subcats.items():
                unique_list = []
                for url in urls:
                    base = normalize_url(url)
                    if base not in seen:
                        seen.add(base)
                        unique_list.append(url)  # keep one representative
                unique_data[main_cat][subcat] = unique_list

        else:
            logging.warning(f" Unknown format in {main_cat}, skipping...")

    with open(write_file_path, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, indent=4, ensure_ascii=False)

    logging.info(f" {country} unique product URLs saved to {write_file_path}")


if __name__ == "__main__":
    today_str = date.today().strftime('%Y-%m-%d')
    
    countries = ['UK']
    for country in countries:
        get_unique_urls(country, today_str)
