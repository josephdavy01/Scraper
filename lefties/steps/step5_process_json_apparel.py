import os
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime

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
    def extract_areas(areas):
        area_strs = []
        for area in areas:
            components_str = ', '.join([f"{comp['material']} {comp['percentage']}" for comp in area['components']])
            area_strs.append(f"{area['description']} : ({components_str})")
        return ', '.join(area_strs)

    def extract_components(components):
        return ', '.join([f"{comp['material']} {comp['percentage']}" for comp in components])

    if not composition_detail or 'parts' not in composition_detail:
        return None

    parts_strs = []
    for part in composition_detail['parts']:
        if part.get('areas'):
            part_str = f"{part['description']} : ({extract_areas(part['areas'])})"
        else:
            part_str = f"{part['description']} : ({extract_components(part.get('components', []))})"
        parts_strs.append(part_str)
    
    return ', '.join(parts_strs) if parts_strs else None


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


def get_age_group(age_range):
    new_born_ages = ['0m', '1m', '2m', '3m', '4m', '5m', '6m']
    baby_ages = ['7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m']
    junior_ages = ['2y', '3y', '4y', '5y', '6y', '7y']
    senior_ages = ['8y', '9y', '10y', '11y', '12y']
    teen_ages = ['13y', '14y', '15y', '16y', '17y']
    adult_ages = ['18y']

    age_goup_list = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']

    if not age_range:
        return ['adult']

    if len(age_range) == 1:
        if age_range[0] in new_born_ages: return ['new_born']
        if age_range[0] in baby_ages: return ['baby']
        if age_range[0] in junior_ages: return ['junior']
        if age_range[0] in senior_ages: return ['senior']
        if age_range[0] in teen_ages: return ['teen']
        return ['adult']

    start = age_range[0]
    end = age_range[-1]
    sindex = eindex = -1

    if start in new_born_ages: sindex = 0
    elif start in baby_ages: sindex = 1
    elif start in junior_ages: sindex = 2
    elif start in senior_ages: sindex = 3
    elif start in teen_ages: sindex = 4
    elif start in adult_ages: sindex = 5

    if end in new_born_ages: eindex = 0
    elif end in baby_ages: eindex = 1
    elif end in junior_ages: eindex = 2
    elif end in senior_ages: eindex = 3
    elif end in teen_ages: eindex = 4
    elif end in adult_ages: eindex = 5
    
    if sindex != -1 and eindex != -1 and sindex <= eindex:
        return age_goup_list[sindex:eindex+1]
    
    return ['others']


def remap_age_range(age_range):
    if len(age_range) > 1:
        age_range = [age_range[0], age_range[-1]]
    if age_range[0] == '1y':
        age_range[0] = '12m'
    if len(age_range) > 1 and age_range[-1] == '2y':
        age_range[-1] = '24m'
    if len(age_range) > 1 and age_range[0] == '24m':
        age_range[0] = '2y'
    if len(age_range) > 1 and age_range[-1] == '48m':
        age_range[-1] = '4y'
    if len(age_range) > 1 and age_range[-1] == '36m':
        age_range[-1] = '3y'
        
    return age_range


def get_age_range(sizename):
    sizename = sizename.strip()
    if 'year' not in sizename and 'month' not in sizename:
        return None

    age_shortname = sizename.split('y')[0] + 'y' if 'year' in sizename else sizename.split('m')[0] + 'm'
    if '1½ y' in age_shortname:
        age_shortname = age_shortname.replace('1½ y', '18 m')
        
    parts = age_shortname.split(' ')
    my = parts[-1]
    numbers = parts[0]

    age_range = []
    if '-' in numbers:
        n1, n2 = map(int, numbers.split('-'))
        age_range = [f"{n}{my}" for n in range(n1, n2 + 1)]
    elif '/' in numbers:
        n1, n2 = map(int, numbers.split('/'))
        age_range = [f"{n}{my}" for n in range(n1, n2 + 1)]
    else:
        age_range.append(numbers + my)

    return remap_age_range(age_range)



