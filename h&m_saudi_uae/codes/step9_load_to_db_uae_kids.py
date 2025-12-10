import os
import json
import pymongo
import traceback
import pandas as pd
from datetime import date, datetime

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

# Function to get the style of an image based on its filename
def get_images(images):
    image_dict = {i: img for i, img in enumerate(images)}
    mi, ni = (0, len(image_dict) - 2) if len(image_dict) > 2 else (-1, len(image_dict) - 2 if len(image_dict) > 1 else -1)

    images = [
        {'url': img, 'image_style': 'm_f_f_c' if i == mi else 'n_f_f_c' if i == ni else 's0'}
        for i, img in image_dict.items()
    ]
    return images

def get_gender(pid, pids):
    for gender, plist in pids.items():
        if pid in plist:
            return gender
    return "unisex"
    
def get_age_group(age_range):
    new_born_ages = ['0m', '1m', '2m', '3m', '4m', '5m', '6m']
    baby_ages = ['7m', '8m', '9m', '10m', '11m', '12m', '13m', '14m', '15m', '16m', '17m', '18m', '19m', '20m', '21m', '22m', '23m', '24m']
    junior_ages = ['2y', '3y', '4y', '5y', '6y', '7y']
    senior_ages = ['8y', '9y', '10y', '11y', '12y']
    teen_ages = ['13y', '14y', '15y', '16y', '17y']
    adult_ages = ['18y']

    age_goup_list = ['new_born', 'baby', 'junior', 'senior', 'teen', 'adult']

    if len(age_range) == 1:
        if age_range[0] in new_born_ages:
            return ['new_born']
        elif age_range[0] in baby_ages:
            return ['baby']
        elif age_range[0] in junior_ages:
            return ['junior']
        elif age_range[0] in senior_ages:
            return ['senior']
        elif age_range[0] in teen_ages:
            return ['teen']
        elif age_range[0] in adult_ages:
            return ['adult']
    else:
        age_group = []
        start = age_range[0]
        end = age_range[-1]

        if start in new_born_ages:
            sindex = age_goup_list.index('new_born')
        elif start in baby_ages:
            sindex = age_goup_list.index('baby')
        elif start in junior_ages:
            sindex = age_goup_list.index('junior')
        elif start in senior_ages:
            sindex = age_goup_list.index('senior')
        elif start in teen_ages:
            sindex = age_goup_list.index('teen')
        elif start in adult_ages:
            sindex = age_goup_list.index('adult')
        
        if end in new_born_ages:
            eindex = age_goup_list.index('new_born')
        elif end in baby_ages:
            eindex = age_goup_list.index('baby')
        elif end in junior_ages:
            eindex = age_goup_list.index('junior')
        elif end in senior_ages:
            eindex = age_goup_list.index('senior')
        elif end in teen_ages:
            eindex = age_goup_list.index('teen')
        elif end in adult_ages:
            eindex = age_goup_list.index('adult')

        for i in range(sindex, eindex + 1):
            age_group.append(age_goup_list[i])

        if age_group == []:
            age_group = ['others']
            
        return age_group

def remap_age_range(age_range):
    if len(age_range) == 2 and age_range[1] == '2y':
        fi = int(float(age_range[0].replace('y', '')) * 12)
        si = int(float(age_range[1].replace('y', '')) * 12)
        age_range = [str(fi) + 'm', str(si) + 'm']
    elif len(age_range) == 2 and age_range[0] == '24m':
        fi = int(float(age_range[0].replace('m', '')) / 12)
        si = int(float(age_range[1].replace('m', '')) / 12)
        age_range = [str(fi) + 'y', str(si) + 'y']

    if age_range[0] == '1y':
        age_range = ['12m', age_range[1]]
    if age_range[0] == '1.5y':
        age_range = ['18m', age_range[1]]
    if age_range == ['2y']:
        age_range = ['24m']
    return age_range

