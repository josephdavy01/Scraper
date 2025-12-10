import os
import json
import traceback
from datetime import datetime
import pymongo
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def parse_launch_date(date_string):
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d', '%Y-%m-%d %H:%M:%S.%f'
    ]
    for f in formats:
        try:
            return datetime.strptime(date_string, f)
        except Exception:
            continue
    logger.error(f"Failed to parse date: {date_string}")
    return None


# def get_images(images_list):
#     image_list = []
#     updated = False
#     for i, img in enumerate(images_list):
#         image_style = "n_f_f_c" if i == 0 else "s0"
#         url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
#         if isinstance(url, str) and url.startswith("//"):
#             new_url = url.replace("//cdn", "https://cdn", 1)
#             logger.info(f"Fixed URL: {url} -> {new_url}")
#             url = new_url
#             updated = True
#         image_list.append({"url": url, "image_style": image_style})
#     if updated:
#         logger.info("Image URLs were updated to use absolute paths.")
#     return image_list
def get_images(images_list):
    image_list = []
    updated = False
    for img in images_list:
        image_style = "s0"
        url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
        if isinstance(url, str) and url.startswith("//"):
            new_url = url.replace("//cdn", "https://cdn", 1)
            logger.info(f"Fixed URL: {url} -> {new_url}")
            url = new_url
            updated = True
        image_list.append({"url": url, "image_style": image_style})
    if updated:
        logger.info("Image URLs were updated to use absolute paths.")
    return image_list



def extract_active_attributes(html_desc, tags):
    if not html_desc:
        return ""
    soup = BeautifulSoup(html_desc, 'html.parser')
    result_items = []
    detail_div = soup.find('div', class_='prd-detail-table-x')
    if detail_div:
        rows = detail_div.find_all('tr')
        for row in rows:
            th = row.find('th')
            if not th:
                continue
            key = th.get_text(strip=True)
            active_span = row.find('span', class_='active')
            if active_span:
                value = active_span.get_text(strip=True)
                result_items.append(f"{key}:{value}")
    style_keywords = {
        'kpop': 'kpop',
        'Acubi': 'acubi',
        'coquette': 'coquette',
        'shoujo': 'shoujo girl',
        'Y2k': 'y2k',
        'streetstyle': 'korean street fashion'
    }
    all_lis = soup.find_all('li')
    composition_keywords = ['style', 'occasion', 'type', 'print', 'sleeve', 'neck', 'fit', 'color', 'material']
    for li in all_lis:
        text = li.get_text(separator=' ', strip=True).lower()
        if any(kw in text for kw in composition_keywords) and not text.endswith('%') and 'model' not in text:
            if text.startswith('style'):
                style_text = li.get_text(separator=' ', strip=True)
                existing_styles = [s.strip().lower() for s in style_text.split(':')[1].split(',')]
                matching_styles = [style_text]
                for key, style in style_keywords.items():
                    if any(key.lower() in tag.lower() for tag in tags) and style.lower() not in existing_styles:
                        matching_styles.append(style)
                result_items.append(", ".join(matching_styles))
            else:
                result_items.append(li.get_text(separator=' ', strip=True))
    return " | ".join(result_items)


def extract_composition(html_desc):
    if not html_desc:
        return ""
    soup = BeautifulSoup(html_desc, 'html.parser')
    all_lis = soup.find_all('li')
    composition_items = []
    for li in all_lis:
        text = li.get_text(separator=' ', strip=True)
        lower_text = text.lower()
        has_percent = '%' in lower_text
        has_fiber_num = any(fiber in lower_text for fiber in ['cotton', 'nylon', 'spandex', 'polyester', 'wool', 'silk'])
        digit_chars = any(char.isdigit() for char in text)
        if has_percent or (has_fiber_num and digit_chars):
            composition_items.append(text)
    return " | ".join(composition_items)


def split_sizes(size_str):
    if not size_str:
        return []
    return [s.strip() for s in size_str.split('/')]


def extract_gender_from_tags(tags):
    if not tags or not isinstance(tags, list):
        return 'unisex'
    for tag in tags:
        tag = tag.lower()
        if tag.startswith('feed-gender-'):
            return tag[len('feed-gender-'):]
    return 'unisex'

def normalize_gender(gender_value):
    if not gender_value:
        return "unisex"
    gender_value = gender_value.lower().strip()
    if gender_value in ["men", "man", "male"]:
        return "male"
    elif gender_value in ["women", "woman", "female"]:
        return "female"
    return gender_value


def convert_to_numeric(value, field_name):
    if value is None:
        logger.error(f"Field {field_name} is None")
        return None
    try:
        cleaned_value = str(value).replace(',', '')
        return float(cleaned_value)
    except (ValueError, TypeError) as e:
        logger.error(f"Field {field_name} contains non-numeric value: {value}")
        return None


