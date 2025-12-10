
# import datetime
# import os
# import re
# import json
# import time
# from urllib.parse import urljoin
# from bs4 import BeautifulSoup
# from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
# from multiprocessing import Process

# def accept_cookies(page):
#     """Accept TrustArc/Truste cookies if popup appears."""
#     try:
#         page.wait_for_selector('#truste-consent-button', timeout=5000)
#         page.click('#truste-consent-button')
#         print(" Clicked ' Agree and Proceed' cookie button.")
#         time.sleep(2)
#         return True
#     except Exception:
#         pass

#     try:
#         for frame in page.frames:
#             try:
#                 button = frame.query_selector('#truste-consent-button')
#                 if button and button.is_visible():
#                     button.click()
#                     print(" Clicked ' Agree and Proceed' cookie button (iframe).")
#                     time.sleep(2)
#                     return True
#             except Exception:
#                 continue
#     except Exception:
#         pass

#     return False

# def scroll_to_bottom(page, scroll_step=1000, scroll_delay=0.5, max_scrolls=500):
#     """Scroll to the absolute bottom of the page to load all content."""
#     previous_height = page.evaluate("document.body.scrollHeight")
#     scroll_position = 0
#     scroll_count = 0

#     while scroll_count < max_scrolls:
#         page.evaluate(f"window.scrollTo(0, {scroll_position + scroll_step})")
#         scroll_position += scroll_step
#         time.sleep(scroll_delay)

#         current_height = page.evaluate("document.body.scrollHeight")
#         print(f"ℹScrolled to {scroll_position}px, page height: {current_height}px")

#         if scroll_position >= current_height and current_height == previous_height:
#             print(" Reached end of page. No new content loaded.")
#             break

#         previous_height = current_height
#         scroll_count += 1

#     print(f"Completed {scroll_count} scroll steps.")
#     time.sleep(2)

# def scrape_product_details(page, product_url, base_url, failed_urls_log):
#     """Scrape product details from a product page, prioritizing JSON-LD and supplementing with HTML."""
#     print(f" Scraping product: {product_url}")

#     try:
#         page.goto(product_url, wait_until="domcontentloaded", timeout=120000)
#         accept_cookies(page)
#         # scroll_to_bottom(page, scroll_step=1000, scroll_delay=0.5, max_scrolls=500)

#         html = page.content()
#         soup = BeautifulSoup(html, "html.parser")

#         product_data = {}

#         # Extract JSON-LD data
#         json_ld = None
#         for script in soup.find_all('script', type='application/ld+json'):
#             try:
#                 data = json.loads(script.text)
#                 if data.get('@type') == 'Product':
#                     json_ld = data
#                     break
#             except json.JSONDecodeError:
#                 continue

#         # Initialize product data
#         product_data['Date of Scraping'] = datetime.date.today().strftime("%Y-%m-%d")
#         product_data['Product Url'] = product_url

#         # Product ID and Color ID from URL
#         pid = product_url.split('/')[-1].split('.')[0]
#         product_data['Product Id'] = pid.split('_')[0] if '_' in pid else pid
#         color_id = pid.split('_')[-1] if '_' in pid else ''
#         product_data['Color Id'] = color_id
#         product_data['Color Reference Code'] = color_id

#         # JSON-LD fields
#         if json_ld:
#             product_data['Title'] = json_ld.get('name', '')
#             product_data['Description'] = json_ld.get('description', '')
#             product_data['Product Reference Code'] = json_ld.get('sku', pid)
#             product_data['SKU as per the website'] = json_ld.get('sku', pid)
#             product_data['Color Name'] = json_ld.get('color', '')
#             product_data['Gender'] = json_ld.get('gender', 'Unknown')
#             product_data['Age group'] = json_ld.get('ageGroup', 'Adult')
#             product_data['Brand'] = json_ld.get('brand', {}).get('name', 'Skechers')
#             product_data['Images'] = json_ld.get('image', []) if isinstance(json_ld.get('image'), list) else [json_ld.get('image')] if json_ld.get('image') else []

