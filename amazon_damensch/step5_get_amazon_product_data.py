import os
import re
import time
import json
import logging
import requests
from datetime import date
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.common.by import By

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(output_path, category, name, data):
    output_file = f"{output_path}/{category}/{name}.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logging.info(f"Saved product data to {output_file}")

def click_continue_shopping(driver):
    try:
        # The button is a <button> element, not an <input>
        continue_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Continue shopping')]")
        if continue_button:
            continue_button.click()
            logging.info("Clicked on 'Continue Shopping' button.")
            time.sleep(1)  # Wait for the page to load after clicking
    except Exception as e:
        logging.error(f"Error clicking 'Continue Shopping' button: {str(e)}")

def is_validation(soup):
    validation_tag = soup.find('form', {'action': '/errors/validateCaptcha'})
    if validation_tag:
        logging.warning("Validation page detected.")
        return True
    return False

def find_options(soup, url):
    div_tag = soup.find('div', {'id': 'twister-plus-inline-twister', 'class': 'a-section'})
    if div_tag:
        sub_urls = []
        sub_div_tag = div_tag.find('div', {'id': 'inline-twister-expander-content-color_name'})
        if sub_div_tag:
            li_tags = sub_div_tag.find_all('li', attrs={'data-asin': True})
            for li_tag in li_tags:
                asin = li_tag['data-asin']
                sub_url = f"{url.split('/dp/')[0]}/dp/{asin}"
                sub_urls.append(sub_url)
        logging.info(f"Found {len(sub_urls)} options for the product.")
        return True, sub_urls
    return False, []

def refine_price_data(price_data):
    for item in price_data:
        twisterSlotDiv = item.get('Value', {}).get('content', {}).get('twisterSlotDiv', "")
        soup = BeautifulSoup(twisterSlotDiv, 'html.parser')
        current_price_tag = soup.find('span', {'data-a-color': 'base'})
        price_tag = soup.find('span', {'data-a-color': 'secondary'})
        availability_tag = soup.find('span', {'id': 'twisterAvailability'})
        if current_price_tag and price_tag:
            current_price = current_price_tag.get_text().strip()
            price = price_tag.find('span', {'class': 'a-offscreen'}).get_text().strip()
            availability = availability_tag.get_text().strip() if availability_tag else ""
        elif current_price_tag:
            current_price = current_price_tag.get_text().strip()
            price = current_price
            availability = availability_tag.get_text().strip() if availability_tag else ""
        else:
            current_price = None
            price = None
            availability = ""

        item['price_values'] = {
            'current_price': float(current_price.replace('₹', '').replace(',', '')) if current_price else None,
            'price': float(price.replace('₹', '').replace(',', '')) if price else None,
            'availability': availability
        }
    return price_data