def map_availability(value, field_name):
    if isinstance(value, bool):
        return "in_stock" if value else "out_of_stock"
    if isinstance(value, str):
        value = value.lower()
        if value in ('true', '1', 'yes', 'available'):
            return "in_stock"
        if value in ('false', '0', 'no', 'unavailable'):
            return "out_of_stock"
    logger.error(f"Field {field_name} contains invalid value: {value}")
    return "out_of_stock"


def map_custom_product_record(product_data, today_str, sku_value, size_name, availability, demand=None,
                              handle=None, variant_id=None, currency=None, color_id=None):
    pid_raw = str(product_data.get("Product Reference Code") or product_data.get('product_id', "")) or ""
    product_id = f'lew{pid_raw}'
    tags = product_data.get('tags', [])
    gender_std = extract_gender_from_tags(tags)
    gender_std = normalize_gender(gender_std)  #
    if gender_std == 'kids':
        age_group = ['kids']
        age_range = ['1y', '17y']
    else:
        age_group = ['adult']
        age_range = ['18y']
    brand = (product_data.get("Brand") or "Skechers").lower()
    price = convert_to_numeric(product_data.get("Price"), "price")
    launch_price = convert_to_numeric(product_data.get("Launch Price") or product_data.get("Price"), "launch_price")
    availability_str = map_availability(availability, "availability")
    html_description = product_data.get('description', '') or product_data.get('Description', '')
    description = extract_active_attributes(html_description, tags)
    compositions = extract_composition(html_description)
    composition = compositions.lower() if compositions else None
    if handle:
        if variant_id:
            product_url = f'https://lewkin.com/en-kr/products/{handle}?variant={variant_id}'
        else:
            product_url = f'https://lewkin.com/en-kr/products/{handle}'
    else:
        product_url = product_data.get('Product Url', '')
    actual_color_id = color_id if color_id else product_data.get('Color Id')
    size_specific_sku = f'{product_id}%p{product_id.replace("lew", "")}c{actual_color_id}s{size_name}'.replace(' ', '')
    return {
        'product_id': product_id,
        'gender': gender_std,
        'age_group': age_group,
        'age_range': age_range,
        'date_of_scraping': parse_launch_date(today_str),
        'url': product_url,
        'title': product_data.get('Title', ''),
        'description': description,
        'product_ref_code': pid_raw,
        'color_id': f'{product_id}%{actual_color_id}',
        'color_name': product_data.get('Color Name', '').lower(),
        'color_ref_code': actual_color_id,
        'sku': size_specific_sku,
        'size_name': size_name,
        'size_ref_code': None,
        'price': price,
        'launch_price': launch_price,
        'availability': availability_str,
        'demand': demand,
        'composition': composition,
        'origin': product_data.get('Made In'),
        'images': get_images(product_data.get('Images', []) or []),
    }


def group_images_sequential_by_color(media):
    color_image_map = {}
    current_color = None
    for item in sorted(media, key=lambda x: x.get('position', 0)):
        alt_text = item.get('alt') or ''
        if '/' in alt_text:
            color = alt_text.split('/')[-1].strip().lower()
        else:
            color = None
        if color and color != current_color:
            current_color = color
            if current_color not in color_image_map:
                color_image_map[current_color] = []
        if current_color:
            src = item.get('src')
            if src:
                color_image_map[current_color].append(src)
    return color_image_map