#             # Handle price extraction
#             product_data['Price'] = "Price information not found"
#             product_data['Price Currency'] = 'GBP'
#             product_data['Availability'] = 'Unknown'
#             product_data['MPN'] = json_ld.get('mpn', pid)
#             product_data['In Product Group With ID'] = json_ld.get('inProductGroupWithID', product_data['Product Id'])
#         else:
#             # Fallback to HTML if JSON-LD is missing
#             title = soup.find('h1', class_='c-product-details__product-name')
#             product_data['Title'] = title.text.strip() if title else ''
#             description_content = soup.find('div', class_='c-product-description__content js-product-description-content')
#             product_data['Description'] = description_content.text.strip() if description_content else ''
#             product_data['Product Reference Code'] = pid
#             product_data['SKU as per the website'] = pid
#             color_name = soup.find('span', class_='js-product-details-attr-colorCode')
#             product_data['Color Name'] = color_name.text.strip() if color_name else ''
#             product_data['Gender'] = 'Unknown'
#             product_data['Age group'] = 'Adult'
#             product_data['Brand'] = 'Skechers'
#             product_data['Images'] = []
#             product_data['Price'] = ''
#             product_data['Price Currency'] = 'GBP'
#             product_data['Availability'] = 'Unknown'
#             product_data['MPN'] = pid
#             product_data['In Product Group With ID'] = product_data['Product Id']

#         # Sub Brand (derived from Title)
#         product_data['Sub Brand'] = ' '.join(product_data['Title'].split(' ')[0:2]) if product_data['Title'] and ' ' in product_data['Title'] else ''

#         # Price fallback to HTML
#         if not product_data['Price'] or product_data['Price'] == "Price information not found":
#             price_elements = soup.find_all('span', class_='price__inner')
#             if price_elements:
#                 price_level = price_elements[-1].find('span', class_='sales')
#                 if price_level:
#                     product_data['Price'] = price_level.get_text(strip=True)
#             if not product_data['Price']:
#                 price_value = soup.find('span', class_='value', content=True)
#                 product_data['Price'] = price_value.get_text(strip=True) if price_value else "Price information not found"

#         # Launch Price
#         launch_price_tags = soup.find_all('span', class_='strike-through list d-inline-block')
#         if len(launch_price_tags) == 3:
#             launch_price_tag = launch_price_tags[-1]
#             text = launch_price_tag.get_text(strip=True)
#             match = re.search(r"£?\s*(\d+(\.\d+)?)", text)
#             if match:
#                 product_data['Launch Price'] = f"£{match.group(1)}"
#             else:
#                 product_data['Launch Price'] = product_data.get('Price', 'Not Specified')
#         else:
#             product_data['Launch Price'] = product_data.get('Price', 'Not Specified')

#         # Gender fallback to breadcrumb
#         if product_data['Gender'] == 'Unknown':
#             breadcrumb = soup.find('nav', class_='c-breadcrumb')
#             if breadcrumb:
#                 links = breadcrumb.find_all('a')
#                 for link in links:
#                     href = link.get('href', '').lower()
#                     if 'women' in href:
#                         product_data['Gender'] = 'Women'
#                         break
#                     elif 'men' in href:
#                         product_data['Gender'] = 'Men'
#                         break
#                     elif 'girls' in href or 'boys' in href:
#                         product_data['Gender'] = 'Kids'
#                         break

#         # Age Range
#         if 'kids' in product_url.lower() or product_data['Gender'] == 'Kids':
#             product_data['Age group'] = 'Toddlers'
#             product_data['Age range'] = '0-17'
#         else:
#             product_data['Age range'] = '18+'

#         sizes = []
#         in_stock_count = 0
#         out_of_stock_count = 0

#         # Check for kids' sizes in kid-size-row
#         kid_size_rows = soup.find_all('div', class_='kid-size-row')
#         if kid_size_rows:
#             print(f" Found {len(kid_size_rows)} kid size rows for {product_url}")
#             for row in kid_size_rows:
#                 # Get age group
#                 age_group_elem = row.find('div', class_='c-product-details__attributes__age-group')
#                 age_group = age_group_elem.text.strip() if age_group_elem else 'Unknown'

