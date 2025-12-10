import json
import logging
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_unique_urls(country, today_str):
    read_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_product_urls.json'
    write_file_path = f'{country}/Data/{today_str}/Item_urls/{country}_unique_product_urls.json'

    with open(read_file_path) as json_file:
        url_dict = json.load(json_file)

    all_urls = set()

    for gender, categories in url_dict.items():
        for category, urls in categories.items():
            for url in urls:
                all_urls.add(url)

    temp = {}

    for gender, categories in url_dict.items():
        temp[gender] = {}
        for category, urls in categories.items():
            curls = all_urls.intersection(set(urls))
            all_urls = all_urls - set(urls)
            temp[gender][category] = list(curls)

    with open(write_file_path, "w", encoding='utf-8') as outfile:
        json.dump(temp, outfile, indent=4)
    
    logging.info(f"{country} unique product urls saved to {write_file_path}")

def get_unique_product_urls_main():
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')

    # Get the day of the week
    day = datetime.strptime(today_str, '%Y-%m-%d').strftime('%A')

    if day in ['Monday', 'Wednesday', 'Friday']:
        countries = ['UK']
        for country in countries:
            get_unique_urls(country, today_str)
    else:
        logging.info(f"Today is {day}. No processing required.")
        # In a main function, it's better to return than to exit
        return

if __name__ == "__main__":
    get_unique_product_urls_main()
