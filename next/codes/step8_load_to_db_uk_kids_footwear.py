import logging
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
    try:
        return datetime.strptime(date_string, format_string_with_ms)
    except ValueError:
        try:
            return datetime.strptime(date_string, format_string_without_ms)
        except ValueError:
            return datetime.strptime(date_string, format_string_date_only)

# Remapping genders
def remap_gender(gender):
    if gender in ['Older Boys',  'Younger Boys', 'Newborn Boys']:
        return 'male'
    elif gender in ['Older Girls', 'Younger Girls', 'Newborn Girls']:
        return 'female'
    else:
        return 'unisex'
    
# Get images
def get_images(imagelist):
    images = []
    for image in imagelist:
        url = f"https://xcdn.next.co.uk{image['imageUrl']}"
        if image['shotType'] == 'SIP Still Life' and image['imageType'] == 'M':
            image_style = 'n_f_f_c'
        elif image['shotType'] == 'SIP Still Life' and image['imageType'] == 'B':
            image_style = 'n_b_f_c'
        else:
            image_style = 's0'
                
        temp = {
            "url": url,
            "image_style": image_style
        }
        images.append(temp)
    return images
    
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
    if len(age_range) > 1:
        if age_range[1] == '2y':
            if 'y' in age_range[0]:
                age1 = str(int(age_range[0].replace('y', '')) * 12) + 'm'
                age_range = [age1, '24m']
            else:
                age_range = [age_range[0], '24m']
        if age_range[1] == '36m':
            age_range = [age_range[0], '3y']
        if age_range[1] == '48m':
            age_range = [age_range[0], '4y']
        if age_range[0] == '1y':
            age_range = ['12m', age_range[1]]
        if age_range[0] == '24m':
            age_range = ['2y', age_range[1]]

    return age_range

def get_age_range(size):
    if '(' in size:
        size = size.split('(')[0].strip()
    size = size.lower().replace('slim', '').replace('long', '').replace('plus', '').replace('1.5', '18 months').replace(' - ', '-').replace(' m', 'm').replace(' y', 'y').strip()

    age_range = []

    if "first" in size:
        age_range = ['0m']
    elif 'to' in size:
        age_range.append('0m')
        range = int(size.split('to')[1].split('m')[0].strip())
        age_range.append(str(range) + 'm')
    else:
        size = size.split(' ')[-1]
        if 'm' in size and 'y' in size:
            mage = int(size.split('-')[0].split('m')[0])
            age_range.append(str(mage)+'m')
            yage = int(size.split('-')[1].split('y')[0])
            age_range.append(str(yage)+'y')
        elif 'y' in size:
            if '-' not in size:
                age = int(size.split('y')[0])
                age_range.append(str(age)+'y')
            else:
                age_string = size.split('y')[0]
                age1 = age_string.split('-')[0]
                age2 = age_string.split('-')[1]
                age_range.append(str(age1)+'y')
                age_range.append(str(age2)+'y')
        elif 'm' in size:
            if '-' not in size:
                age = int(size.split('m')[0].strip())
                age_range.append(str(age)+'m')
            else:
                age_string = size.split('m')[0]
                age1 = age_string.split('-')[0]
                age2 = age_string.split('-')[1]
                age_range.append(str(age1)+'m')
                age_range.append(str(age2)+'m')

    age_range = remap_age_range(age_range)
    return age_range