#                 # Get size buttons within this row
#                 size_buttons = row.select('button.c-product-attributes__item__selector.js-attr-selector')
#                 for button in size_buttons:
#                     size_span = button.find('span', class_='size-value')
#                     if not size_span:
#                         continue
#                     size_name = size_span.text.strip().upper()
#                     size_code = size_span.get('data-attr-value', size_name).strip().upper()
#                     is_unselectable = 'c-product-attributes__item__selector--unselectable' in button.get('class', [])
#                     data_url = button.get('data-url', 'null')
#                     available = 'In Stock' if not is_unselectable and data_url != 'null' else 'Out of Stock'
#                     if available == 'In Stock':
#                         in_stock_count += 1
#                     else:
#                         out_of_stock_count += 1
#                     sizes.append({
#                         'Size name': size_name,
#                         'Size Reference Code': size_code,
#                         'Availability': available,
#                         'Age Group': age_group
#                     })

#         # Fallback to standard size buttons for non-kids products
#         if not sizes:
#             size_buttons = soup.select('button.c-product-attributes__item__selector.button-select-size')
#             for button in size_buttons:
#                 size_name = button.get('data-pdp-attr-value', '').strip().upper()
#                 if not size_name:
#                     continue
#                 size_span = button.find('span', class_='size-value')
#                 size_code = size_span.get('data-attr-value', size_name).strip().upper() if size_span else size_name
#                 available = 'Out of Stock' if 'c-product-attributes__item__selector--unselectable' in button.get('class', []) else 'In Stock'
#                 if available == 'In Stock':
#                     in_stock_count += 1
#                 else:
#                     out_of_stock_count += 1
#                 sizes.append({
#                     'Size name': size_name,
#                     'Size Reference Code': size_code,
#                     'Availability': available,
#                 })

#         if not sizes:
#             print(f" No sizes found for {product_url}")
#         else:
#             print(f" Found {len(sizes)} sizes for {product_url}: {in_stock_count} In Stock, {out_of_stock_count} Out of Stock")

#         product_data['Sizes'] = sizes


#         # Extract features
#         features = []
#         feature_sections = soup.find_all('div', class_='c-product-features-details__detail')
#         for section in feature_sections:
#             section_title = section.find('h2', class_='c-product-features-details__title')
#             if section_title:
#                 section_name = section_title.text.strip()
#                 bullets = section.find('ul', class_='c-product-features-details__bullets')
#                 if bullets:
#                     for li in bullets.find_all('li', class_='c-product-features-details__bullet'):
#                         features.append(f"{section_name}: {li.text.strip()}")

#         # Map features to specific fields
#         product_data['Sole Material'] = next(
#             (f.split(': ')[1] for f in features if f.startswith('Outsole: ')), 'Not Specified'
#         )
#         product_data['Upper Material'] = next(
#             (f.split(': ')[1] for f in features if f.startswith('Upper: ')), 'Not Specified'
#         )
#         product_data['Insole Material'] = next(
#             (f.split(': ')[1] for f in features if f.startswith('Insole: ') or f.startswith('Lining insole: ')), 
#             'Not Specified'
#         )
#         product_data['Closure Type'] = next(
#             (f.split(': ')[1] for f in features if 'lace-up' in f.lower() or 'slip' in f.lower()), 
#             'Not Specified'
#         )
#         product_data['Toe Type'] = 'Not Specified'
#         product_data['Heel Type'] = 'Not Specified'
#         product_data['Weight'] = 'Not Specified'
#         product_data['Heel to Toe Drop'] = 'Not Specified'
#         product_data['Occasion'] = next((f.split(': ')[1] for f in features if 'occasion' in f.lower()), 'Casual')
#         product_data['Made in'] = 'Not Specified'
#         product_data['Features'] = features

