import os
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def process_country_data(country, today_str):
    p_count_list_1 = []
    p_count_list_2 = []
    p1_total = 0
    p2_total = 0

    try:
        file_path_1 = f"{country}/Data/{today_str}/Item_urls/{country}_product_urls.json"
        file_path_2 = f"{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json"

        if not os.path.exists(file_path_1):
            logging.error(f"Error: {file_path_1} file not found.")
            return
        if not os.path.exists(file_path_2):
            logging.error(f"Error: {file_path_2} file not found.")
            return

        with open(file_path_1, "r", encoding="utf-8") as f:
            pids_dict_1 = json.load(f)
        with open(file_path_2, "r", encoding="utf-8") as f:
            pids_dict_2 = json.load(f)

        is_uk_style = False
        first_gender_val = next(iter(pids_dict_1.values()), {})
        if first_gender_val and isinstance(first_gender_val, dict):
            first_inner_val = next(iter(first_gender_val.values()), {})
            if isinstance(first_inner_val, dict):  
                is_uk_style = True

    
        if is_uk_style:
            for gender, brands in pids_dict_1.items():
                for brand, categories in brands.items():
                    for category, plist in categories.items():
                        if plist:
                            p1_total += len(plist)
                            p_count_list_1.append({
                                "Gender": gender,
                                "Brand": brand,
                                "Category": category,
                                "Count": len(plist)
                            })
            p_count_list_1.append({"Gender": "all", "Brand": "all", "Category": "all", "Count": p1_total})

    
            for gender, brands in pids_dict_2.items():
                for brand, categories in brands.items():
                    for category, plist in categories.items():
                        if plist:
                            p2_total += len(plist)
                            p_count_list_2.append({
                                "Gender": gender,
                                "Brand": brand,
                                "Category": category,
                                "Count": len(plist)
                            })
            p_count_list_2.append({"Gender": "all", "Brand": "all", "Category": "all", "Count": p2_total})

        else:  
            for gender, categories in pids_dict_1.items():
                for category, plist in categories.items():
                    if plist:
                        p1_total += len(plist)
                        p_count_list_1.append({"Gender": gender, "Category": category, "Count": len(plist)})
            p_count_list_1.append({"Gender": "all", "Category": "all", "Count": p1_total})

            for gender, categories in pids_dict_2.items():
                for category, plist in categories.items():
                    if plist:
                        p2_total += len(plist)
                        p_count_list_2.append({"Gender": gender, "Category": category, "Count": len(plist)})
            p_count_list_2.append({"Gender": "all", "Category": "all", "Count": p2_total})

    except Exception as e:
        logging.error(f"Error reading JSON file for {country}: {e}")
        return

    output_dir = Path(f"{country}/Data/{today_str}/Validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(p_count_list_1).to_csv(output_dir / f"{country}_product_count.csv", index=False)
    pd.DataFrame(p_count_list_2).to_csv(output_dir / f"{country}_unique_product_count.csv", index=False)

    logging.info(f"{country} product count saved to {output_dir / f'{country}_product_count.csv'}.")
    logging.info(f"{country} unique product count saved to {output_dir / f'{country}_unique_product_count.csv'}.")
    logging.info(f"{country} total product count: {p1_total}")
    logging.info(f"{country} total unique product count: {p2_total}")

if __name__ == "__main__":
    today_str = date.today().strftime("%Y-%m-%d")
    countries = ["UK", "India","USA"]  
    for country in countries:
        process_country_data(country, today_str)
