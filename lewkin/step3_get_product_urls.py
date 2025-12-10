import json
import os
import requests
from datetime import datetime

# Base URL for product links
PRODUCT_BASE_URL = "https://lewkin.com/en-kr"

# API URL template (replace {category_id}, {uuid}, and {page_num} accordingly)
API_URL_TEMPLATE = ("https://api.fastsimon.com/categories_navigation?"
                    "request_source=v-next&src=v-next&UUID={uuid}&uuid={uuid}"
                    "&store_id=60044935332&api_type=json&category_id={category_id}"
                    "&facets_required=1&products_per_page=80&page_num={page_num}"
                    "&with_product_attributes=true&st=g01K4Y8MRY8VBFHN7ZP59QNJ4P9"
                    "&market_context=KR&qs=false")

# Load category IDs from file
def load_category_ids(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Fetch product URLs for a given category id across all pages
def fetch_product_urls(category_id, uuid):
    product_urls = []
    page_num = 1

    while True:
        url = API_URL_TEMPLATE.format(category_id=category_id, uuid=uuid, page_num=page_num)
        response = requests.get(url)
        if response.ok:
            data = response.json()
            items = data.get("items", [])
            if not items:  # No more products, stop pagination
                break
            for item in items:
                relative_url = item.get("u")
                if relative_url:
                    full_url = PRODUCT_BASE_URL + relative_url
                    product_urls.append(full_url)
            print(f"Fetched {len(items)} product URLs for category ID {category_id} on page {page_num}")
            page_num += 1  # Move to next page
        else:
            print(f"Failed to fetch products for category ID {category_id} on page {page_num}: {response.status_code}")
            break

    return product_urls

# Main workflow
if __name__ == "__main__":
    # Adjust the path to your saved category IDs JSON
    categories_ids_file = os.path.join("South_korea", "Data", datetime.today().strftime("%Y-%m-%d"), "Item_urls", "categories_ids.json")
    # categories_ids_file = os.path.join("South_korea", "Data", '2025-12-09', "Item_urls", "categories_ids.json")
    # Set the fixed UUID you obtained from your analysis
    uuid = "f3569aee-72ff-4f62-98b8-737e41144508"
    
    category_ids = load_category_ids(categories_ids_file)
    
    all_product_urls = {}
    for category_name, cat_id in category_ids.items():
        if cat_id:
            urls = fetch_product_urls(cat_id, uuid)
            all_product_urls[category_name] = urls
            print(f"Fetched {len(urls)} product URLs for category '{category_name}'")
        else:
            print(f"No category ID for {category_name}, skipping.")
    
    # Save all product URLs to a JSON file
    output_products_file = os.path.join(os.path.dirname(categories_ids_file), "product_urls.json")
    with open(output_products_file, "w", encoding="utf-8") as f:
        json.dump(all_product_urls, f, indent=2, ensure_ascii=False)

    print(f"Saved all product URLs to {output_products_file}")