#         # Images fallback to HTML
#         if not product_data['Images']:
#             image_elements = soup.select('div.c-pdp-carousel__slider__item img')
#             for img in image_elements:
#                 src = img.get('data-src-actual') or img.get('src')
#                 if src and 'empty.gif' not in src:
#                     full_url = urljoin(base_url, src)
#                     product_data['Images'].append(full_url)
#             product_data['Images'] = list(set(product_data['Images']))

#         return product_data

#     except PlaywrightTimeoutError:
#         print(f" Timeout loading: {product_url}")
#         with open(failed_urls_log, 'a', encoding='utf-8') as f:
#             f.write(f"{datetime.datetime.now()}: Timeout - {product_url}\n")
#         return None
#     except Exception as e:
#         print(f"Error scraping {product_url}: {e}")
#         with open(failed_urls_log, 'a', encoding='utf-8') as f:
#             f.write(f"{datetime.datetime.now()}: Error - {product_url} - {str(e)}\n")
#         return None

# def scrape_country(country, base_url, product_file):
#     """Scrape products for a specific country using multiple tabs in parallel."""
#     print(f"\n Processing {country} ...")

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         pages = [browser.new_page(viewport={"width": 1920, "height": 1080}) for _ in range(3)]

#         # Load base URL in each tab & accept cookies
#         for i, page in enumerate(pages):
#             print(f" Loading base URL in tab {i+1}")
#             page.goto(base_url, wait_until="domcontentloaded")
#             accept_cookies(page)

#         if not os.path.exists(product_file):
#             print(f" Product file not found: {product_file}")
#             browser.close()
#             return

#         with open(product_file, "r", encoding="utf-8") as f:
#             product_links = json.load(f)

#         all_urls = []
#         for cat_name, subcats in product_links.items():
#             for subcat_name, urls in subcats.items():
#                 for url in urls:
#                     all_urls.append((cat_name, subcat_name, url))

#         total_products = 0
#         unique_product_ids = set()
#         failed_urls_log = os.path.join(country, "Data", datetime.date.today().strftime("%Y-%m-%d"), "failed_urls.txt")
#         os.makedirs(os.path.dirname(failed_urls_log), exist_ok=True)

#         # Process in batches of 3 URLs across 3 tabs
#         for i in range(0, len(all_urls),3):
#             batch = all_urls[i:i+3]
#             results = []

#             for j, (cat_name, subcat_name, url) in enumerate(batch):
#                 page = pages[j % len(pages)]
#                 print(f" Tab {j+1}: Scraping {url}")
#                 details = scrape_product_details(page, url, base_url, failed_urls_log)
#                 results.append((cat_name, subcat_name, url, details))

#             # Save results
#             for cat_name, subcat_name, url, details in results:
#                 if not details:
#                     print(f" Skipped product: {url}")
#                     continue

#                 product_id = details['Product Id']
#                 unique_product_ids.add(product_id)

#                 gender_dir = details['Gender']
#                 if gender_dir.lower() == 'female':
#                     gender_dir = 'Women'
#                 elif gender_dir.lower() == 'male':
#                     gender_dir = 'Men'
#                 elif gender_dir.lower() == 'kids':
#                     gender_dir = 'Kids'
#                 else:
#                     gender_dir = 'Unisex'

#                 gender_dir = gender_dir.replace('/', '_').replace('\\', '_')
#                 category_dir = subcat_name.replace('/', '_').replace('\\', '_')

#                 out_dir = os.path.join(country, "Data", datetime.date.today().strftime("%Y-%m-%d"), "Json_data", gender_dir, category_dir)
#                 os.makedirs(out_dir, exist_ok=True)

#                 out_file = os.path.join(out_dir, f"{product_id}_{details['Color Id']}.json")

#                 if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
#                     print(f" {country}: Skipping {product_id}_{details['Color Id']} (already exists)")
#                     continue

#                 with open(out_file, "w", encoding="utf-8") as f:
#                     json.dump(details, f, ensure_ascii=False, indent=4)

#                 total_products += 1

#         print(f"\n Total {total_products} products scraped for {country}")
#         print(f" Unique Product IDs: {len(unique_product_ids)}")
#         print(f" Failed URLs logged to: {failed_urls_log}")

