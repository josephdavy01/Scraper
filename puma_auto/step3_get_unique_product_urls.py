import json
import logging
from datetime import date, datetime
import os


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'

    with open(read_file_path,encoding='utf-8') as json_file:
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
        read_file_path = f'{base_dir}/{country}_product_urls.json'  # Fixed filename
        write_file_path = f'{base_dir}/{country}_unique_product_urls.json'  # Updated output filename
        
        # Check if input file exists
        if not os.path.exists(read_file_path):
            logging.error(f"Input file not found: {read_file_path}")
            return
        
        try:
            with open(read_file_path, 'r', encoding='utf-8') as json_file:
                url_dict = json.load(json_file)
        except Exception as e:
            logging.error(f"Error reading file {read_file_path}: {e}")
            return

        # Collect all unique URLs (keeping the full object structure)
        all_urls = {}  # Dictionary to store id: {id, url} mapping
        
        for gender, categories in url_dict.items():
            for category, products in categories.items():
                for product in products:
                    if isinstance(product, dict) and 'id' in product and 'url' in product:
                        all_urls[product['id']] = product
                    else:
                        logging.warning(f"Invalid product format in {gender}/{category}: {product}")

        logging.info(f"Total unique products found for {country}: {len(all_urls)}")

        # Create the deduplicated structure
        temp = {}
        processed_ids = set()  # Track which IDs we've already assigned

        for gender, categories in url_dict.items():
            temp[gender] = {}
            for category, products in categories.items():
                unique_products = []
                
                for product in products:
                    if isinstance(product, dict) and 'id' in product:
                        product_id = product['id']
                        # Only add if we haven't seen this ID in a previous category
                        if product_id not in processed_ids:
                            unique_products.append(product)
                            processed_ids.add(product_id)
                            
                temp[gender][category] = unique_products

        # Ensure output directory exists
        os.makedirs(os.path.dirname(write_file_path), exist_ok=True)
        
        try:
            with open(write_file_path, "w", encoding='utf-8') as outfile:
                json.dump(temp, outfile, indent=4, ensure_ascii=False)
            
            logging.info(f"{country} unique product URLs saved to {write_file_path}")
            
            # Log summary statistics
            total_unique = sum(len(categories[cat]) for categories in temp.values() for cat in categories)
            
        except Exception as e:
            logging.error(f"Error writing file {write_file_path}: {e}") 
    
    

if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-10-09'

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')
    
    if day in ['Monday','Wednesday', 'Friday']:
        countries = ['INDIA']

        for country in countries:
            get_unique_urls(country, today_str)
    else:
        countries = ['UK','UAE']
        for country in countries:
            if country == 'UAE':
                get_unique_urls_uae(country, today_str)
            else:
                get_unique_urls(country, today_str)
                
        
 