def get_sizes_from_api(api_json_data, driver):
    try:
        skus = api_json_data.get('dimensionValuesDisplayData', {})
        main_sku = api_json_data.get('parentAsin', '')
        prefix = "https://www.amazon.in/gp/product/ajax/twisterDimensionSlotsDefault"
        
        asin = api_json_data.get('currentAsin', '')
        asinList = ','.join(skus.keys()) if 'dimensionValuesDisplayData' in api_json_data else ''
        ajaxUrlParams = api_json_data.get('ajaxUrlParams', '').replace('&originalHttpReferer=https%3A%2F%2Fwww.amazon.in%2F', '')

        full_url = f"{prefix}?isDimensionSlotsAjax=1&asinList={asinList}&vs=1&asin={asin}{ajaxUrlParams}&deviceType=web&showFancyPrice=false&twisterFlavor=twisterPlusDesktopConfigurator"
        
        # logging.info(f"Fetching sizes from API: {full_url}")
        
        # Get cookies from Selenium driver
        selenium_cookies = driver.get_cookies()
        
        # Convert Selenium cookies to requests format
        session = requests.Session()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
        
        # Set headers to mimic browser request
        headers = {
            'User-Agent': driver.execute_script("return navigator.userAgent;"),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.amazon.in/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # Make the request
        response = session.get(full_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            response_text = response.text
            # Clean up trailing commas
            cleaned_text = '[' + response_text.replace('&&&', ',') + ']'
            # Parse the JSON
            try:
                price_data = refine_price_data(json.loads(cleaned_text))
            except Exception as e:
                logging.error(f"Error parsing price data JSON: {str(e)}")
                price_data = []

            logging.info("Successfully fetched size data from API")
            return main_sku, skus, price_data
        else:
            logging.warning(f"API request failed with status code: {response.status_code}")
            return '', {}, {}
    except Exception as e:
        logging.error(f"Error extracting sizes from API data: {str(e)}")
        return '', {}, {}

def get_product_data(soup, url, driver):
    try:
        # Extract product data in JSON format
        json_data = {}

        # Product Title
        span_tag = soup.find('span', {'id': 'productTitle'})
        if span_tag:
            product_name = span_tag.get_text().strip()
            json_data['title'] = product_name
        else:
            json_data['title'] = ''

        # Product URL
        json_data['url'] = url

        # Product color
        color_tag = soup.find('span', {'id': 'inline-twister-expanded-dimension-text-color_name'})
        if color_tag:
            color_name = color_tag.get_text().strip()
            json_data['color'] = color_name
        else:
            json_data['color'] = ''
        
        # Product description
        description_tag = soup.find('div', {'class': 'a-expander-content a-expander-partial-collapse-content'})
        if description_tag:
            product_details_tag = description_tag.find('div', {'class':'a-section', 'role':'list'})
            product_details = {}
            if product_details_tag:
                product_fact_tags = product_details_tag.find_all('div', {'class':'a-fixed-left-grid product-facts-detail'})
                if product_fact_tags:
                    for product_fact_tag in product_fact_tags:
                        fact_name_tag = product_fact_tag.find('div', {'class':'a-fixed-left-grid-col a-col-left'})
                        fact_value_tag = product_fact_tag.find('div', {'class':'a-fixed-left-grid-col a-col-right'})
                        if fact_name_tag and fact_value_tag:
                            fact_name = fact_name_tag.get_text().strip().replace(':', '')
                            fact_value = fact_value_tag.get_text().strip()
                            product_details[fact_name] = fact_value

            product_about_tag = description_tag.find('ul', {'class': 'a-unordered-list'})
            abouts = []
            if product_about_tag:
                span_tags = product_about_tag.find_all('span', {'class': 'a-list-item'})
                for span_tag in span_tags:
                    about_text = span_tag.get_text().strip()
                    abouts.append(about_text)

            additional_info_tags = description_tag.find_all('div', {'class':'a-fixed-left-grid product-facts-detail'})
            if additional_info_tags:
                # Filter out product_fact_tags from additional_info_tags
                actual_additional_info_tags = [tag for tag in additional_info_tags if tag not in product_fact_tags]
                additional_info = {}
                for add_info_tag in actual_additional_info_tags:
                    add_name_tag = add_info_tag.find('div', {'class':'a-fixed-left-grid-col a-col-left'})
                    add_value_tag = add_info_tag.find('div', {'class':'a-fixed-left-grid-col a-col-right'})
                    if add_name_tag and add_value_tag:
                        add_name = add_name_tag.get_text().strip().replace(':', '')
                        add_value = add_value_tag.get_text().strip()
                        additional_info[add_name] = add_value

            json_data['description'] = {
                "details": product_details,
                "about": abouts,
                "additional_info": additional_info
            }

            secondary_product_details_tag = soup.find('div', {'id':'detailBulletsWrapper_feature_div'})
            if secondary_product_details_tag:
                secondary_product_details = {}
                li_tags = secondary_product_details_tag.find_all('li')
                for li_tag in li_tags:
                    # Get the full text and split by colon
                    full_text = li_tag.get_text()
                    if ':' in full_text:
                        # Split on the first colon
                        parts = full_text.split(':', 1)
                        if len(parts) == 2:
                            # Clean up the key and value
                            key = parts[0].strip().replace('‏', '').replace('‎', '').strip()
                            value = parts[1].strip().replace('‏', '').replace('‎', '').strip()
                            if key and value:
                                secondary_product_details[key] = value
                json_data['description']['secondary_details'] = secondary_product_details
            else:
                logging.info("Secondary details tag not found")
                json_data['description']['secondary_details'] = {}

            productDescription_tag = soup.find('div', {'data-template-name':'productDescription'})
            if productDescription_tag:
                product_description = productDescription_tag.get_text().strip()
                json_data['description']['product_description'] = product_description

        else:
            logging.info("Description tag not found")
            json_data['description'] = {}

        image_block_tag = soup.find('div', {'id':'imageBlockVariations_feature_div'})
        json_data['images'] = {}
        json_data['color_asin'] = {}
        if image_block_tag:
            script_tags = image_block_tag.find_all('script', {'type':'text/javascript'})
            for script_tag in script_tags:
                script_content = script_tag.string
                if script_content and 'ImageBlockBTF' in script_content:
                    start_index = script_content.find("jQuery.parseJSON('") + len("jQuery.parseJSON('")
                    end_index = script_content.rfind("');")
                    image_data_str = script_content[start_index:end_index].strip()
                    try:
                        # Fix escaped single quotes and other escape sequences
                        image_data_str = image_data_str.replace("\\'", "'").replace('\\\\', '\\')
                        image_data_json = json.loads(image_data_str)
                        json_data['images'] = image_data_json['colorImages']
                        json_data['color_asin'] = image_data_json['colorToAsin']
                    except Exception as e:
                        logging.error(f"Error parsing image JSON data: {str(e)}")
                    break
        else:
            logging.info("Image block tag not found")
        
        if not json_data['images'] and not json_data['color_asin']:
            image_block_tag = soup.find('div', {'id':'imageBlock_feature_div'})
            if image_block_tag:
                script_tags = image_block_tag.find_all('script', {'type':'text/javascript'})
                for script_tag in script_tags:
                    script_content = script_tag.string
                    if script_content and 'ImageBlockATF' in script_content:
                        start_index = script_content.find("data =") + len("data =")
                        end_index = script_content.rfind("};") + 1
                        image_data_str = script_content[start_index:end_index].strip()
                        #save as text file for debugging
                        with open("debug_image_data.txt", "w", encoding="utf-8") as debug_file:
                            debug_file.write(image_data_str)
                        try:
                            # Fix escaped single quotes and other escape sequences
                            image_data_str = image_data_str.replace("\\'", "'").replace('\\\\', '\\')
                            # Remove trailing commas before closing braces/brackets
                            image_data_str = re.sub(r',(\s*[}\]])', r'\1', image_data_str)
                            # Replace JavaScript Date.now() with a placeholder timestamp
                            image_data_str = re.sub(r'Date\.now\(\)', '0', image_data_str)
                            # Replace single quotes with double quotes for valid JSON
                            image_data_str = image_data_str.replace("'", '"')
                            image_data_json = json.loads(image_data_str)
                            json_data['images'] = image_data_json.get('colorImages', {})
                            json_data['color_asin'] = image_data_json.get('colorToAsin', {})
                        except Exception as e:
                            logging.error(f"Error parsing image JSON data: {str(e)}")
                        break

        api_div_tag = soup.find('div', {'id':'twister_feature_div'})
        if api_div_tag:
            script_tags = api_div_tag.find_all('script', {'type':'text/javascript'})
            for script_tag in script_tags:
                script_content = script_tag.string
                if script_content and 'twister-js-init-dpx-data' in script_content:
                    start_index = script_content.find("dataToReturn =") + len("dataToReturn =")
                    end_index = script_content.rfind("};") + 2
                    api_data_str = script_content[start_index:end_index].strip()[:-1]

                    # Clean up the JSON string
                    api_data_str = api_data_str.replace('" + "', '')  # Remove string concatenation
                    
                    # Use regex to remove trailing commas before closing braces/brackets
                    api_data_str = re.sub(r',(\s*[}\]])', r'\1', api_data_str)
                    try:
                        api_json_data = json.loads(api_data_str)
                        main_sku, skus, price_data = get_sizes_from_api(api_json_data, driver)
                        json_data['sizes'] = {'main_sku': main_sku, 'skus': skus, 'price_data': price_data}
                    except Exception as e:
                        logging.error(f"Error parsing API JSON data: {str(e)}")
                    break
        else:
            logging.info("API div tag not found")
            json_data['sizes'] = {}
            
        return json_data
    except Exception as e:
        logging.error(f"Error extracting product data: {str(e)}")
        return {}
    
def get_asins_from_json(json_data):
    asins = []
    try:
        color_asin = json_data.get('color_asin', {})
        for color, asin in color_asin.items():
            tasin = asin.get('asin', '')
            if tasin and tasin not in asins:
                asins.append(tasin)
        
        sizes = json_data.get('sizes', {})
        tasin = sizes.get('main_sku', '')
        if tasin and tasin not in asins:
            asins.append(tasin)
        skus = sizes.get('skus', {})
        for asin, sizes in skus.items():
            if asin not in asins:
                asins.append(asin)
        
        logging.info(f"Extracted {len(asins)} ASINs from product data.")
    except Exception as e:
        logging.error(f"Error extracting ASINs from JSON data: {str(e)}")
    return asins

def upadte_asin_file(asin_file, asin_list):
    with open(asin_file, 'w', encoding='utf-8') as f:
        json.dump(asin_list, f, ensure_ascii=False, indent=4)

def process_url(driver, category, urls, asin_list, output_path, asin_file):
    # Get page source
    page_source = driver.get_page_source()
    soup = BeautifulSoup(page_source, 'html.parser')

    check_validation = is_validation(soup)
    if check_validation:
        click_continue_shopping(driver)

    for url in urls:
        try:
            # Extract product name
            name_tag = url.replace('https://www.amazon.in/', '').split('/dp/')[0]
            code_tag = url.split('/dp/')[1]
            if code_tag in asin_list:
                logging.info(f"ASIN {code_tag} already processed, skipping...")
                continue
            file_name = f'{name_tag}--{code_tag}'

            file_exists = os.path.exists(f"{output_path}/{category}/{file_name}.json")
            if file_exists:
                logging.info(f"File already exists for {file_name}, skipping...")
                continue

            # Navigate to the URL
            logging.info(f"Navigating to: {url}")
            driver.uc_open_with_reconnect(url, reconnect_time=4)
            time.sleep(2)  # Wait for the page to load completely
            
            # Get page source
            page_source = driver.get_page_source()
            soup = BeautifulSoup(page_source, 'html.parser')

            json_data = get_product_data(soup, url, driver)
            if not json_data['title']:
                logging.warning(f"No title found for {file_name}, skipping save...")
            if not json_data['images']:
                logging.warning(f"No images found for {file_name}, skipping save...")

            if json_data['title'] != '' and json_data['images']:
                asins = get_asins_from_json(json_data)
                asin_list.extend(asins)
                upadte_asin_file(asin_file, asin_list)
                save_json(output_path, category, file_name, json_data)
            else:
                check_validation = is_validation(soup)
                if check_validation:
                    click_continue_shopping(driver)
                logging.warning(f"Incomplete data for {file_name}, skipping save...")
        except Exception as e:
            logging.error(f"Error occurred while scraping: {str(e)}")

if __name__ == "__main__":
    # Create output directory based on today's date
    today_str = date.today().strftime('%Y-%m-%d')
    input_path = f'Data/{today_str}/Item_urls'
    output_path = f'Data/{today_str}/Json_data'
    os.makedirs(input_path, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)

    # Initialize driver with UC mode enabled (headless=False for debugging, set to True for production)
    driver = Driver(uc=True, headless=False)
    driver.uc_open_with_reconnect('https://www.amazon.in/', reconnect_time=4)
    time.sleep(1)

    brands = ['damensch']

    try:
        for brand in brands:
            input_file = f'{input_path}/amazon_{brand}_product_urls.json'
            asin_file = f'{input_path}/amazon_{brand}_asins.json'

            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)

            if asin_file and os.path.exists(asin_file):
                with open(asin_file, 'r', encoding='utf-8') as f:
                    asin_list = json.load(f)
            else:
                asin_list = []

            temp = {}
    
            for category, urls in products.items():
                temp[category] = process_url(driver, category, urls, asin_list, output_path, asin_file)
    finally:
        # Close the browser and end the session
        driver.quit()