#         browser.close()


# def main():
#     today_str = datetime.date.today().strftime("%Y-%m-%d")
#     today_str = '2025-12-03'
#     countries = {
#         "UK": {
#             "base_url": "https://www.skechers.co.uk/",
#             "product_file": os.path.join("UK", "Data", today_str, "Item_urls", "UK_unique_product_urls.json")
#         },
#         "USA": {
#             "base_url": "https://www.skechers.com/",
#             "product_file": os.path.join("USA", "Data", today_str, "Item_urls", "USA_unique_product_urls.json")
#         }
#     }

#     processes = []
#     for country, config in countries.items():
#         p = Process(
#             target=scrape_country,
#             args=(country, config["base_url"], config["product_file"])
#         )
#         processes.append(p)
#         p.start()

#     for p in processes:
#         p.join()

   

# if __name__ == "__main__":
#     main()
import datetime
import os
import re
import json
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from multiprocessing import Process


def accept_cookies(page):
    """Accept TrustArc/Truste cookies if popup appears."""
    try:
        page.wait_for_selector('#truste-consent-button', timeout=5000)
        page.click('#truste-consent-button')
        print("Clicked 'Agree and Proceed' cookie button.")
        time.sleep(2)
        return True
    except Exception:
        pass

    try:
        for frame in page.frames:
            try:
                button = frame.query_selector('#truste-consent-button')
                if button and button.is_visible():
                    button.click()
                    print("Clicked 'Agree and Proceed' cookie button (iframe).")
                    time.sleep(2)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def scroll_to_bottom(page, scroll_step=1000, scroll_delay=0.5, max_scrolls=500):
    """Scroll to the absolute bottom of the page to load all content."""
    previous_height = page.evaluate("document.body.scrollHeight")
    scroll_position = 0
    scroll_count = 0

    while scroll_count < max_scrolls:
        page.evaluate(f"window.scrollTo(0, {scroll_position + scroll_step})")
        scroll_position += scroll_step
        time.sleep(scroll_delay)

        current_height = page.evaluate("document.body.scrollHeight")
        print(f"ℹScrolled to {scroll_position}px, page height: {current_height}px")

        if scroll_position >= current_height and current_height == previous_height:
            print("Reached end of page. No new content loaded.")
            break

        previous_height = current_height
        scroll_count += 1

    print(f"Completed {scroll_count} scroll steps.")
    time.sleep(2)


