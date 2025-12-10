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
            
def get_availability(gender, tpid, avail_path):
    file_path = f'{avail_path}/{gender}/{tpid}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    return None

# Function to get the style of an image based on its filename
def get_images(images_list):
    images = []
    for image in images_list:
        url = image['baseUrl']
        assettype = image['assetType']
        image_style = 's0'

        if assettype == 'DESCRIPTIVESTILLLIFE':
            image_style = 'n_f_f_c'
        elif assettype == 'LOOKBOOK':
            image_style = 'm_f_f_c'
            
        images.append({
            'url': url,
            'image_style': image_style
        })
    return images

def remap_gender(gender):
    if 'boy' in gender and 'girl' in gender:
        return 'unisex'
    elif 'boy' in gender:
        return 'male'
    elif 'girl' in gender:
        return 'female'
    else:
        return "unisex"
    
def get_materialdetails(materialdetails):
    detaillist = []
    for material in materialdetails:
        name = material['name']
        description = material['description']
        detaillist.append(f'{name} : {description}')

    details = ', '.join(detaillist)
    return details

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
    if 'M' in size:
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

def get_origin(description):
    for i in description:
        if i['title'] == 'countryOfProduction':
            return i['values'].lower()

# Function to create individual JSON objects for each SKU
def create_individual_json(fetch_date, gender, product, avail_path):
    all_products = []
    tpid = product['productId']
    avail_dict = get_availability(gender, tpid, avail_path)

    pid = 'hnm' + tpid
    name = product['productName'].lower()
    agegender = product.get('ageGender')
    if agegender:
        gender = remap_gender(agegender.strip().lower())

        variants = product['variations']
        for vcode, variant in variants.items():
            url = 'https://www2.hm.com' + variant['url']
            cname = variant['name'].lower().strip()
            cid = vcode[-3:]
            description = variant['description']
            oldprice = float(variant['whitePriceValue'])
            price = float(variant.get('redPriceValue', oldprice))
            compositions = ', '.join(variant['compositions'])
            materialdetail = get_materialdetails(variant.get('materialDetails', []))
            composition = f'compositions: {compositions} | materials: {materialdetail}'
            images = get_images(variant['images'])

            origin = get_origin(variant['productAttributes']['description'])

            sizes = variant['sizes']
            for size in sizes:
                sname = size['name']
                if 'Y' in sname or 'M' in sname:
                    age_range = get_age_range(sname)
                    age_group = get_age_group(age_range)
                    sizecode = size['sizeCode']
                    sku = f'{tpid}{cid}s{sname.lower()}'
                    if avail_dict:
                        if 'fewPieceLeft' in avail_dict.keys() and sizecode in avail_dict['fewPieceLeft']:
                            availability = 'low_on_stock'
                        elif 'availability' in avail_dict.keys() and sizecode in avail_dict['availability']:
                            availability = 'in_stock'
                        else:
                            availability = 'out_of_stock'
                    else:
                        availability = 'out_of_stock'

                    entry = {
                        "product_id": pid,
                        "gender": gender,
                        "age_group": age_group,
                        "age_range": age_range,
                        "date_of_scraping": parse_launch_date(fetch_date),
                        "url": url,
                        "title": name,
                        "description": description,
                        "product_ref_code" : vcode[:-3],
                        "color_id": f'{pid}%{cid}',
                        "color_name": cname,
                        "color_ref_code" : vcode,
                        "sku": f'{pid}%{sku}',
                        "size_name": sname,
                        "size_ref_code" : sku,
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

# Function to get names of subfolders in a folder, excluding specified folders
def get_subfolder_names(folder_path, exclude_folders=None):
    exclude_folders = exclude_folders if exclude_folders else []
    return [f.name for f in os.scandir(folder_path) if f.is_dir() and f.name not in exclude_folders]

# Function to process a folder and log SKU details
def process_folder(root_path, avail_path, fetch_date):
    log_data = []

    genders_path = os.path.join(root_path, "Json_data")
    genders = get_subfolder_names(genders_path, ['women', 'men'])
    
    for gender in genders:
        files_path = os.path.join(genders_path, gender)
        files = os.listdir(files_path)
        for file in files:
            file_path = os.path.join(files_path, file)
            print(file_path)
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
                try:
                    skus = create_individual_json(fetch_date, gender, data, avail_path)
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

    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    countries = ['India']
        
    for country in countries:
        collection = db[f'crawler_sink_h&m_{country.lower()}_kids']
        root_path = rf"{country}/Data/{today_str}"
        avail_path = rf"{country}/Data/{today_str}/Availability"
        # Process folder and log SKU details
        process_folder(root_path, avail_path, today_str)

    client.close()