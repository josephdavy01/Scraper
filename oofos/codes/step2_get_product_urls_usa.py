from datetime import date, time
import json
import logging
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

country = "USA"
today = date.today().strftime('%Y-%m-%d')

# Input file path
input_file = Path(country).joinpath("Data", today, "Item_urls", f"{country}_category_urls.json")

# Output directory and file
output_dir = Path(country).joinpath("Data", today, "Item_urls")
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / f"{country}_unique_product_urls.json"

# Load the category URLs JSON
with open(input_file, "r") as f:
    category_urls = json.load(f)

base_url = "https://www.oofos.com"

all_product_urls = {}

# Loop through each gender and category
for gender, categories in category_urls.items():
    if gender not in all_product_urls:
        all_product_urls[gender] = {}
    
    for category_name, url in categories.items():
        all_product_urls[gender][category_name] = []
        
        if "/products/" in url:
            all_product_urls[gender][category_name].append(url)
            logging.info(f"Added direct product URL to {gender}/{category_name}: {url}")
        
        elif "/collections/" in url:
            category_slug = url.split("/collections/")[-1].split("?")[0]
            
            query_params = ""
            if "?" in url:
                query_params = "&" + url.split("?")[1]
            
            json_url = f"{base_url}/collections/{category_slug}?view=json{query_params}"
            
            try:
                response = requests.get(json_url)
                if response.status_code == 429:
                    wait = int(response.headers.get("Retry_After",20))
                    logging.info("Rate Limited . Waiting {wait} seconds...")
                    time.sleep(10)
                    continue
                response.raise_for_status()
                data = response.json()
                products = data.get("products", [])
                for product in products:
                    variants = product.get("variants", [])
                    for variant in variants:
                        variant_id = variant.get("id")
                        product_path = product.get("url")
                        if product_path and variant_id:
                            full_url = f"{base_url}{product_path}?variant={variant_id}"
                            all_product_urls[gender][category_name].append(full_url)
                
                logging.info(f"Fetched {len(products)} products from {gender}/{category_name}")
            
            except Exception as e:
                logging.error(f"Error fetching {json_url}: {e}")

# Save all product URLs to a JSON file 
with open(output_path, "w") as f:
    json.dump(all_product_urls, f, indent=4)

# Count total URLs
total_urls = sum(len(urls) for gender_data in all_product_urls.values() for urls in gender_data.values())

logging.info(f"Total product URLs found: {total_urls}")
logging.info(f"Product URLs saved to: {output_path}")
