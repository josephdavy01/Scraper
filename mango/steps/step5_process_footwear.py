import os
import json
import logging
import traceback
from datetime import datetime

# Configure logging to console (will be overridden/augmented per country)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_launch_date(date_string):
    formats = ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    return None

def remap_gender(gender):
    try:
        gender = gender.lower().strip()
        if gender in ['men', 'he', 'mens', 'mens;']:
            return 'male'
        elif gender in ['women', 'she', 'womens', 'womens;']:
            return 'female'
        else:
            return 'unisex'
    except AttributeError:
        return 'unisex'

def get_gender_from_url(url):
    try:
        raw_gender = url.split('/')[6]
        genders = {
            "shopurlkidse": "female",
            "shopurlkidsa": "female",
            "newborn": "unisex",
            "baby-girls": "female",
            "shopurlkidsf": "unisex",
            "girls": "female",
            "shopurlkidso": "male",
            "boys": "male",
            "shopurlkidsd": "male",
            "baby-boys": "male"
        }
        return genders.get(raw_gender, "unisex")
    except Exception:
        return "unisex"

def get_images(imagelist):
    images = []
    if not imagelist:
        return images
        
    # Handle list format (from Kids script) or dict format (from Adult script)
    if isinstance(imagelist, list):
         # Kids script format: looks is a list of dicts directly? 
         # Wait, Kids script: images = get_images(looks). looks = color.get('looks').
         # In Kids script get_images iterates: for s, s1 in imagelist.items():
         # So looks is expected to be a dict in both cases based on the provided code.
         pass

    for s, s1 in imagelist.items():
        for image in s1.get('media', []):
            mtype = image.get('type')
            image_url = image.get('src')

            if not image_url:
                continue

            if 'https://shop.mango.com' in image_url:
                url = image_url
            else:
                url = 'https://shop.mango.com' + image_url

            if mtype == 'F':
                image_style = 'm_f_h_c'
            elif mtype in ('O1', 'D3'):
                image_style = 'm_f_f_c'
            elif mtype == 'B':
                image_style = 'n_f_f_c'
            elif mtype == 'R':
                image_style = 'm_b_f_c'
            else:
                image_style = 's0'

            images.append({
                "url": url,
                "image_style": image_style
            })
    return images

def get_pid(pid, pdict):
    for i, j in pdict.items():
        if pid in j:
            return i
    return '00000000'

