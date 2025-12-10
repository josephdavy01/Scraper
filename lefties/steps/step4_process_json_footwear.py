import os
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_image_style(image_urls, base_url):
    images = []
    for name, url in image_urls.items():
        filename = url.split('/')[-1].split('.')[0]
        image_style = 's0'
        if '-R' not in filename:
            if name == 'a5':
                image_style = 'm_f_f_c'
            elif name == 'a6':
                image_style = 'n_f_f_c'
            elif name in ['m', 'm1']:
                image_style = 'm_f_h_c'
            elif '.mp4' in url:
                image_style = 'video'
            if name == 'a2' and ('m' not in image_urls.keys() or 'm1' not in image_urls.keys()):
                image_style = 'm_f_h_c'

            temp = {
                "url": url,
                "image_style": image_style
            }
            images.append(temp)
    return images


def extract_composition_details(composition_detail):
    def format_comps(components):
        parts = []
        for c in components:
            mat = (c.get('material') or '').strip()
            pct = (c.get('percentage') or '').strip()
            if mat or pct:
                parts.append(f"{mat} {pct}".strip())
        return ', '.join(parts) if parts else None

    upper = lining = sole = insole = None
    if not composition_detail or 'parts' not in composition_detail:
        return upper, lining, sole, insole

    for part in composition_detail['parts']:
        desc = part.get('description', '').upper()
        value = None
        if part.get('areas'):
            for area in part['areas']:
                comps = area.get('components', []) or []
                v = format_comps(comps)
                if v:
                    value = v
                    break
        elif part.get('components'):
            value = format_comps(part.get('components', []))

        if desc == 'UPPER':
            upper = value
        elif desc == 'LINING':
            lining = value
        elif desc == 'SOLE':
            sole = value
        elif desc == 'INSOLE':
            insole = value

    return upper, lining, sole, insole


def parse_launch_date(date_string):
    format_string_with_ms = '%Y-%m-%dT%H:%M:%S.%fZ'
    format_string_without_ms = '%Y-%m-%dT%H:%M:%SZ'
    format_string_date_only = '%Y-%m-%d'
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            return datetime.strptime(date_string, format_string_date_only)


def get_image_urls(colorcode, xmedia, base_url):
    temp = {}
    for tempmedia in xmedia:
        if tempmedia.get('colorCode') == colorcode:
            for j in tempmedia.get('xmediaItems', []):
                for k in j.get('medias', []):
                    extrainfo = k.get('extraInfo', '')
                    if extrainfo:
                        name = extrainfo.get('originalName', '')
                        url = extrainfo.get('url', '')
                        if name and url:
                            temp[name] = base_url + url
    return temp


def get_avail(availability):
    avail_dict = {
        'HIDDEN': 'out_of_stock',
        'SHOW': 'in_stock',
        'SOLD_OUT': 'out_of_stock'
    }
    return avail_dict.get(availability)


def create_individual_json(fetch_date, json_data, base_url):
    all_products = []
    try:
        product = json_data['products'][0]
    except (IndexError, KeyError):
        return []

    name = product.get('nameEn', '').lower()
    productType = product.get('productType', '').lower().strip()
    if productType != "footwear":
        return []

    gender = product.get('sectionNameEN', '')
    if gender == 'MEN':
        gender = 'male'
    elif gender == 'WOMEN':
        gender = 'female'
    else:
        gender = 'unisex'

    summaries = product.get('bundleProductSummaries', [])
    detail = {}
    product_url_part = ""

    if summaries:
        summary = summaries[0]
        detail = summary.get('detail', {})
        product_url_part = summary.get('productUrl', '')
    
    # If detail or url part is missing from the summary, fall back to the product root
    if not detail:
        detail = product.get('detail', {})
    if not product_url_part:
        product_url_part = product.get('productUrl', '')
    
    if not detail:
        logging.warning(f"Could not find detail object for product ID {product.get('id')}. Skipping.")
        return []

    description = detail.get('longDescription') or None
    reference = detail.get('reference')
    apid = None
    if reference:
        apid = 'lft' + reference.split('-')[0]

    colors = detail.get('colors', [])
    xmedia = detail.get('xmedia', [])
    for color in colors:
        c_id = str(color.get('id', ''))
        c_reference = color.get('reference', '')
        c_name = color.get('name', '').lower().strip()

        catentry = str(color.get('catentryId', ''))
        
        url_base = product_url_part.split('-l')[0] if product_url_part and '-l' in product_url_part else product_url_part
        url = f"https://www.lefties.com/es/en/{url_base}-c0p{catentry}.html?colorId={c_id}"

        upper = lining = sole = insole = None
        if color.get('compositionDetail'):
            upper, lining, sole, insole = extract_composition_details(color.get('compositionDetail'))

        image_urls = get_image_urls(c_id, xmedia, base_url)
        images = get_image_style(image_urls, base_url) if image_urls else []

        for size in color.get('sizes', []):
            sku = str(size.get('sku', ''))
            sizename = size.get('name', '')
            sizereference = size.get('partnumber', '')
            price = float(size.get('price', 0) or 0) / 100
            oldprice = float(size.get('oldPrice', 0) or 0) / 100
            if not oldprice:
                oldprice = price
            origin = size.get('country', '') or None
            availability = get_avail(size.get('visibilityValue', ''))

            entry = {
                "product_id": apid,
                "sub_brand": None,
                "gender": gender,
                "age_group": ['adult'],
                "age_range": ['18y'],
                "date_of_scraping": parse_launch_date(fetch_date),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code": reference,
                "color_id": f'{apid}%{c_id}' if apid else None,
                "color_name": c_name,
                "color_ref_code": c_reference,
                "sku": f'{apid}%{sku}' if apid else sku,
                "size_name": sizename,
                "size_ref_code": sizereference,
                "price": price,
                "launch_price": oldprice,
                "availability": availability,
                "sole_material": sole,
                "upper_material": upper,
                "closure_type": None,
                "toe_type": None,
                "heel_type": None,
                "weight": None,
                "heel_to_toe_drop": None,
                "occasion": None,
                "origin": origin,
                "images": images
            }
            all_products.append(entry)

    return all_products


