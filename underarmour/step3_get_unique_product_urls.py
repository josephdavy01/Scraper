import json
import logging
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_unique_urls(country, today_str):
    if country == "India":
        read_file_path = f"{country}/Data/{today_str}/Item_urls/product_ids.json"
        write_file_path = f"{country}/Data/{today_str}/Item_urls/unique_product_ids.json"
    else:
        read_file_path = f"{country}/Data/{today_str}/Item_urls/product_urls.json"
        write_file_path = f"{country}/Data/{today_str}/Item_urls/unique_product_urls.json"

    with open(read_file_path, encoding="utf-8") as json_file:
        url_dict = json.load(json_file)
    all_urls = set()
    for gender, categories in url_dict.items():
        for cat, urls in categories.items():
            all_urls.update(urls)
    logging.info(f"Total unique urls found for {country}: {len(all_urls)}")
    temp = {}
    for gender, categories in url_dict.items():
        temp[gender] = {}
        for cat, urls in categories.items():
            uq_urls = all_urls.intersection(set(urls))
            all_urls -= uq_urls
            if uq_urls:  
                temp[gender][cat] = list(uq_urls)
        if not temp[gender]: 
            temp.pop(gender, None)
    with open(write_file_path, "w", encoding="utf-8") as outfile:
        json.dump(temp, outfile, indent=4)
    logging.info(f"{country} unique product urls saved to {write_file_path}")

if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    # today_str = '2025-11-19'
    day = datetime.strptime(today_str, "%Y-%m-%d").strftime("%A")
    if day in ["Monday", "Wednesday", "Friday"]:
        countries = ["India", "UAE"]
    elif day in ["Tuesday", "Thursday", "Saturday"]:
        countries = ["UK", "USA"]
    else:
        countries = []
    for country in countries:
        get_unique_urls(country, today_str)
