import os
import json
import logging
from datetime import datetime, date

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ------------------------------------------
# SAFE DATE PARSER
# ------------------------------------------
def parse_launch_date(date_string):
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S.%f'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_string}")


# ------------------------------------------
# NORMALIZATION HELPERS
# ------------------------------------------
def normalize_gender(value):
    if not value:
        return None

    v = str(value).strip().lower()

    mapping = {
        "men": "male",
        "man": "male",
        "boy": "male",
        "boys": "male",

        "women": "female",
        "woman": "female",
        "girl": "female",
        "girls": "female",

        "kids": "unisex",
        "kid": "unisex",
        "unisex": "unisex"
    }

    return mapping.get(v, v)  # return normalized OR raw lower-case


def safe_extract(records, field):
    values = set()
    for r in records:
        val = r.get(field)
        if isinstance(val, list):
            for x in val:
                values.add(x)
        else:
            values.add(val)
    return values


# ------------------------------------------
# MAIN VALIDATION FUNCTION
# ------------------------------------------
def check_data_format(geography, date_str):
    format_check = 0

    file_path = os.path.join(geography, date_str, "Final_json", "data.json")

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return

    # Load JSON
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        logging.error(f"Error reading JSON: {e}")
        return

    # Normalize gender field
    for r in records:
        r["gender"] = normalize_gender(r.get("gender"))

    # Collect values
    product_ids = {r.get("product_id") for r in records}
    genders = {r.get("gender") for r in records}
    titles = {r.get("title") for r in records}
    colors = {r.get("color_name") for r in records}
    skus = {r.get("sku") for r in records}
    prices = {r.get("price") for r in records}
    launch_prices = {r.get("launch_price") for r in records}
    availabilities = {r.get("availability") for r in records}

    # Use safe_extract for fields that might be lists
    age_groups = safe_extract(records, "age_group")
    age_ranges = safe_extract(records, "age_range")

    # Field presence validation
    mandatory_fields = [
        ("product_id", product_ids),
        ("gender", genders),
        ("title", titles),
        ("color_name", colors),
        ("sku", skus),
        ("price", prices),
        ("launch_price", launch_prices),
        ("availability", availabilities),
        ("age_group", age_groups),
        ("age_range", age_ranges),
    ]

    for field_name, values in mandatory_fields:
        if None in values:
            format_check = 1
            logging.error(f"'{field_name}' contains None.")

    # Gender validation (after normalization)
    valid_genders = {"male", "female", "unisex"}
    if not genders.issubset(valid_genders):
        format_check = 1
        logging.error(f"Invalid 'gender' values found: {genders}")

    # Availability check
    valid_availabilities = {
        "in_stock", "out_of_stock", "low_on_stock", "back_soon", "coming_soon"
    }
    if not availabilities.issubset(valid_availabilities):
        format_check = 1
        logging.error("Invalid 'availability' values found.")

    # Numeric validations
    if any(not isinstance(p, (int, float)) for p in prices if p is not None):
        format_check = 1
        logging.error("'price' contains non-numeric values.")

    if any(not isinstance(lp, (int, float)) for lp in launch_prices if lp is not None):
        format_check = 1
        logging.error("'launch_price' contains non-numeric values.")

    # String validations
    if any(not isinstance(s, str) for s in skus if s is not None):
        format_check = 1
        logging.error("'sku' contains non-string values.")

    if any(not isinstance(t, str) for t in titles if t is not None):
        format_check = 1
        logging.error("'title' contains non-string values.")

    if any(not isinstance(c, str) for c in colors if c is not None):
        format_check = 1
        logging.error("'color_name' contains non-string values.")

    # Age validations
    valid_age_groups = {"new_born", "baby", "junior", "senior", "teen", "adult"}
    if not age_groups.issubset(valid_age_groups):
        logging.error(f"Invalid 'age_group' values found: {age_groups}")
        format_check = 1

    valid_age_ranges = {
        '1m','2m','3m','4m','5m','6m','7m','8m','9m','10m','11m','12m','13m','14m','15m','16m','17m','18m',
        '19m','20m','21m','22m','23m','24m','2y','3y','4y','5y','6y','7y','8y',
        '9y','10y','11y','12y','13y','14y','15y','16y','17y','18y'
    }
    if not age_ranges.issubset(valid_age_ranges):
        logging.error(f"Invalid 'age_range' values found: {age_ranges}")
        format_check = 1

    # Final output
    if format_check == 0:
        logging.info(f"Data format check passed for {geography} on {date_str}.")
    else:
        logging.error(f"Data format check failed for {geography} on {date_str}.")


# ------------------------------------------
# MAIN RUN
# ------------------------------------------
def main():
    today_str = date.today().strftime('%Y-%m-%d')
    geographies = ["UAE"]

    for geo in geographies:
        check_data_format(geo, today_str)


if __name__ == "__main__":
    main()