def create_individual_json(fetch_date, json_data, base_url):
    all_products = []
    try:
        product = json_data['products'][0]
    except (IndexError, KeyError):
        return []

    name = product.get('nameEn', '').lower()

    # --------------------------------------------------
    # Skip caps / hats / socks products
    # --------------------------------------------------
    skip_keywords = ['cap', 'hat', 'socks']
    if any(word in name for word in skip_keywords):
        return []
    # --------------------------------------------------

    productType = product.get('productType', '').lower().strip()
    if productType != "clothing":
        return []

    section_gender = product.get('sectionNameEN', '')
    if section_gender == 'MEN':
        gender = 'male'
    elif section_gender == 'WOMEN':
        gender = 'female'
    else: # Kids or other
        gender = 'unisex'

    summaries = product.get('bundleProductSummaries', [])
    detail = {}
    product_url_part = ""

    if summaries:
        summary = summaries[0]
        detail = summary.get('detail', {})
        product_url_part = summary.get('productUrl', '')
    
    if not detail:
        detail = product.get('detail', {})
    if not product_url_part:
        product_url_part = product.get('productUrl', '')
    
    if not detail:
        logging.warning(f"Could not find detail object for product ID {product.get('id')}. Skipping.")
        return []

    description = detail.get('longDescription') or None
    reference = detail.get('reference')
    apid = 'lft' + reference.split('-')[0] if reference else None

    colors = detail.get('colors', [])
    xmedia = detail.get('xmedia', [])
    for color in colors:
        c_id = str(color.get('id', ''))
        c_reference = color.get('reference', '')
        c_name = color.get('name', '').lower().strip()
        catentry = str(color.get('catentryId', ''))
        
        url_base = product_url_part.split('-l')[0] if product_url_part and '-l' in product_url_part else product_url_part
        url = f"https://www.lefties.com/es/en/{url_base}-c0p{catentry}.html?colorId={c_id}"

        composition = extract_composition_details(color.get('compositionDetail'))
        image_urls = get_image_urls(c_id, xmedia, base_url)
        images = get_image_style(image_urls, base_url) if image_urls else []

        for size in color.get('sizes', []):
            sizename = size.get('name', '')
            age_range = get_age_range(sizename)
            age_group = get_age_group(age_range)
            
            if age_range is None:
                age_range = ['18y']

            sku = str(size.get('sku', ''))
            sizereference = size.get('partnumber', '')
            price = float(size.get('price', 0) or 0) / 100
            oldprice = float(size.get('oldPrice', 0) or 0) / 100
            if not oldprice:
                oldprice = price
            origin = size.get('country', '') or None
            availability = get_avail(size.get('visibilityValue', ''))

            entry = {
                "product_id": apid,
                "gender": gender,
                "age_group": age_group,
                "age_range": age_range,
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
                "demand": None,
                "composition": composition,
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
    gender_folder = Path(country) / today_str / 'Json_data'
    if not gender_folder.exists():
        logging.warning(f"Json_data not found for {country} on {today_str}: {gender_folder}")
        return

    output_dir = Path(country) / today_str / 'Data'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'{country}_data_apparel.json'
    
    if re_run and output_file.exists():
        try:
            output_file.unlink()
            logging.info(f"Deleted existing file for {country} due to re-run: {output_file}")
        except Exception as e:
            logging.error(f"Failed to delete existing file for {country}: {e}")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('[')
            is_first_item = True

            genders = get_folders(gender_folder)
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
                                if gender.lower() == 'kids':
                                    if 'boy' in category.lower():
                                        sku['gender'] = 'male'
                                    elif 'girl' in category.lower():
                                        sku['gender'] = 'female'

                            for sku in skus:
                                if not is_first_item:
                                    f.write(',\n')
                                json.dump(sku, f, default=str, indent=4)
                                is_first_item = False
                        
                        except Exception as e:
                            logging.error(f"Error processing {file}: {e}")
                            logging.debug(traceback.format_exc())
            
            f.write('\n]')

        logging.info(f"Finished processing apparel for {country}. Data saved to {output_file}")

    except Exception as e:
        logging.error(f"Failed to write apparel data for {country}: {e}")


def process_apparel(countries, today_str, re_run=False, base_url='https://static.lefties.com/'):
    statuses = {}
    for country in countries:
        try:
            output_file = Path(country) / today_str / 'Data' / f'{country}_data_apparel.json'
            if not re_run and output_file.exists():
                try:
                    if output_file.stat().st_size > 2:
                        logging.info(f"Skipping {country}: existing apparel data present at {output_file}")
                        statuses[country] = 'skipped'
                        continue
                except Exception:
                    logging.warning(f"Could not check existing output file for {country}; will re-run processing")

            process_jsons(today_str, country, base_url, re_run)
            statuses[country] = 'success'
        except Exception as e:
            logging.error(f"Error processing apparel for {country}: {e}")
            logging.debug(traceback.format_exc())
            statuses[country] = 'failed'

    return statuses
