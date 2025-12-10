import os
import re
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
    return (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()


async def process_urls(page, gender, category, urls, date_subfolder):
    for url in urls:
        name = url.split("?")[-1]
        if not check_file(gender, category, name, date_subfolder):
            try:
                await page.goto(url, timeout=30000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                product_data = {"url": url}

                # Extract price
                price_tag = soup.find("div", class_="PriceDisplay_sr-price__NA35y")
                if price_tag:
                    price_text = price_tag.get_text(strip=True)
                    if "Price:" in price_text:
                        cleaned_price = price_text.replace("Price:", "").replace("£", "").strip()
                        product_data["Price"] = cleaned_price

                    match = re.search(r"Original price: £([\d.]+), Sale price: £([\d.]+)", price_text)
                    if match:
                        product_data["original_price"] = match.group(1)
                        product_data["sale_price"] = match.group(2)

                specs_section = soup.find("section", {"id": "whats-it-do"})
                if specs_section:
                    offset = None
                    for li in specs_section.find_all("li"):
                        text = li.text.strip()
                        if text.startswith("Offset:"):
                            offset = text.replace("Offset:", "").strip()
                            break
                    product_data["offset"] = offset

                # Accordion sections
                accordion_sections = soup.find_all('div', attrs={'data-testid': 'accordion-detail'})
                for section in accordion_sections:
                    heading = section.find('div', class_='Accordion_accordion--heading__Qzk_d')
                    if heading and 'Product Details' in heading.get_text():
                        details_list = section.find('ul', attrs={'data-bullets': 'true'})
                        if details_list:
                            list_items = details_list.find_all('li')
                            product_data["extra_description"] = [item.get_text(strip=True) for item in list_items]

                # Extract color
                color_tag = soup.find("div", class_="ProductInformation_product-detail-container__Eo03_")
                if color_tag:
                    span_tag = color_tag.find("span", attrs={"aria-hidden": "true"})
                    if span_tag:
                        product_data["color"] = span_tag.get_text(strip=True)

                # Extract JSON data
                data_tag = soup.find("script", attrs={"id": "ld_json_product", "type": "application/ld+json"})
                if data_tag and data_tag.string:
                    try:
                        json_data = json.loads(data_tag.string)
                        if isinstance(json_data, dict):
                            product_data.update(json_data)
                    except Exception as e:
                        logging.warning(f"Invalid JSON data for {url}: {e}")

                # Save JSON with url
                save_json(gender, category, name, product_data, date_subfolder)

            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                continue


async def process_gender_section(page, gender, categories, date_subfolder):
    logging.info(f"Starting USA {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"USA {gender} section complete.")


async def limited_process_gender_section(p, gender, categories, date_subfolder, semaphore):
    async with semaphore:  # Semaphore limits concurrent gender sections
        logging.info(f"Semaphore acquired for gender {gender}")
        browser = await p.chromium.launch(channel='chrome',headless=False) 
        page = await browser.new_page()
        try:
            await process_gender_section(page, gender, categories, date_subfolder)
        except Exception as e:
            logging.error(f"Error in gender section {gender}: {e}")
        finally:
            await browser.close()
            logging.info(f"Semaphore released for gender {gender}")


async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    
    country = 'USA'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / 'Data' / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as json_file:
        urls_dict = json.load(json_file)

    semaphore = asyncio.Semaphore(4)  # allow 4 concurrent gender sections

    async with async_playwright() as p:
        tasks = [
            limited_process_gender_section(p, gender, categories, date_subfolder, semaphore)
            for gender, categories in urls_dict.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    logging.info(f"{country} products completed.")


if __name__ == "__main__":
    asyncio.run(main())
