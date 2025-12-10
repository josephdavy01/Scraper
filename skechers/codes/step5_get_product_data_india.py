import json
import logging
import asyncio
import html
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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
    return (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()

async def process_urls(page, gender, category, urls, date_subfolder):
    for url in urls:
        name = url.split('/')[-1].split('.')[0]
        if not check_file(gender, category, name, date_subfolder):
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                html_content = await page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                all_product_data = {
                    'url': url
                }

                # Extract script data
                data_tags = soup.find_all("script", {'type': 'application/ld+json'})
                if data_tags:
                    for tag in data_tags:
                        if tag.string:
                            try:
                                product_data = json.loads(tag.string)
                                all_product_data['script_data'] = product_data
                                break
                            except json.JSONDecodeError as e:
                                logging.warning(f"JSON decode error for {url}: {e}")

                # Extract analytics data
                main_content = soup.find("div", {"role": "main", "id": "maincontent"})
                if main_content:
                    analytics_div = main_content.find("div", {"data-analytics-data": True})
                    if analytics_div:
                        analytics_data = analytics_div.get("data-analytics-data")
                        if analytics_data:
                            try:
                                decoded_data = html.unescape(analytics_data)
                                analytics_json = json.loads(decoded_data)
                                all_product_data['analytics_data'] = analytics_json
                            except json.JSONDecodeError:
                                logging.warning(f"Analytics data JSON decode error for {url}")

                # Extract available sizes
                size_container = soup.find("div", {"class": "select-size"})
                if size_container:
                    size_buttons = size_container.find_all("button", class_="size-select")
                    available_sizes = []
                    for button in size_buttons:
                        if "disabled" not in button.get("class", []) and "size-disabled" not in button.get("class", []):
                            size_text = button.get_text(strip=True)
                            available_sizes.append(size_text)
                    all_product_data['available_sizes'] = available_sizes

                # Extract description with structured key features
                description_container = soup.find("div", {"class": "col-sm-12 col-md-8 col-lg-9 value content pl-0 details-page-long-description"})
                if description_container:
                    main_desc = description_container.find("div")
                    main_description = main_desc.get_text(strip=True) if main_desc else ""

                    key_features = []
                    strong_tags = description_container.find_all("strong")
                    for strong in strong_tags:
                        if "Key Features" in strong.get_text():
                            next_div = strong.find_next_sibling("div")
                            if next_div:
                                ul_tag = next_div.find("ul")
                                if ul_tag:
                                    for li in ul_tag.find_all("li"):
                                        key_features.append(li.get_text(strip=True))
                            break

                    design_details = []
                    for strong in strong_tags:
                        if "Design Details" in strong.get_text():
                            next_div = strong.find_next_sibling("div")
                            if next_div:
                                ul_tag = next_div.find("ul")
                                if ul_tag:
                                    for li in ul_tag.find_all("li"):
                                        design_details.append(li.get_text(strip=True))
                            break

                    full_description_text = description_container.get_text(separator="\n", strip=True)

                    price_tag = soup.find("div", {"class": "price"})
                    prices = {}
                    if price_tag:
                        sale_tag = price_tag.find("span", {"class": "sales"})
                        if sale_tag:
                            new_price = sale_tag.find('span').get_text(strip=True)
                            strike_through_tag = price_tag.find('span', {"class": "strike-through"})
                            if strike_through_tag:
                                old_price = strike_through_tag.get_text(strip=True)
                            else:
                                old_price = new_price
                        else:
                            new_price = price_tag.find('span', {"class": "strike-through"}).get_text(strip=True)
                            old_price = new_price
                        prices['new_price'] = new_price
                        prices['old_price'] = old_price
                    else:
                        print(f"Price not found for {url}")


                    all_product_data['description'] = main_description
                    all_product_data['key_features'] = key_features
                    all_product_data['design_details'] = design_details
                    all_product_data['full_description_text'] = full_description_text
                    all_product_data['price'] = prices

                # Extract Legal Metrology section as key-value pairs
                legal_metrology_dict = {}
                legal_metrology_div = soup.find("div", {"id": "legalMetrology"})

                if legal_metrology_div:
                    rows = legal_metrology_div.find_all("div", class_="row")
                    for row in rows:
                        key_tag = row.find("p", class_="p-heading")
                        value_tag = row.find("p", class_="font-normal")
                        if key_tag and value_tag:
                            key = key_tag.get_text(strip=True).rstrip(":")
                            value = value_tag.get_text(separator=" ", strip=True)
                            legal_metrology_dict[key] = value

                    # Handle customer care section
                    content_asset = legal_metrology_div.find("div", class_="content-asset")
                    if content_asset:
                        customer_care = {}
                        for p in content_asset.find_all("p", class_="font-normal"):
                            text = p.get_text(strip=True)
                            if '-' in text:
                                parts = text.split('-', 1)
                                key, val = parts[0].strip(), parts[1].strip()
                                customer_care[key] = val
                            else:
                                customer_care["Additional Info"] = text
                        if customer_care:
                            legal_metrology_dict["Customer care cell"] = customer_care

                    all_product_data['legal_metrology'] = legal_metrology_dict

                # Save the combined data
                save_json(gender, category, name, all_product_data, date_subfolder)

            except PlaywrightTimeoutError:
                logging.error(f"Timeout while loading URL: {url}")
            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                continue

async def process_gender_section(playwright, gender, categories, date_subfolder):
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()

    logging.info(f"Starting India {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"India {gender} section complete.")

    await browser.close()

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'India'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)
    (date_subfolder / 'Item_urls').mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as json_file:
        urls_dict = json.load(json_file)

    async with async_playwright() as p:
        tasks = []

        for gender, categories in urls_dict.items():
            tasks.append(process_gender_section(p, gender, categories, date_subfolder))

        await asyncio.gather(*tasks)

    logging.info(f"{country} products completed.")

if __name__ == "__main__":
    asyncio.run(main())
