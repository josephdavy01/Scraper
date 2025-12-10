import os, time, json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def get_product_urls(gender, category, category_code):
    urls = []
    ccode = category_code.replace('=', '%3D')
    try:
        # Navigate to the category page
        url = f"https://www.asics.co.in/graphql?query=query+GetCategories%28%24id%3AString%21%24pageSize%3AInt%21%24currentPage%3AInt%21%24filters%3AProductAttributeFilterInput%21%24sort%3AProductAttributeSortInput%29%7Bcategories%28filters%3A%7Bcategory_uid%3A%7Bin%3A%5B%24id%5D%7D%7D%29%7Bitems%7Buid+...CategoryFragment+__typename%7D__typename%7Dproducts%28pageSize%3A%24pageSize+currentPage%3A%24currentPage+filter%3A%24filters+sort%3A%24sort%29%7B...ProductsFragment+__typename%7D%7Dfragment+CategoryFragment+on+CategoryTree%7Buid+meta_title+meta_keywords+meta_description+image+__typename%7Dfragment+ProductsFragment+on+Products%7Bitems%7Bid+uid+name+price_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7Ddiscount%7Bamount_off+__typename%7D__typename%7Dminimum_price%7Bdiscount%7Bamount_off+percent_off+__typename%7Dfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dsku+small_image%7Burl+__typename%7Dstock_status+rating_summary+__typename+url_key+product_label+product_sub_title+customised%7Dpage_info%7Btotal_pages+__typename%7Dtotal_count+__typename%7D&operationName=GetCategories&variables=%7B%22currentPage%22%3A1%2C%22id%22%3A%22{ccode}%22%2C%22filters%22%3A%7B%22category_uid%22%3A%7B%22eq%22%3A%22{ccode}%22%7D%7D%2C%22pageSize%22%3A24%2C%22sort%22%3A%7B%22position%22%3A%22ASC%22%7D%7D"
        page.goto(url)
        time.sleep(2)
        
        # Parse the page content
        soup = BeautifulSoup(page.content(), 'html.parser')
        json_data = soup.find('pre').text
        if json_data:
            data = json.loads(json_data)
            pages = data['data']['products']['page_info']['total_pages']
            print(f"Total pages for category {category_code}: {pages}")

            for page_num in range(1, pages + 1):
                print(f"Fetching page {page_num} for category {gender}->{category}->{category_code}")
                # Navigate to the category page
                url = f"https://www.asics.co.in/graphql?query=query+GetCategories%28%24id%3AString%21%24pageSize%3AInt%21%24currentPage%3AInt%21%24filters%3AProductAttributeFilterInput%21%24sort%3AProductAttributeSortInput%29%7Bcategories%28filters%3A%7Bcategory_uid%3A%7Bin%3A%5B%24id%5D%7D%7D%29%7Bitems%7Buid+...CategoryFragment+__typename%7D__typename%7Dproducts%28pageSize%3A%24pageSize+currentPage%3A%24currentPage+filter%3A%24filters+sort%3A%24sort%29%7B...ProductsFragment+__typename%7D%7Dfragment+CategoryFragment+on+CategoryTree%7Buid+meta_title+meta_keywords+meta_description+image+__typename%7Dfragment+ProductsFragment+on+Products%7Bitems%7Bid+uid+name+price_range%7Bmaximum_price%7Bfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7Ddiscount%7Bamount_off+__typename%7D__typename%7Dminimum_price%7Bdiscount%7Bamount_off+percent_off+__typename%7Dfinal_price%7Bcurrency+value+__typename%7Dregular_price%7Bcurrency+value+__typename%7D__typename%7D__typename%7Dsku+small_image%7Burl+__typename%7Dstock_status+rating_summary+__typename+url_key+product_label+product_sub_title+customised%7Dpage_info%7Btotal_pages+__typename%7Dtotal_count+__typename%7D&operationName=GetCategories&variables=%7B%22currentPage%22%3A{page_num}%2C%22id%22%3A%22{ccode}%22%2C%22filters%22%3A%7B%22category_uid%22%3A%7B%22eq%22%3A%22{ccode}%22%7D%7D%2C%22pageSize%22%3A24%2C%22sort%22%3A%7B%22position%22%3A%22ASC%22%7D%7D"
                page.goto(url)

                # Parse the page content
                soup = BeautifulSoup(page.content(), 'html.parser')
                json_data = soup.find('pre').text
                if json_data:
                    data = json.loads(json_data)
                    for item in data['data']['products']['items']:
                        product_url = f"https://www.asics.co.in/{item['url_key']}.html"
                        urls.append(product_url)
        else:
            print(f"No data found for category {gender}->{category}->{category_code}")
    except Exception as e:
        print(f"Error fetching product URLs for category {gender}->{category}->{category_code}: {e}")
    return urls

if __name__ == "__main__":
    # save
    country = 'India'
    today_str = datetime.today().strftime("%Y-%m-%d")
    # today_str = '2025-11-27'
    base_path = f'{country}/Data/{today_str}/Item_urls'
    validation_path = f'{country}/Data/{today_str}/Validation'
    os.makedirs(base_path, exist_ok=True)
    os.makedirs(validation_path, exist_ok=True)
    out_file = f'{base_path}/{country}_product_urls.json'
    read_file = f'{base_path}/{country}_category_codes.json'
    
    # Load category structure from step 1
    with open(read_file, 'r', encoding='utf-8') as f:
        category_data = json.load(f)

    temp = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for gender, categories in category_data.items():
            temp[gender] = {}
            for category, items in categories.items():
                urls = get_product_urls(gender, category, items['code'])
                temp[gender][category] = urls

        # Save the collected URLs to a file
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(temp, f, indent=4, ensure_ascii=False)

        context.close()
        browser.close()
        