def scrape_product_details(page, product_url, base_url, failed_urls_log):
    """Scrape product details from a product page, prioritizing JSON-LD and supplementing with HTML."""
    print(f"Scraping product: {product_url}")

    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=120000)
        accept_cookies(page)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        product_data = {}

        # Extract JSON-LD data
        json_ld = None
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.text)
                if data.get('@type') == 'Product':
                    json_ld = data
                    break
            except json.JSONDecodeError:
                continue

        # Initialize product data
        product_data['Date of Scraping'] = datetime.date.today().strftime("%Y-%m-%d")
        product_data['Product Url'] = product_url

        pid = product_url.split('/')[-1].split('.')[0]
        product_data['Product Id'] = pid.split('_')[0] if '_' in pid else pid
        color_id = pid.split('_')[-1] if '_' in pid else ''
        product_data['Color Id'] = color_id
        product_data['Color Reference Code'] = color_id

        # JSON-LD fields
        if json_ld:
            product_data['Title'] = json_ld.get('name', '')
            product_data['Description'] = json_ld.get('description', '')
            product_data['Product Reference Code'] = json_ld.get('sku', pid)
            product_data['SKU as per the website'] = json_ld.get('sku', pid)
            product_data['Color Name'] = json_ld.get('color', '')
            product_data['Gender'] = json_ld.get('gender', 'Unknown')
            product_data['Age group'] = json_ld.get('ageGroup', 'Adult')
            product_data['Brand'] = json_ld.get('brand', {}).get('name', 'Skechers')
            product_data['Images'] = json_ld.get('image', []) if isinstance(json_ld.get('image'),
                                                                            list) else [json_ld.get('image')] if json_ld.get(
                'image') else []
            product_data['Price'] = "Price information not found"
            product_data['Price Currency'] = 'GBP'
            product_data['Availability'] = 'Unknown'
            product_data['MPN'] = json_ld.get('mpn', pid)
            product_data['In Product Group With ID'] = json_ld.get('inProductGroupWithID',
                                                                   product_data['Product Id'])
        else:
            title = soup.find('h1', class_='c-product-details__product-name')
            product_data['Title'] = title.text.strip() if title else ''
            description_content = soup.find('div',
                                            class_='c-product-description__content js-product-description-content')
            product_data['Description'] = description_content.text.strip() if description_content else ''
            product_data['Product Reference Code'] = pid
            product_data['SKU as per the website'] = pid
            color_name = soup.find('span', class_='js-product-details-attr-colorCode')
            product_data['Color Name'] = color_name.text.strip() if color_name else ''
            product_data['Gender'] = 'Unknown'
            product_data['Age group'] = 'Adult'
            product_data['Brand'] = 'Skechers'
            product_data['Images'] = []
            product_data['Price'] = ''
            product_data['Price Currency'] = 'GBP'
            product_data['Availability'] = 'Unknown'
            product_data['MPN'] = pid
            product_data['In Product Group With ID'] = product_data['Product Id']

        product_data['Sub Brand'] = ' '.join(product_data['Title'].split(' ')[0:2]) if product_data[
            'Title'] and ' ' in product_data['Title'] else ''

        # Price fallback
        if not product_data['Price'] or product_data['Price'] == "Price information not found":
            price_elements = soup.find_all('span', class_='price__inner')
            if price_elements:
                price_level = price_elements[-1].find('span', class_='sales')
                if price_level:
                    product_data['Price'] = price_level.get_text(strip=True)
            if not product_data['Price']:
                price_value = soup.find('span', class_='value', content=True)
                product_data['Price'] = price_value.get_text(strip=True) if price_value else "Price information not found"

        launch_price_tags = soup.find_all('span', class_='strike-through list d-inline-block')
        if len(launch_price_tags) == 3:
            launch_price_tag = launch_price_tags[-1]
            text = launch_price_tag.get_text(strip=True)
            match = re.search(r"£?\s*(\d+(\.\d+)?)", text)
            if match:
                product_data['Launch Price'] = f"£{match.group(1)}"
            else:
                product_data['Launch Price'] = product_data.get('Price', 'Not Specified')
        else:
            product_data['Launch Price'] = product_data.get('Price', 'Not Specified')

        # Gender fallback
        if product_data['Gender'] == 'Unknown':
            breadcrumb = soup.find('nav', class_='c-breadcrumb')
            if breadcrumb:
                links = breadcrumb.find_all('a')
                for link in links:
                    href = link.get('href', '').lower()
                    if 'women' in href:
                        product_data['Gender'] = 'Women'
                        break
                    elif 'men' in href:
                        product_data['Gender'] = 'Men'
                        break
                    elif 'girls' in href or 'boys' in href:
                        product_data['Gender'] = 'Kids'
                        break

        # Age Range
        if 'kids' in product_url.lower() or product_data['Gender'] == 'Kids':
            product_data['Age group'] = 'Toddlers'
            product_data['Age range'] = '0-17'
        else:
            product_data['Age range'] = '18+'

        # Sizes
        sizes = []
        in_stock_count = 0
        out_of_stock_count = 0

        kid_size_rows = soup.find_all('div', class_='kid-size-row')
        if kid_size_rows:
            print(f"Found {len(kid_size_rows)} kid size rows for {product_url}")
            for row in kid_size_rows:
                age_group_elem = row.find('div', class_='c-product-details__attributes__age-group')
                age_group = age_group_elem.text.strip() if age_group_elem else 'Unknown'

                size_buttons = row.select('button.c-product-attributes__item__selector.js-attr-selector')
                for button in size_buttons:
                    size_span = button.find('span', class_='size-value')
                    if not size_span:
                        continue
                    size_name = size_span.text.strip().upper()
                    size_code = size_span.get('data-attr-value', size_name).strip().upper()
                    is_unselectable = 'c-product-attributes__item__selector--unselectable' in button.get('class', [])
                    data_url = button.get('data-url', 'null')
                    available = 'In Stock' if not is_unselectable and data_url != 'null' else 'Out of Stock'
                    if available == 'In Stock':
                        in_stock_count += 1
                    else:
                        out_of_stock_count += 1
                    sizes.append({
                        'Size name': size_name,
                        'Size Reference Code': size_code,
                        'Availability': available,
                        'Age Group': age_group
                    })

        if not sizes:
            size_buttons = soup.select('button.c-product-attributes__item__selector.button-select-size')
            for button in size_buttons:
                size_name = button.get('data-pdp-attr-value', '').strip().upper()
                if not size_name:
                    continue
                size_span = button.find('span', class_='size-value')
                size_code = size_span.get('data-attr-value', size_name).strip().upper() if size_span else size_name
                available = 'Out of Stock' if 'c-product-attributes__item__selector--unselectable' in button.get(
                    'class', []) else 'In Stock'
                if available == 'In Stock':
                    in_stock_count += 1
                else:
                    out_of_stock_count += 1
                sizes.append({
                    'Size name': size_name,
                    'Size Reference Code': size_code,
                    'Availability': available,
                })

        product_data['Sizes'] = sizes

        # Features
        features = []
        feature_sections = soup.find_all('div', class_='c-product-features-details__detail')
        for section in feature_sections:
            section_title = section.find('h2', class_='c-product-features-details__title')
            if section_title:
                section_name = section_title.text.strip()
                bullets = section.find('ul', class_='c-product-features-details__bullets')
                if bullets:
                    for li in bullets.find_all('li', class_='c-product-features-details__bullet'):
                        features.append(f"{section_name}: {li.text.strip()}")

        product_data['Sole Material'] = next((f.split(': ')[1] for f in features if f.startswith('Outsole: ')),
                                             'Not Specified')
        product_data['Upper Material'] = next((f.split(': ')[1] for f in features if f.startswith('Upper: ')),
                                              'Not Specified')
        product_data['Insole Material'] = next(
            (f.split(': ')[1] for f in features if f.startswith('Insole: ') or f.startswith('Lining insole: ')),
            'Not Specified')
        product_data['Closure Type'] = next(
            (f.split(': ')[1] for f in features if 'lace-up' in f.lower() or 'slip' in f.lower()),
            'Not Specified')
        product_data['Toe Type'] = 'Not Specified'
        product_data['Heel Type'] = 'Not Specified'
        product_data['Weight'] = 'Not Specified'
        product_data['Heel to Toe Drop'] = 'Not Specified'
        product_data['Occasion'] = next((f.split(': ')[1] for f in features if 'occasion' in f.lower()), 'Casual')
        product_data['Made in'] = 'Not Specified'
        product_data['Features'] = features

        # Image fallback
        if not product_data['Images']:
            image_elements = soup.select('div.c-pdp-carousel__slider__item img')
            for img in image_elements:
                src = img.get('data-src-actual') or img.get('src')
                if src and 'empty.gif' not in src:
                    full_url = urljoin(base_url, src)
                    product_data['Images'].append(full_url)
            product_data['Images'] = list(set(product_data['Images']))

        return product_data

    except PlaywrightTimeoutError:
        print(f"Timeout loading: {product_url}")
        with open(failed_urls_log, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now()}: Timeout - {product_url}\n")
        return None
    except Exception as e:
        print(f"Error scraping {product_url}: {e}")
        with open(failed_urls_log, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now()}: Error - {product_url} - {str(e)}\n")
        return None


