from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time, json, os
from datetime import datetime
from typing import Dict, List

def save_to_json(json_path, gender, category, name, json_data):
    try:
        # Build directory path safely
        category_path = os.path.join(json_path, gender, category)
        os.makedirs(category_path, exist_ok=True)

        # Build file path safely
        file_path = os.path.join(category_path, f"{name}.json")

        # Save product data
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)

        print(f"Product data saved to: {file_path}")

    except Exception as e:
        print(f"Error while saving the data: {e}")

# Check if file already exists
def check_file(gender, category, name, json_path):
    file_path = f'{json_path}/{gender}/{category}/{name}.json'
    return os.path.exists(file_path)

def get_product_data(json_path, gender, category, urls):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        for turl in urls:
            url_code = turl.split('/')[-1].split('.')[0]
            if not check_file(gender, category, url_code, json_path):
                try:
                    url = f"https://www.asics.co.in/graphql?query=query+getProductDetailForProductPage%28%24urlKey%3AString%21%29%7Bproducts%28filter%3A%7Burl_key%3A%7Beq%3A%24urlKey%7D%7D%29%7Bitems%7Bid+uid+...ProductDetailsFragment+__typename%7D__typename%7D%7Dfragment+ProductDetailsFragment+on+ProductInterface%7B__typename+categories%7Buid+breadcrumbs%7Bcategory_uid+__typename%7D__typename%7Ddescription%7Bhtml+__typename%7Dshort_description%7Bhtml+__typename%7Did+uid+media_gallery_entries%7Buid+label+position+disabled+file+video_content%7Bvideo_url+__typename%7D__typename%7Dmeta_title+meta_keyword+meta_description+gumlet_url+gumlet_thumb_url+name+product_sub_title+per_pair+promo_url+price%7BregularPrice%7Bamount%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dprice_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7Ddiscount%7Bamount_off+__typename%7D__typename%7Dminimum_price%7Bdiscount%7Bamount_off+percent_off+__typename%7Dfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dsku+small_image%7Burl+__typename%7Dstock_status+url_key+url_suffix+size_chart_block+pdp_offer_content+catalog_width+product_label+custom_attributes%7Bselected_attribute_options%7Battribute_option%7Buid+label+is_default+__typename%7D__typename%7Dentered_attribute_value%7Bvalue+__typename%7Dattribute_metadata%7Buid+code+label+attribute_labels%7Bstore_code+label+__typename%7Ddata_type+is_system+entity_type+ui_input%7Bui_input_type+is_html_allowed+__typename%7D...on+ProductAttributeMetadata%7Bused_in_components+__typename%7D__typename%7D__typename%7D...on+ConfigurableProduct%7Bconfigurable_options%7Battribute_code+attribute_id+uid+label+values%7Buid+default_label+label+store_label+use_default_value+value_index+swatch_data%7B...on+ImageSwatchData%7Bthumbnail+__typename%7Dvalue+__typename%7D__typename%7D__typename%7Dvariants%7Battributes%7Bcode+value_index+__typename%7Dproduct%7Buid+media_gallery_entries%7Buid+disabled+file+label+position+__typename%7Dsku+url_key+url_suffix+stock_status+per_pair+pdp_offer_content+price%7BregularPrice%7Bamount%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dprice_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7Ddiscount%7Bamount_off+__typename%7D__typename%7Dminimum_price%7Bdiscount%7Bamount_off+percent_off+__typename%7Dfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dcustom_attributes%7Bselected_attribute_options%7Battribute_option%7Buid+label+is_default+__typename%7D__typename%7Dentered_attribute_value%7Bvalue+__typename%7Dattribute_metadata%7Buid+code+label+attribute_labels%7Bstore_code+label+__typename%7Ddata_type+is_system+entity_type+ui_input%7Bui_input_type+is_html_allowed+__typename%7D...on+ProductAttributeMetadata%7Bused_in_components+__typename%7D__typename%7D__typename%7D__typename%7D__typename%7Dcolour+color_variants%7Bid+sku+url_key+is_available+is_current+image_url+image_path+more_plus+__typename%7Dwidth+tech_materials+__typename%7D%7D&operationName=getProductDetailForProductPage&variables=%7B%22urlKey%22%3A%22{url_code}%22%7D"
                    page.goto(url)
                    
                    html_content = page.content()
                    page_source= BeautifulSoup(html_content, 'html.parser')
                    json_tag = page_source.find('pre')
                    json_data = json.loads(json_tag.string)
                    
                    save_to_json(json_path, gender, category, url_code, json_data)
                except:
                    print(f'Error processing: {url_code}')
        browser.close()

if __name__ == "__main__":
    # save
    country = 'India'
    today_str = datetime.today().strftime("%Y-%m-%d")
    # today_str = '2025-11-29'
    base_path = f'{country}/Data/{today_str}/Item_urls'
    json_path = f'{country}/Data/{today_str}/Json_data'
    os.makedirs(base_path, exist_ok=True)
    os.makedirs(json_path, exist_ok=True)

    read_file = f'{base_path}/{country}_unique_product_urls.json'

    # Load category structure from step 1
    with open(read_file, 'r', encoding='utf-8') as f:
        url_dict = json.load(f)
        
    for gender, categories in url_dict.items():
        for category, urls in categories.items():
            get_product_data(json_path, gender, category, urls)