def get_folders(sub_folders, exclude_folder=None):
    try:
        folders = os.listdir(sub_folders)
    except Exception:
        return []
    if exclude_folder is None:
        exclude_folder = []
    folders = [folder for folder in folders if folder not in exclude_folder]
    return [folder for folder in folders if '.json' not in folder]


def process_jsons(today_str, country, base_url='https://static.lefties.com/', re_run=False):
    """
    Processes all product JSONs for a country and writes the processed footwear
    data to a single JSON file in a memory-efficient way.
    
    If re_run is True, deletes the existing file before processing to avoid duplicating data.
    """
    gender_folder = Path(country) / today_str / 'Json_data'
    if not gender_folder.exists():
        logging.warning(f"Json_data not found for {country} on {today_str}: {gender_folder}")
        return

    output_dir = Path(country) / today_str / 'Data'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_data_footwear.json'
    
    # Delete existing file if re-running to avoid appending to old data
    if re_run and output_file.exists():
        try:
            output_file.unlink()
            logging.info(f"Deleted existing file for {country} due to re-run: {output_file}")
        except Exception as e:
            logging.error(f"Failed to delete existing file for {country}: {e}")

    # Memory-efficient processing: write to file incrementally
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('[')  # Start of JSON array
            is_first_item = True

            genders = get_folders(gender_folder, ['Kids'])
            for gender in genders:
                category_folder = gender_folder / gender
                categories = get_folders(category_folder)
                for category in categories:
                    file_folder = category_folder / category
                    if not file_folder.is_dir():
                        continue
                    
                    for file in file_folder.glob('*.json'):
                        try:
                            with open(file, 'r', encoding='utf-8') as json_file:
                                data = json.load(json_file)
                            
                            skus = create_individual_json(today_str, data, base_url)
                            if not skus:
                                continue

                            for sku in skus:
                                if not is_first_item:
                                    f.write(',\n')
                                json.dump(sku, f, default=str, indent=4)
                                is_first_item = False
                        
                        except Exception as e:
                            logging.error(f"Error processing {file}: {e}")
                            logging.debug(traceback.format_exc())
            
            f.write('\n]')  # End of JSON array

        logging.info(f"Finished processing footwear for {country}. Data saved to {output_file}")

    except Exception as e:
        logging.error(f"Failed to write footwear data for {country}: {e}")


def process_footwear(countries, today_str, re_run=False, base_url='https://static.lefties.com/'):
    """Wrapper to run footwear processing for the given list of countries.

    If re_run is False, skip a country when the output file exists and contains data.
    Returns a dict of country -> status ('success', 'skipped', 'failed').
    """
    statuses = {}
    for country in countries:
        try:
            output_file = Path(country) / today_str / 'Data' / f'{country}_data_footwear.json'
            if not re_run and output_file.exists():
                try:
                    # Check if file size is greater than a minimal threshold (e.g., 2 bytes for "[]")
                    if output_file.stat().st_size > 2:
                        logging.info(f"Skipping {country}: existing footwear data present at {output_file}")
                        statuses[country] = 'skipped'
                        continue
                except Exception:
                    # If we fail to check the existing file, re-run processing
                    logging.warning(f"Could not check existing output file for {country}; will re-run processing")

            # Process the country
            process_jsons(today_str, country, base_url, re_run)
            statuses[country] = 'success'
        except Exception as e:
            logging.error(f"Error processing footwear for {country}: {e}")
            logging.debug(traceback.format_exc())
            statuses[country] = 'failed'

    return statuses