def scrape_country(country, base_url, product_file):
    """Scrape products for a specific country using multiple tabs in parallel."""
    print(f"\nProcessing {country} ...")

    today = datetime.date.today().strftime("%Y-%m-%d")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        pages = [browser.new_page(viewport={"width": 1920, "height": 1080}) for _ in range(3)]

        # Load base URL in each tab
        for i, page in enumerate(pages):
            print(f"Loading base URL in tab {i+1}")
            page.goto(base_url, wait_until="domcontentloaded")
            accept_cookies(page)

        if not os.path.exists(product_file):
            print(f"Product file not found: {product_file}")
            browser.close()
            return

        with open(product_file, "r", encoding="utf-8") as f:
            product_links = json.load(f)

        # --------------------------------------------------------------------
        # ** NEW: BUILD LIST BUT SKIP URLs WHERE JSON ALREADY EXISTS **
        # --------------------------------------------------------------------
        all_urls = []
        for cat_name, subcats in product_links.items():
            for subcat_name, urls in subcats.items():
                for url in urls:

                    pid = url.split('/')[-1].split('.')[0]
                    product_id = pid.split('_')[0] if '_' in pid else pid
                    color_id = pid.split('_')[-1] if '_' in pid else ''

                    # Predict path (placeholder gender "Unisex")
                    safe_cat = subcat_name.replace('/', '_').replace('\\', '_')

                    expected_json = os.path.join(
                        country, "Data", today, "Json_data",
                        "Unisex", safe_cat, f"{product_id}_{color_id}.json"
                    )

                    if os.path.exists(expected_json) and os.path.getsize(expected_json) > 0:
                        print(f"Skipping {url} → JSON already exists")
                        continue

                    all_urls.append((cat_name, subcat_name, url))

        print(f"Total URLs to scrape after skipping: {len(all_urls)}")

        total_products = 0
        unique_product_ids = set()
        failed_urls_log = os.path.join(country, "Data", today, "failed_urls.txt")
        os.makedirs(os.path.dirname(failed_urls_log), exist_ok=True)

        # Process in batches of 3 URLs across 3 tabs
        for i in range(0, len(all_urls), 3):
            batch = all_urls[i:i + 3]
            results = []

            for j, (cat_name, subcat_name, url) in enumerate(batch):
                page = pages[j % len(pages)]
                print(f"Tab {j+1}: Scraping {url}")
                details = scrape_product_details(page, url, base_url, failed_urls_log)
                results.append((cat_name, subcat_name, url, details))

            for cat_name, subcat_name, url, details in results:
                if not details:
                    print(f"Skipped product: {url}")
                    continue

                product_id = details['Product Id']
                unique_product_ids.add(product_id)

                gender_dir = details['Gender']
                if gender_dir.lower() == 'female':
                    gender_dir = 'Women'
                elif gender_dir.lower() == 'male':
                    gender_dir = 'Men'
                elif gender_dir.lower() == 'kids':
                    gender_dir = 'Kids'
                else:
                    gender_dir = 'Unisex'

                safe_cat = subcat_name.replace('/', '_').replace('\\', '_')

                out_dir = os.path.join(
                    country, "Data", today, "Json_data",
                    gender_dir, safe_cat
                )
                os.makedirs(out_dir, exist_ok=True)

                out_file = os.path.join(out_dir, f"{product_id}_{details['Color Id']}.json")

                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    print(f"{country}: Skipping {product_id}_{details['Color Id']} (already exists)")
                    continue

                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(details, f, ensure_ascii=False, indent=4)

                total_products += 1

        print(f"\nTotal {total_products} products scraped for {country}")
        print(f"Unique Product IDs: {len(unique_product_ids)}")
        print(f"Failed URLs logged to: {failed_urls_log}")

        browser.close()


def main():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    # today_str = '2025-12-08'

    countries = {
        "UK": {
            "base_url": "https://www.skechers.co.uk/",
            "product_file": os.path.join("UK", "Data", today_str, "Item_urls", "UK_unique_product_urls.json")
        },
        "USA": {
            "base_url": "https://www.skechers.com/",
            "product_file": os.path.join("USA", "Data", today_str, "Item_urls", "USA_unique_product_urls.json")
        }
    }

    processes = []
    for country, config in countries.items():
        p = Process(target=scrape_country, args=(country, config["base_url"], config["product_file"]))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
