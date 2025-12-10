import json
import logging
from datetime import date
import os
from urllib.parse import urlparse, parse_qs, urlunparse

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def normalize_url(url: str) -> str:
    """
    Normalize product URLs by stripping color variant query params (?dwvar_pid_color=...)
    so we only keep one representative URL per product.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Remove any dwvar_*_color parameters
    filtered_query = {k: v for k, v in query.items() if "_color" not in k.lower()}

    # Rebuild URL without color-specific query params
    new_query = "&".join([f"{k}={v[0]}" for k, v in filtered_query.items()])
    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    return normalized.rstrip("?")  # remove trailing ? if empty


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

    all_urls = set()
    for main_cat, subcats in url_dict.items():
        if isinstance(subcats, list):  # flat list
            all_urls.update(subcats)
        elif isinstance(subcats, dict):
            for subcat, urls in subcats.items():
                all_urls.update(urls)

    logging.info(f"Total product URLs before deduplication for {country}: {len(all_urls)}")

    # Normalize to remove duplicate variants
    normalized_map = {}
    for url in all_urls:
        base_url = normalize_url(url)
        if base_url not in normalized_map:
            normalized_map[base_url] = url  # keep first occurrence

    logging.info(f"Unique products after removing color variants: {len(normalized_map)}")

    # Reconstruct dictionary using normalized URLs
    unique_data = {}
    used_urls = set()

    for main_cat, subcats in url_dict.items():
        if isinstance(subcats, list):
            normalized_list = []
            for url in subcats:
                base_url = normalize_url(url)
                if base_url in normalized_map and normalized_map[base_url] not in used_urls:
                    normalized_list.append(normalized_map[base_url])
                    used_urls.add(normalized_map[base_url])
            unique_data[main_cat] = normalized_list

        elif isinstance(subcats, dict):
            unique_data[main_cat] = {}
            for subcat, urls in subcats.items():
                normalized_list = []
                for url in urls:
                    base_url = normalize_url(url)
                    if base_url in normalized_map and normalized_map[base_url] not in used_urls:
                        normalized_list.append(normalized_map[base_url])
                        used_urls.add(normalized_map[base_url])
                unique_data[main_cat][subcat] = normalized_list

    with open(write_file_path, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, indent=4, ensure_ascii=False)

    logging.info(f"{country} unique product URLs saved to {write_file_path}")


if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    countries = ["UAE"]

    for country in countries:
        get_unique_urls(country, today_str)