# Function to create individual JSON objects for each SKU
def create_individual_json(today_str, product, gender):
    all_products = []
    name = product['title'].lower()
    pid = product['styleNumber']
    mpid = 'nxt' + pid
    cid = product['itemNumber']
    gender = remap_gender(gender)
    url = f"https://www.next.co.uk/style/{pid}/{cid}"
    reference = product['productCode']
    description = product['itemDescription'].get('toneOfVoiceSanitised', None)
    cname = product['colour'].lower().strip()
    composition = product['itemDescription'].get('composition', None)
    origin = product['itemDescription'].get('countryOfOrigin', None)
    images = get_images(product['itemMedia'])

    for size in product['options']['options']:
        sizename = size['name'].strip()
        if 'First' in sizename or 'Yr' in sizename or 'yrs' in sizename or 'Years' in sizename or 'Mth' in sizename or 'Month' in sizename or 'yrs' in sizename:
            age_range = get_age_range(sizename)
            age_group = get_age_group(age_range)

            sizeid = size['value']
            sku = 'p' + pid + 'c' + cid + 's' + sizeid
            sizename = size['name'].strip()
            if size['stockStatus'] == 'InStock':
                availability = 'in_stock'
            elif size['stockStatus'] == 'SoldOut':
                availability = 'out_of_stock'
            else:
                availability = 'out_of_stock'

            if product['priceData']['wasPrice'] == None:
                price = float(size['priceUnformatted'])
                oldprice = price
            else:
                price = float(size['priceUnformatted'])
                oldmin = product['priceData']['price']['minPrice']
                oldmax = product['priceData']['price']['maxPrice']
                newmin = product['priceData']['salePrice']['minPrice']
                newmax = product['priceData']['salePrice']['maxPrice']
                dis_percentage = int(((((oldmax - newmax)/oldmax) + ((oldmin - newmin)/oldmin))/2) * 100)
                oldprice = float(round(price/(100-dis_percentage)*100))

            entry = {
                "product_id": mpid,
                "gender": gender,
                "age_group": age_group,
                "age_range": age_range,
                "date_of_scraping": parse_launch_date(today_str),
                "url": url,
                "title": name,
                "description": description,
                "product_ref_code" : reference,
                "color_id": f'{mpid}%{cid}',
                "color_name": cname,
                "color_ref_code" : None,
                "sku": f'{mpid}%{sku}',
                "size_name": sizename,
                "size_ref_code" : None,
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

keys = [
    "Boots", "Sandals", "Shoes", "Slippers", "Trainers", "Wellies", "Swim Shoes"
]

def get_folders(sub_folders, exclude_folder = ["Men","Women","Women Dresses","Women Lingerie","Men Suits","Men Nightwear","Men Underwear","Women Workwear","Women Swimwear"]):
    folders = os.listdir(sub_folders)
    folders = [folder for folder in folders if folder not in exclude_folder]
    # Filter out any folder that is in the exclude list
    return [folder for folder in folders if '.json' not in folder]

# In your process_jsons function
def process_jsons(today_str, country):
    log_data = []
    gender_folder = os.path.join(country, 'Data', today_str, 'Json_data')
    genders = os.listdir(gender_folder)
    for gender in genders:
        file_folder = os.path.join(gender_folder, gender)
        files = os.listdir(file_folder)
        for file in files:
            file_path = os.path.join(file_folder , file)
            try:
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                skus = create_individual_json(today_str, data, gender)
                category = data.get("category")
                if category in keys:
                    for sku in skus:
                        logging.info(f'Category:{category},Product_id :{sku["product_id"]}, SKU : {sku["sku"]}')
                        collection.insert_one(sku)
                        log_data.append({"file_path": file_path, "sku": sku["sku"], "status": 'new'})
                else:
                    logging.info("Skipping {category}")
            except Exception as e:
                logging.info(file_path)
                logging.info(e)

if __name__ == "__main__":
    # Fetch date from the folder structure
    today_str = date.today().strftime('%Y-%m-%d')
    # today_str = '2025-12-03'

    countries = ['UK']

    # Database details
    connection_string = "mongodb://localhost:27017"
    client = pymongo.MongoClient(connection_string)
    db = client['tg_analytics']

    for country in countries:
        collection = db[f'crawler_sink_next_{country.lower()}_footwear']
        # Process folder and log SKU details
        process_jsons(today_str, country)

    client.close()