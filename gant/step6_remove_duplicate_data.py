import os
import json
import logging
from datetime import date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def remove_duplicates_from_json(countries, today_str=None):
    """Remove duplicate product entries from the final JSON data.
    Simple deduplication based on a combination of product_id and sku.
    """
    if today_str is None:
        today_str = date.today().strftime('%Y-%m-%d')
    for country in countries:
        final_path = os.path.join(country, today_str, 'Final_json', 'data.json')
        if not os.path.exists(final_path):
            logging.warning(f"Final JSON not found for {country} on {today_str}: {final_path}")
            continue
        try:
            with open(final_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logging.error(f"Error reading {final_path}: {e}")
            continue
        seen = set()
        deduped = []
        for item in data:
            key = (item.get('product_id'), item.get('sku'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        if len(deduped) != len(data):
            try:
                with open(final_path, 'w', encoding='utf-8') as f:
                    json.dump(deduped, f, indent=4, ensure_ascii=False)
                logging.info(f"Removed duplicates for {country}: {len(data)-len(deduped)} entries removed.")
            except Exception as e:
                logging.error(f"Error writing deduped data to {final_path}: {e}")
        else:
            logging.info(f"No duplicates found for {country}.")

if __name__ == "__main__":
    # Example usage for debugging
    remove_duplicates_from_json(['UAE'])