def get_age_range(size):
    if '½' in size or '<' in size:
        size = size.replace('½', '.5').replace('<', '')
    if '-14Y+' in size:
        size = size.replace('-14Y+', '-16Y')

    if '14Y+' == size:
        return ['15y', '16y']
    if 'M' in size and len(size)> 1:
        if '-' in size:
            tsize = size.replace('M', '')
            srange = tsize.split('-')
            age_range = [srange[0] + 'm', srange[1] + 'm']
            age_range = remap_age_range(age_range)
            return age_range
        else:
            size = size.replace('M', 'm')
            return [size]
    elif 'Y' in size:
        if '-' in size:
            tsize = size.replace('Y', '')
            srange = tsize.split('-')
            age_range = [srange[0] + 'y', srange[1] + 'y']
            age_range = remap_age_range(age_range)
            return age_range
        else:
            size = size.replace('Y', 'y')
            age_range = remap_age_range([size])
            return age_range
    return None

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, data, filename):
    all_products = []
    product = data['product']
    prices = data['price']
    sizes = data['sizes']
    attributes = data['attributes']
    breadcrumb = data['breadcrumb']

    # Breadcrumb
    if breadcrumb:
        breadcrumb_text = ''
        for itemlist in breadcrumb['itemListElement']:
            breadcrumb_text += itemlist['item']['name'].lower() + '_'

        if 'girl' in breadcrumb_text:
            gender = 'female'
        elif 'boy' in breadcrumb_text:
            gender = 'male'
        else:
            gender = 'unisex'
    else:
        gender = 'unisex'

    # Attributes
    composition_data = attributes.get('Composition')
    if composition_data:
        composition_list = json.loads(composition_data)
        composition = 'compositions: ' + ', '.join(composition_list)
    else:
        composition = None

    # Price
    if 'regularprice' in prices.keys():
        price = float(prices['specialprice'])
        if not price or price == 0:
            return
        oldprice = float(prices['regularprice'])
    else:
        price = float(prices['specialprice'])
        oldprice = price

    tpid = product['sku'][:-3]
    pid = 'hnm' + tpid
    name = product['name'].lower()
    handle = filename.split('.')[0]
    url = f'https://ae.hm.com/en/{handle}'
    description = product['description']
    images = get_images(product['image'])

    # Color
    cname = data['color'].lower().strip()
    cid = product['sku'][-3:]

    for size, availability in sizes.items():
        if ('Y' in size or 'M' in size) and not('M' in size and 'Y' in size):
            age_range = get_age_range(size)
            age_group = get_age_group(age_range)
            sku = f'{tpid}{cid}s{size.lower()}'
            entry = {
                "product_id": pid,
                "gender": gender,
                "age_group": age_group,
                "age_range": age_range,
                "date_of_scraping": parse_launch_date(fetch_date),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code" : tpid,
                "color_id": f'{pid}%{cid}',
                "color_name": cname,
                "color_ref_code" : f'{tpid}{cid}',
                "sku": f'{pid}%{sku}',
                "size_name": size,
                "size_ref_code" : None,
                "price": price,
                "launch_price": oldprice,
                "availability": availability,
                "demand": None,
                "composition": composition,
                "origin": None,
                "images": images
            }
            all_products.append(entry)
    return all_products

# Function to get names of subfolders in a folder, excluding specified folders
def get_subfolder_names(folder_path, exclude_folders=None):
    exclude_folders = exclude_folders if exclude_folders else []
    return [f.name for f in os.scandir(folder_path) if f.is_dir() and f.name not in exclude_folders]

# Function to process a folder and log SKU details
def process_folder(root_path, fetch_date):
    log_data = []

    genders_path = os.path.join(root_path, "Json_data")
    genders = get_subfolder_names(genders_path, ['Men', 'Women'])
    
    for gender in genders:
        files_path = os.path.join(genders_path, gender)
        files = os.listdir(files_path)
        for file in files:
            file_path = os.path.join(files_path, file)
            print(file_path)
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
                try:
                    skus = create_individual_json(fetch_date, data, file)
                    for sku in skus:
                        print(f'Inserting pid: {sku["product_id"]}, sku: {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                except Exception as e:
                    print(f"Error processing file: {file_path}: {e}")
                    traceback.print_exc()
            
if __name__ == "__main__":
    # Get today's date and format it
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = "2025-12-05" 


    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['UAE']
        
    for country in countries:
        collection = db[f'crawler_sink_h&m_{country.lower()}_kids']
        root_path = rf"{country}/Data/{today_str}"
        # Process folder and log SKU details
        process_folder(root_path, today_str)

    client.close()