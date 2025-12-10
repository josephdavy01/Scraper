import os
import logging
import multiprocessing
from curl_cffi import requests
from validations import save_json

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- WORKER LOGIC ---
def worker_cffi(country, config, today_date):
   
    initial = config.get('base_url') 
    cid = config.get('cid')
    
    # Construct API URL
    url = f'https://www.bershka.com/itxrest/2/catalog/store/{cid}/category?languageId=-1&typeCatalog=1&appId=1'
    if country == 'USA':
        url = f'https://www.bershka.com/itxrest/2/catalog/store/{cid}/category?languageId=-15&typeCatalog=1&appId=1'

    logging.info(f'[{country}] Fetching category URLs via curl_cffi...')
    
    try:
        # Request using curl_cffi with impersonation
        response = requests.get(
            url, 
            impersonate="chrome120", 
            timeout=30
        )
        
        if response.status_code != 200:
            logging.error(f"[{country}] Failed to fetch. Status: {response.status_code}")
            return

        json_data = response.json()

        # --- JSON PARSING LOGIC (Preserved from original) ---
        temp_json = {}

        for category in json_data.get('categories', []):
            gender = category.get('nameEn')
            if gender in ['WOMEN', 'MEN', 'BY INFLUENCERS']:
                temp_json[gender] = {}
                for subcat in category.get('subcategories', []):
                    cname = subcat.get('nameEn')
                    if not cname:
                        continue
                    name1 = cname.lower().replace(' ', '-').replace('|', '&')
                    url1 = subcat.get('categoryUrl')
                    id1 = subcat.get('viewCategoryId')

                    sub_subcats = subcat.get('subcategories', [])
                    if sub_subcats:
                        for inner in sub_subcats:
                            cname2 = inner.get('nameEn')
                            if cname2:
                                name2 = cname2.lower().replace(' ', '-').replace('|', '&')
                                url2 = inner.get('categoryUrl', url1)
                                id2 = inner.get('id')
                                if id2:
                                    # Create key combining parent and child category
                                    key_name = f"{name1}_{name2}"
                                    temp_json[gender][key_name] = {
                                        'id': id2,
                                        'url': initial + url2 if url2 else None
                                    }
                    elif id1 and url1:
                        temp_json[gender][name1] = {
                            'id': id1,
                            'url': initial + url1
                        }
        # ----------------------------------------------------

        # Output Path (Aligned with Master Code)
        base_path = f'{country}/{today_date}/Category'
        output_file = f'{base_path}/{country}_category_urls.json'
        
        save_json(output_file, temp_json)
        logging.info(f"[{country}] Success. Saved to {output_file}")

    except Exception as e:
        logging.error(f"[{country}] Error processing categories: {str(e)}")

# --- MAIN ENTRY POINT ---
def get_category_urls(config_dict, today_date, re_run=False):
    """
    Main function called by Master Code.
    """
    processes = []
    
    for country, settings in config_dict.items():
        # Check if file exists to avoid re-running if not forced
        base_path = f'{country}/{today_date}/Category'
        out_file = f'{base_path}/{country}_category_urls.json'
        
        if os.path.exists(out_file) and not re_run:
            logging.info(f"[{country}] Data already exists. Skipping...")
            continue

        # Spawn a process for the country
        p = multiprocessing.Process(target=worker_cffi, args=(country, settings, today_date))
        processes.append(p)
        p.start()
        
    for p in processes:
        p.join()

    logging.info("All Category URL extraction tasks finished.")