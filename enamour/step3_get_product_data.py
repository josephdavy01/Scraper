import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_path = date_subfolder / 'Json_data' / gender / category
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f'{name}.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")
        
def check_file(gender, category, name, date_subfolder):
    file_exists = (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()
    if file_exists:
        logging.info(f"Skipping file {name}")
    return file_exists

def remove_duplicates(urls):
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls

async def process_urls(page, gender, category, urls, date_subfolder):
    urls = remove_duplicates(urls)
    for url in urls:
        name = url.split("/products/")[-1]
        if not check_file(gender, category, name, date_subfolder):
            try:
                await page.goto(url, wait_until='load',timeout=150000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                data_tag = soup.find("script", {"type": "application/ld+json"})  
                if data_tag and data_tag.string:
                    product_data = json.loads(data_tag.string)
                    color_tag = soup.find("span", {"class": "option-selected-value"})
                    color = color_tag.text.strip() if color_tag else ''
                    product_data["color"] = color
                      
                    image_tags = soup.find_all("div", {"class": "product__media"})
                    if image_tags:
                        images = []
                        for image_tag in image_tags:
                            img_tag = image_tag.find('img')
                            if img_tag:
                                image_url = 'https:' + img_tag.get('src')
                                if image_url not in images:
                                    images.append(image_url)
                        product_data["images"] = images if images else []

                    script_tags = soup.find_all("script", {"type": "application/json"})
                    if script_tags and len(script_tags) >= 3:
                        sizes = {}
                        json_data = json.loads(script_tags[2].string)
                        for item in json_data:
                            sku = item.get("sku")
                            size = item.get("option2")
                            price = item.get("price")
                            old_price = item.get("compare_at_price")
                            if sku and size:
                                sizes[sku] = {"size": size, "price": price, "old_price": old_price}
                        product_data["sizes"] = sizes
                    else:
                        product_data["sizes"] = {}

                # color_name 
                parent_div = soup.find('div', class_='product-color__variant')
                if parent_div:
                    cname = parent_div.get_text(separator=' ', strip=True).lower().strip()
                    if cname:
                        cname = cname.replace('color:', '').strip()
                        product_data["color_name"] = cname
                else:
                    product_data["color_name"] = ''


                    #price
                    sale_price_tag = soup.select_one('.price-item.price-item--sale')
                    sale_price = None
                    if sale_price_tag:
                        sale_price_text = sale_price_tag.get_text(strip=True)
                        sale_price = int(''.join(filter(str.isdigit, sale_price_text)))
                        product_data['current_price'] = sale_price

                    # Extract regular (old) price
                    old_price_tag = soup.select_one('.price-item.price-item--regular')
                    old_price = None
                    if old_price_tag:
                        old_price_text = old_price_tag.get_text(strip=True)
                        old_price = int(''.join(filter(str.isdigit, old_price_text)))
                        product_data['old_price'] = old_price

                # composition
                data_tags = soup.find_all("div", class_="product__accordion accordion quick-add-hidden")
                if len(data_tags) != 3:
                    logging.info(f"Expected 3 accordion tags but found {len(data_tags)} for URL: {url}")
                    product_data["composition"] = ''
                    product_data["origin"] = ''
                else:
                    second_data_tag = data_tags[1]
                    composition_div = second_data_tag.find("div", {"class": "accordion__content rte", "id": "ProductAccordion--template--24340116275478__main"})
                    if composition_div:
                        composition = composition_div.get_text(separator="\n", strip=True)
                        product_data["composition"] = composition if composition else ''
                    else:
                        product_data["composition"] = ''

                    # origin
                    origin_tags = data_tags[-1].find_all("li")
                    if origin_tags:
                        origin = origin_tags[-1].text.strip()
                        product_data["origin"] = origin.split(":")[-1].strip() if ":" in origin else origin.strip()
                    else:
                        product_data["origin"] = ''

                # product_list
                main_div_tag = soup.find('div', class_='product-size-options-dropdown-value')
                if main_div_tag:
                    product_list = []
                    a_tags = main_div_tag.find_all('a')
                    if a_tags:
                        for a_tag in a_tags:
                            href = a_tag.get('href')
                            if href:
                                product_list.append(href.split('/')[-1])
                    product_data["product_list"] = product_list
                else:
                    product_data["product_list"] = [name]
                
                save_json(gender, category, name, product_data, date_subfolder)
            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                continue

async def process_gender_section(playwright, gender, categories, date_subfolder):
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()

    logging.info(f"Starting India {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        for url in urls:
            logging.info(f"{url}")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"India {gender} section complete.")

    await browser.close()

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'India'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as json_file:
        urls_dict = json.load(json_file)

    async with async_playwright() as playwright:  
        for gender, categories in urls_dict.items():
            await process_gender_section(playwright, gender, categories, date_subfolder)

    logging.info(f"{country} products completed.")

if __name__ == "__main__":
    asyncio.run(main())