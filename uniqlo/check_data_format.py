import logging
from pymongo import MongoClient
from datetime import date, datetime

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    format_string_with_ms_no_tz = '%Y-%m-%d %H:%M:%S.%f'
    
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            try:
                return datetime.strptime(date_string, format_string_date_only)
            except ValueError:
                return datetime.strptime(date_string, format_string_with_ms_no_tz)

def check_data_format(connection_string, database_name, collection_name, geography, date):
    format_check = 0

    # Connect to MongoDB
    client = MongoClient(connection_string)
    db = client[database_name]
    collection = db[collection_name]
    
    # Convert the date to the MongoDB format
    db_date = parse_launch_date(date)
    
    # Define the match criteria
    match_criteria = {
        "date_of_scraping": db_date
    }

    product_ids = collection.distinct("product_id", match_criteria)
    genders = collection.distinct("gender", match_criteria)
    titles = collection.distinct("title", match_criteria)
    colors = collection.distinct("color_name", match_criteria)
    skus = collection.distinct("sku", match_criteria)
    prices = collection.distinct("price", match_criteria)
    launch_prices = collection.distinct("launch_price", match_criteria)
    availabilities = collection.distinct("availability", match_criteria)
    age_groups = collection.distinct("age_group", match_criteria)
    age_ranges = collection.distinct("age_range", match_criteria)

    # Check if the data format is correct
    if None in product_ids:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'product_id' contains None.")
    if None in prices:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'price' contains None.")
    if None in launch_prices:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'launch_price' contains None.")
    if None in availabilities:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'availability' contains None.")
    if None in colors:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'color_name' contains None.")
    if None in skus:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'sku' contains None.")
    if None in genders:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'gender' contains None.")
    if None in titles:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'title' contains None.")
    if None in age_groups:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'age_group' contains None.")
    if None in age_ranges:
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'age_range' contains None.")

    if any(gender not in ['male', 'female', 'kids', 'unisex'] for gender in genders):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'gender' contains invalid values.")
    if any(availability not in ['in_stock', 'out_of_stock', 'low_on_stock', 'back_soon', 'coming_soon'] for availability in availabilities):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'availability' contains invalid values.")
    if any(not isinstance(price, (int, float)) for price in prices):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'price' contains non-numeric values.")
    if any(not isinstance(launch_price, (int, float)) for launch_price in launch_prices):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'launch_price' contains non-numeric values.")
    if any(not isinstance(sku, str) for sku in skus):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'sku' contains non-string values.")
    if any(not isinstance(title, str) for title in titles):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'title' contains non-string values.")
    if any(not isinstance(color, str) for color in colors):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'color_name' contains non-string values.")
    if any(age_group not in ['new_born', 'baby', 'kids', 'junior', 'senior', 'teen', 'adult'] for age_group in age_groups):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'age_group' contains invalid values.")
    if any(age_range not in ['1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m', '1y', '2y', '3y', '4y', '5y', '6y', '7y', '8y', '9y', '10y', '11y', '12y', '13y', '14y', '15y', '16y', '17y', '18y'] for age_range in age_ranges):
        format_check = 1
        logging.error(f"Data format error in {geography} for date {date}: 'age_range' contains invalid values.")

    if format_check == 0:
        logging.info(f"Data format check passed for {geography} on {date}. All fields are correctly formatted.")
    else:
        logging.error(f"Data format check failed for {geography} on {date}. Please check and fix the data format issues.")

if __name__ == "__main__":
    # Example usage
    connection_string = "mongodb://localhost:27017"
    database_name = 'tg_analytics'

    # Get today's date
    today_str = date.today().strftime('%Y-%m-%d')

    collections = {
        "UK": ["crawler_sink_uniqlo_uk", "crawler_sink_uniqlo_uk_kids"],
        "USA": ["crawler_sink_uniqlo_usa", "crawler_sink_uniqlo_usa_kids"],
        "Australia": ["crawler_sink_uniqlo_australia", "crawler_sink_uniqlo_australia_kids"],
        "Spain": ["crawler_sink_uniqlo_spain", "crawler_sink_uniqlo_spain_kids"],
        "Canada": ["crawler_sink_uniqlo_canada", "crawler_sink_uniqlo_canada_kids"],
        "India": ["crawler_sink_uniqlo_india", "crawler_sink_uniqlo_india_kids"]
    }

    for geography, collection_names in collections.items():
        for collection_name in collection_names:
            check_data_format(connection_string, database_name, collection_name, geography.lower(), today_str)