def is_float(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def remap_age_range(age_range):
    try:
        if len(age_range) == 2 and age_range[1] == '2y':
            f = int(float(age_range[0].replace('y', '')) * 12)
            s = int(float(age_range[1].replace('y', '')) * 12)
            return [f"{f}m", f"{s}m"]
        elif len(age_range) == 2 and age_range[0] == '24m':
            f = int(float(age_range[0].replace('m', '')) / 12)
            s = int(float(age_range[1].replace('m', '')) / 12)
            return [f"{f}y", f"{s}y"]
        if len(age_range) > 1 and age_range[1] == '36m':
            return [age_range[0], '3y']
        if age_range == ['2y']:
            return ['24m']
    except Exception:
        pass
    return age_range

def get_age_range(size):
    try:
        size = size.replace(' ', '').replace('–', '-')
        if 'months' in size:
            if '-' in size:
                vals = size.replace('months', '').split('-')
                if len(vals) == 2 and all(is_float(v) for v in vals):
                    return remap_age_range([f"{vals[0]}m", f"{vals[1]}m"])
            return [size.replace('months', 'm')]
        elif 'years' in size:
            if '-' in size:
                vals = size.replace('years', '').split('-')
                if len(vals) == 2 and all(is_float(v) for v in vals):
                    return remap_age_range([f"{vals[0]}y", f"{vals[1]}y"])
            return remap_age_range([size.replace('years', 'y')])
        return None
    except Exception:
        return None

def get_age_group(age_range):
    groups = {
        'new_born': ['0m', '1m', '2m', '3m', '4m', '5m', '6m'],
        'baby': ['7m','8m','9m','10m','11m','12m','13m','14m','15m','16m','17m','18m','19m','20m','21m','22m','23m','24m'],
        'junior': ['2y','3y','4y','5y','6y','7y'],
        'senior': ['8y','9y','10y','11y','12y'],
        'teen': ['13y','14y','15y','16y','17y'],
        'adult': ['18y']
    }
    labels = list(groups.keys())

    if not age_range:
        return ['others']

    if len(age_range) == 1:
        for name, ages in groups.items():
            if age_range[0] in ages:
                return [name]
        return ['others']
    else:
        s, e = None, None
        for idx, name in enumerate(labels):
            if age_range[0] in groups[name]:
                s = idx
            if age_range[-1] in groups[name]:
                e = idx
        if s is not None and e is not None:
            return labels[s:e+1]
        return ['others']

def create_individual_skus(today_str, json_data, gender, pdict):
    if 'product' in json_data and 'price' in json_data:
        all_products = []
        product = json_data['product']
        price_data = json_data.get('price', {})

        if 'sale_price' in price_data:
            price = price_data['sale_price']['amount']
            oldprice = price_data.get('original_price', {}).get('amount', price)
        else:
            price = None
            oldprice = None

        name = product.get('nameEn', '').lower()
        pid = get_pid(product.get('id'), pdict)
        tpid = 'mng' + pid
        
        url = 'https://shop.mango.com' + product.get('url', '')
        
        # Determine gender: try URL first (better for kids), then fallback to folder gender
        url_gender = get_gender_from_url(url)
        if url_gender != "unisex":
            gender_mapped = url_gender
        else:
            gender_mapped = remap_gender(gender)
            
        reference = product.get('reference')

        for color in product.get('colors', []):
            cid = color.get('id')
            cname = color.get('label', '').lower().strip()
            composition = color.get('compositions')
            origin = color.get('originCountries', {}).get('manufacturing')
            
            if not (composition and origin):
                continue

            desc = color.get('description')
            if desc:
                bullets = '. '.join(desc.get('bullets', [])) + '.' if 'bullets' in desc and desc['bullets'] else None
                caps = '\n'.join(desc.get('capsules', [])) if 'capsules' in desc and desc['capsules'] else None
                desc_text = (bullets or '') + ('\n' + caps if caps else '')
            else:
                desc_text = None

            composition_str = ', '.join(composition)
            origin_str = origin.lower().strip()
            images = get_images(color.get('looks', {}))

            for size in color.get('sizes', []):
                sizename = size.get('label', '').strip()
                sizeid = size.get('id')
                
                # Dynamic Age Logic
                if 'month' in sizename or 'year' in sizename:
                    age_range = get_age_range(sizename)
                    if not age_range:
                        continue
                    age_group = get_age_group(age_range)
                else:
                    age_group = ['adult']
                    age_range = ['18y']

                availability = 'in_stock' if size.get('available') else 'out_of_stock'
                sku = 'p' + pid + 'c' + cid + 's' + sizeid
                
                all_products.append({
                    "product_id": tpid,
                    "gender": gender_mapped,
                    "age_group": age_group,
                    "age_range": age_range,
                    "date_of_scraping": parse_launch_date(today_str),
                    "url": url,
                    "title": name,
                    "description": desc_text.strip() if desc_text else None,
                    "product_ref_code": reference,
                    "color_id": f"{tpid}%{cid}",
                    "color_name": cname,
                    "color_ref_code": None,
                    "sku": f"{tpid}%{sku}",
                    "size_name": sizename,
                    "size_ref_code": None,
                    "price": price,
                    "launch_price": oldprice,
                    "availability": availability,
                    "demand": None,
                    "composition": composition_str,
                    "origin": origin_str,
                    "images": images
                })
        return all_products
    return []

def get_folders(path, exclude=None):
    try:
        items = os.listdir(path)
        folders = [f for f in items if os.path.isdir(os.path.join(path, f))]
        if exclude:
            folders = [f for f in folders if f not in exclude]
        return folders
    except Exception:
        return []

def process_footwear(countries, today_date, re_run=False):
    # Load PID remapping
    pid_path = 'mango_pid_remapping.json'
    pdict = {}
    if os.path.exists(pid_path):
        try:
            with open(pid_path, 'r') as f:
                pdict = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load PID remapping file: {e}")

    for country in countries:
        logging.info(f"Processing footwear for {country}")
        
        data_dir = os.path.join(country, today_date, 'Data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        output_file = os.path.join(data_dir, f'{country}_data_footwear.json')
        error_log_file = os.path.join(data_dir, f'{country}_data_process_footwear_log.json')

        # Re-run Logic
        if re_run:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    logging.info(f"Deleted existing output file for {country} due to re-run.")
                except Exception as e:
                    logging.error(f"Failed to delete existing output file: {e}")
            if os.path.exists(error_log_file):
                try:
                    os.remove(error_log_file)
                    logging.info(f"Deleted existing log file for {country} due to re-run.")
                except Exception as e:
                    logging.error(f"Failed to delete existing log file: {e}")
        else:
            # Skip Logic (Memory Efficient)
            if os.path.exists(output_file):
                try:
                    if os.path.getsize(output_file) > 10:
                        logging.info(f"Skipping {country}: existing footwear data present at {output_file}")
                        continue
                except Exception as e:
                    logging.warning(f"Could not check existing output file for {country}: {e}")

        error_logs = []

        json_data_dir = os.path.join(country, today_date, 'Json_data')
        if not os.path.exists(json_data_dir):
            error_logs.append({"error": f"Directory not found: {json_data_dir}", "timestamp": str(datetime.now())})
            with open(error_log_file, 'w') as f:
                json.dump(error_logs, f, indent=4)
            continue
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('[')
                is_first_item = True
                sku_count = 0

                genders = get_folders(json_data_dir)
                
                for gender in genders:
                    category_folder = os.path.join(json_data_dir, gender)
                    categories = get_folders(category_folder)
                    
                    for category in categories:
                        category_path = os.path.join(category_folder, category)
                        try:
                            files = os.listdir(category_path)
                        except Exception as e:
                            error_logs.append({"error": f"Failed to list files in {category_path}: {str(e)}", "timestamp": str(datetime.now())})
                            continue

                        for file in files:
                            if not file.endswith('.json'):
                                continue
                            if any(x in file for x in ['scrap_log', 'summary', 'duplicate_urls']):
                                continue

                            file_path = os.path.join(category_path, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as jf:
                                    data = json.load(jf)

                                # Check if category is "Shoes"
                                families = data.get("product", {}).get("families", [])
                                is_shoes = any(c.get("label", "") == "Shoes" for c in families)
                                
                                if not is_shoes:
                                    continue

                                skus = create_individual_skus(today_date, data, gender, pdict)
                                
                                for sku in skus:
                                    if not is_first_item:
                                        f.write(',\n')
                                    json.dump(sku, f, indent=4, default=str)
                                    is_first_item = False
                                    sku_count += 1

                            except Exception as e:
                                error_logs.append({
                                    "file": file_path,
                                    "error": str(e),
                                    "traceback": traceback.format_exc(),
                                    "timestamp": str(datetime.now())
                                })
                
                f.write('\n]')
                logging.info(f"Saved {sku_count} SKUs to {output_file}")

        except Exception as e:
            error_logs.append({"error": f"Failed to write output file {output_file}: {str(e)}", "timestamp": str(datetime.now())})

        # Save Error Logs (only if there are errors)
        if error_logs:
            try:
                with open(error_log_file, 'w') as f:
                    json.dump(error_logs, f, indent=4)
            except Exception as e:
                logging.error(f"Failed to write error log: {e}")