def load_color_id_mapping(color_id_path):
    if not os.path.exists(color_id_path):
        logger.error(f"Color ID mapping file not found: {color_id_path}")
        return {}
    with open(color_id_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
        return {k.lower(): v for k, v in mapping.items()}


def create_records_from_json(today_str, json_data, json_data_variants, color_id_mapping):
    records = []
    product_base = {
        'id': json_data.get('id'),
        'Product Url': json_data.get('url'),
        'Title': json_data.get('title').lower(),
        'description': json_data.get('description'),
        'Product Reference Code': json_data.get('id'),
        'Color Id': None,
        'Color Name': None,
        'Price': None,
        'Launch Price': None,
        'Composition': None,
        'Made In': None,
        'Images': json_data.get('images', []),
        'Brand': json_data.get('vendor'),
        'handle': json_data.get('handle'),
        'tags': json_data.get('tags', []),
        'media': json_data.get('media', [])
    }
    soup = BeautifulSoup(product_base['description'], 'html.parser')
    all_lis = soup.find_all('li')
    for li in all_lis:
        text = li.get_text(separator=' ', strip=True).lower()
        if 'made in' in text:
            country = text.split('made in')[-1].strip().lower()
            product_base['Made In'] = country

    valid_sizes = {"XS", "S", "M", "L", "XL", "XXS", "XXL", "2XL", "3XL", "4XL", "5XL", "6XL", "M/L"}
    all_sizes_valid = True
    for variant in json_data.get('variants', []):
        sizes_combined = variant.get('option2', '')
        sizes = split_sizes(sizes_combined) or [sizes_combined]
        for size in sizes:
            if size and size not in valid_sizes:
                all_sizes_valid = False
                break
        if not all_sizes_valid:
            break
    if not all_sizes_valid:
        logger.warning(f"Skipping product {product_base['id']} due to invalid sizes")
        return records

    color_images = group_images_sequential_by_color(json_data.get('media', []))

    for variant, json_variant in zip(json_data.get('variants', []), json_data_variants.get('product', {}).get('variants', [])):
        product = product_base.copy()
        color_name = variant.get('option1', '').lower()

        color_id = color_id_mapping.get(color_name)

        images_matched = color_images.get(color_name)
        if not images_matched and variant.get('featured_image'):
            images_matched = [variant.get('featured_image', {}).get('src')]

        product.update({
            'Color Id': color_id,
            'Color Name': color_name,
            'Price': json_variant.get('price'),
            'Launch Price': json_variant.get('compare_at_price'),
            'SKU': variant.get('sku'),
            'Images': images_matched if images_matched else product_base['Images']
        })
        sizes_combined = variant.get('option2', '')
        sizes = split_sizes(sizes_combined) or [sizes_combined]
        for size in sizes:
            if not size:
                continue
            availability = variant.get('available', False)
            rec = map_custom_product_record(
                product,
                today_str,
                product['SKU'],
                size,
                availability=availability,
                handle=product_base.get('handle'),
                variant_id=variant.get('id'),
                currency=json_variant.get('price_currency'),
                color_id=color_id
            )
            if rec['price'] is None or rec['launch_price'] is None:
                logger.error(f"Skipping record for SKU {rec['sku']} due to invalid price or launch_price")
                continue
            if rec['availability'] not in ("in_stock", "out_of_stock"):
                logger.error(f"Skipping record for SKU {rec['sku']} due to invalid availability: {rec['availability']}")
                continue
            records.append(rec)
    return records


def process_json_files_recursive(today_str, country, collection, base_path, color_id_mapping):
    if not os.path.exists(base_path):
        logger.error(f"Path not found: {base_path}")
        return
    for root, _, files in os.walk(base_path):
        for file_name in files:
            if file_name.endswith('.json'):
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    records = create_records_from_json(today_str, json_data['js_data'], json_data['json_data'], color_id_mapping)
                    if records:
                        try:
                            collection.insert_many(records)
                            logger.info(f"Inserted {len(records)} records from {file_path}")
                        except Exception as e:
                            logger.error(f"Error inserting records from {file_path}: {e}")
                            traceback.print_exc()
                    else:
                        logger.warning(f"No valid records to insert from {file_path}")
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    traceback.print_exc()


def main():
    MONGODB_URI = "mongodb://localhost:27017"  # Specify your MongoDB URI here
    MONGODB_DB = "tg_analytics"   # Specify your MongoDB DB name here
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        collection = db['crawler_sink_lewkin_south_korea']

        country = 'South_korea'
        today_str = datetime.today().strftime("%Y-%m-%d") 
        # today_str='2025-12-06'
        data_base_path = os.path.join(country, 'Data',today_str)
        if not os.path.exists(data_base_path):
            logger.error(f"Data base path not found: {data_base_path}")
            return
        for date_folder in os.listdir(data_base_path):
            date_path = os.path.join(data_base_path, date_folder)
            if not os.path.isdir(date_path):
                continue
        # today_str = datetime.today().strftime("%Y-%m-%d") 
        # today_str='2025-12-02'
        base_path = os.path.join(data_base_path, 'Json_data')
        color_id_path = 'lewkin_cid_remapping.json'
        color_id_mapping = load_color_id_mapping(color_id_path)
        process_json_files_recursive(today_str, country, collection, base_path, color_id_mapping)
        # data_root = os.path.join(country, 'Data')
        # color_id_path = 'lewkin_cid_remapping.json'
        # color_id_mapping = load_color_id_mapping(color_id_path)

        # if not os.path.exists(data_root):
        #     logger.error(f"Data root path not found: {data_root}")
        #     return

        # # Loop through all date folders
        # for date_folder in sorted(os.listdir(data_root)):
        #     date_path = os.path.join(data_root, date_folder)
        #     if not os.path.isdir(date_path):
        #         continue

        #     base_path = os.path.join(date_path, 'Json_data')
        #     today_str = date_folder  # Use folder name as date

        #     logger.info(f"Processing date folder: {date_folder}")
        #     process_json_files_recursive(today_str, country, collection, base_path, color_id_mapping)

        logger.info("Load complete.")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
