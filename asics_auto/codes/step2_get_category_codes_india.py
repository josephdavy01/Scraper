import re, os, time, json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def get_category_code(category_url, page):
    try:
        page.goto(category_url)
        time.sleep(2)
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        script_tags = soup.find_all('script', {'nonce': ''})
        for script_tag in script_tags:
            if script_tag.string and 'INLINED_PAGE_TYPE' in script_tag.string:
                script = script_tag.string
                match = re.search(r"JSON\.parse\('(.+?)'\.replace", script)
                if match:
                    json_str = match.group(1).replace('&quot;', '"')
                    data = json.loads(json_str)
                    category_code = data['uid']
                    print(category_url, category_code)
                    return category_code
        return None
    except Exception as e:
        print(f'Error getting category code for {category_url}: {e}')
        return None

def get_category_code_with_retry(category_url, page, retries=3):
    for attempt in range(retries):
        code = get_category_code(category_url, page)
        if code is not None:
            return code
        print(f"Retry {attempt+1} for {category_url}...")
        time.sleep(2)
    return None

def recheck_category_code(data, page):
    for gender, categories in data.items():
        for category, items in categories.items():
            if items['code'] is None:
                category_code = get_category_code_with_retry(items['url'], page)
                data[gender][category]['code'] = category_code
    return data

if __name__ == "__main__":
    # get category code
    country = 'India'
    today_str = datetime.today().strftime("%Y-%m-%d")
    
    base_path = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_path, exist_ok=True)
    read_file = f'{base_path}/{country}_category_urls.json'
    write_file = f'{base_path}/{country}_category_codes.json'
    temp = {}

    with open(read_file, 'r') as f:
        data = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_page()

        # Initial fetch with retry
        for gender, categories in data.items():
            temp[gender] = {}
            for category, url in categories.items():
                category_code = get_category_code_with_retry(url, page)
                temp[gender][category] = {'url': url, 'code': category_code}
        
        # Save after initial fetch
        with open(write_file, 'w') as f:
            json.dump(temp, f, indent=4)

        # Recheck missing codes with retry
        temp = recheck_category_code(temp, page)

        # Save after recheck
        with open(write_file, 'w') as f:
            json.dump(temp, f, indent=4)

        browser.close()