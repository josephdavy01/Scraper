import json
import logging
from datetime import date, datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'

    with open(read_file_path, encoding='utf-8') as json_file:
        url_dict = json.load(json_file)

    all_urls = set()

    for gender, categories in url_dict.items():
        for category, urls in categories.items():
            for url in urls:
                all_urls.add(url)

    logging.info(f"Total unique urls found for {country}: {len(all_urls)}")

    temp = {}

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for category, urls in categories.items():
            curls = all_urls.intersection(set(urls))
            all_urls = all_urls - set(urls)
            urls = list(curls)
            temp[gender][category] = urls

    with open(write_file_path, "w", encoding='utf-8') as outfile:
        json.dump(temp, outfile, indent=4)

    logging.info(f"{country} unique product urls saved to {write_file_path}")


def get_unique_urls_uae(country, today_str):
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    read_file_path = f'{base_dir}/{country}_product_urls.json'
    write_file_path = f'{base_dir}/{country}_unique_product_urls.json'

    if not os.path.exists(read_file_path):
        logging.error(f"Input file not found: {read_file_path}")
        return

    try:
        with open(read_file_path, 'r', encoding='utf-8') as json_file:
            url_dict = json.load(json_file)
    except Exception as e:
        logging.error(f"Error reading file {read_file_path}: {e}")
        return

    # Deduplication map: id -> url
    id_to_url = {}

    for gender, categories in url_dict.items():
        for category, products in categories.items():
            for product in products:
                if isinstance(product, dict) and 'id' in product and 'url' in product:
                    id_to_url[product['id']] = product['url']
                elif isinstance(product, str):
                    derived_id = product.strip().split("/")[-1].replace(".html", "")
                    id_to_url[derived_id] = product
                else:
                    logging.warning(f"Invalid product format in {gender}/{category}: {product}")

    logging.info(f"Total unique products found for {country}: {len(id_to_url)}")

    temp = {}
    processed_ids = set()

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for category, products in categories.items():
            unique_urls = []

            for product in products:
                if isinstance(product, dict) and 'id' in product:
                    product_id = product['id']
                elif isinstance(product, str):
                    product_id = product.strip().split("/")[-1].replace(".html", "")
                else:
                    continue

                if product_id not in processed_ids:
                    url = id_to_url.get(product_id)
                    if url:
                        unique_urls.append(url)
                        processed_ids.add(product_id)

            temp[gender][category] = unique_urls
            logging.info(f"Category {gender}/{category}: {len(unique_urls)} unique URLs")

    os.makedirs(os.path.dirname(write_file_path), exist_ok=True)

    try:
        with open(write_file_path, "w", encoding='utf-8') as outfile:
            json.dump(temp, outfile, indent=4, ensure_ascii=False)

        logging.info(f"{country} unique product URLs saved to {write_file_path}")

        total_unique = sum(len(categories[cat]) for categories in temp.values() for cat in categories)
        logging.info(f"Total unique URLs after deduplication: {total_unique}")

    except Exception as e:
        logging.error(f"Error writing file {write_file_path}: {e}")



if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-11-27'
    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Tuesday', 'Thursday', 'Saturday']:
        countries = ['India', 'UAE']
    else:
        countries = ['UK', 'USA']

    for country in countries:
        if country == 'UAE':
            get_unique_urls_uae(country, today_str)
        else:
            get_unique_urls(country, today_str)
