import json
import logging
import asyncio
import time
from pathlib import Path
from datetime import date, datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import re

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
    
# Function to check if a file already exists
def check_file(gender, category, name, date_subfolder):
    return (date_subfolder / 'Json_data' / gender / category / f'{name}.json').exists()

async def process_urls(page, gender, category, urls, date_subfolder, successful_urls, failed_urls):
    crawler_delay_ms = 5000

    for url in urls:
        name = url.split("/")[-1].split("#")[0]
        if check_file(gender, category, name, date_subfolder):
            logging.info(f"Skipping {name}, already exists.")
            continue

        logging.info(f"Fetching URL: {url}")
        
        try:
            await page.goto(url, timeout=100000)
            
            # Fixed sleep instead of timeout/selector wait
            await page.wait_for_timeout(6000)

            # Scroll to gallery to trigger lazy loading
            try:
                gallery = page.locator(".gallery-placeholder")
                if await gallery.count() > 0:
                    await gallery.first.scroll_into_view_if_needed()
                    await page.wait_for_selector(".fotorama__img", state="visible", timeout=20000)
            except Exception:
                pass # Continue if scrolling/waiting fails, extracting what's available

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # --- Extraction ---
            product_data = {
                "url": url,
                "name": "",
                "sku": "",
                "price": "",
                "description": "",
                "composition": "",
                "detailed_description": [],
                "variants": []
            }

            # Title - Try multiple selectors
            title_tag = soup.find("h1", {"class": "product-title"})
            if not title_tag:
                title_tag = soup.find("h1", {"class": "page-title"})
            if not title_tag:
                title_tag = soup.find("h1") # Fallback to any h1

            if title_tag:
                product_data["name"] = title_tag.get_text(strip=True)

            # Correct keyword arguments for find
            sku_tag = soup.find("div", class_="value", itemprop="sku")
            if sku_tag:
                product_data["sku"] = sku_tag.get_text(strip=True)
            
            # Price
            price_tag = soup.find("span", {"id":True,"data-price-amount":True,"data-price-type":True})
            if price_tag:
                product_data["price"] = price_tag.get_text(strip=True)

            composition_classes = [
                "col-lg-3 col-md-6 text-center",
                "col-lg-4 text-center",
                "col-lg-3 text-center",
                "col-lg-3 col-md-6 col-sm-6 col-6 text-center",
                "col-lg-3 col-md-4 col-sm-6 col-6 text-center mb-4"
            ]

            composition_tags = []

            for cls in composition_classes:
                composition_tags = soup.find_all("div", class_=cls)
                if composition_tags:
                    break  # stop at first successful match

            if composition_tags:
                product_data["composition"] = [
                    comp.get_text(strip=True)
                    for comp in composition_tags
                    if comp.get_text(strip=True)
                ]


            # Description
            description_div = soup.find("div", {"itemprop":"description"})
            description_div_text = ""
            if description_div:
                lis = description_div.find_all("li")
                if lis:
                    description_div_text = "\n".join([li.get_text(strip=True) for li in lis])
                else:
                    description_div_text = description_div.get_text(strip=True)
            product_data["description"] = description_div_text
 
            # Detailed Description
            product_data.setdefault("detailed_description", [])

            def extract_description(container):
                if not container:
                    return

                paragraphs = container.find_all("p")

                if paragraphs:
                    for p in paragraphs:
                        text = p.get_text(separator=" ", strip=True)
                        if text:
                            product_data["detailed_description"].append(text)
                else:
                    text = container.get_text(separator=" ", strip=True)
                    if text:
                        product_data["detailed_description"].append(text)


            # Main description block
            main_desc_div = soup.find("div", class_="product attribute description")
            extract_description(main_desc_div)

            # Fallback / tab description block
            alt_desc_div = soup.find("div", {"class": "data item content", "id": "description"})
            extract_description(alt_desc_div)

            
            # Variants 
            swatches_locator = page.locator("div.swatch-option.image")
            count = await swatches_locator.count()
            
            # Fallback to color swatches if no image swatches found
            if count == 0:
                swatches_locator = page.locator("div.swatch-option.color")
                count = await swatches_locator.count()

            if count > 0:
                for i in range(count):
                    s_el = swatches_locator.nth(i)
                    try:
                        await s_el.click()
                        await page.wait_for_timeout(2000) 
                    except Exception as click_error:
                        logging.warning(f"Could not click swatch {i}: {click_error}")
                        continue

                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # Finding selected swatch to identify color name
                    selected_color_div = soup.find("div", class_="swatch-option image selected")
                    if not selected_color_div:
                         selected_color_div = soup.find("div", class_="swatch-option color selected")
                    if not selected_color_div:
                        selected_color_div = soup.find(lambda tag: tag.name == "div" and 
                                                    "swatch-option" in tag.get("class", []) and 
                                                    "selected" in tag.get("class", []))
                    
                    color_name = selected_color_div.get("aria-label") if selected_color_div else ""
                    
                    image_urls = []
                    
                    # Image extraction using user's strict filters + fallback
                    div_img = soup.find_all(
                        "div",
                        class_=re.compile(
                            r"fotorama__thumb.*fotorama_vertical_ratio.*fotorama__loaded.*fotorama__loaded--img"
                        )
                    )

                    for div in div_img:
                        img = div.find("img", class_="fotorama__img", src=True)
                        if not img:
                            continue
                        src = img.get("src")
                        if (src and "/media/catalog/product/" in src and 
                            "7ecaf5ade1ac041756e3c8e2118b0b21" in src and 
                            src not in image_urls):
                            image_urls.append(src)
                                
                    # Fallback logic
                    if not image_urls:
                        # logging.info("Specific image selector failed, trying broad search...")
                        all_imgs = soup.find_all("img", src=True)
                        for img in all_imgs:
                            src = img.get("src")
                            if (src and "/catalog/" in src and 
                                "7ecaf5ade1ac041756e3c8e2118b0b21" in src and 
                                src not in image_urls):
                                image_urls.append(src)

                    # logging.info(f"Found {len(image_urls)} images for {url}")

                    # Sizes
                    sizes_divs = soup.find_all("div",{"data-option-label": True, "data-option-tooltip-value": True})
                    available_size = {}

                    for s in sizes_divs:
                        size_text = s.get_text(strip=True)
                        if not size_text:
                            continue
                        is_disabled = (
                            "disabled" in s.get("class", []) or
                            s.has_attr("disabled")
                        )
                        available_size[size_text] = "out_of_stock" if is_disabled else "in_stock"
                    
                    variant_data = {
                        "color": color_name,
                        "images": image_urls,
                        "sizes": available_size
                    }
                    product_data["variants"].append(variant_data)

                sizes_divs = soup.find_all("div", {"data-option-label": True, "data-option-tooltip-value": True})
                available_sizes = []
                if sizes_divs:
                    available_sizes = [s.get_text(strip=True) for s in sizes_divs]
                    # Remove empty strings from list if any
                    available_sizes = [size for size in available_sizes if size]
                
            # Save Data
            if product_data["name"]: 
                save_json(gender, category, name, product_data, date_subfolder)
                logging.info(f"Successfully saved {name}")
                successful_urls.append(url)
            else:
                logging.warning(f"Extracted empty data/name for {url}")
                failed_urls.append(url)

        except Exception as e:
            logging.warning(f"Failed for {url}: {e}")
            failed_urls.append(url)
            # Check for critical connection errors
            if "Target closed" in str(e) or "Connection closed" in str(e):
                logging.error("Critical browser error, waiting before retry...")
                await page.wait_for_timeout(5000)
            else:
                await page.wait_for_timeout(2000)
        
        await page.wait_for_timeout(crawler_delay_ms)

# Function to process gender sections
async def process_gender_section(page, gender, categories, date_subfolder, successful_urls, failed_urls):
    logging.info(f"Starting India {gender} section with {len(categories)} categories...")

    def flatten_urls(data):
        """Recursively extract all URL strings from nested dictionaries or lists."""
        urls = []
        if isinstance(data, dict):
            for value in data.values():
                urls.extend(flatten_urls(value))
        elif isinstance(data, list):
            for item in data:
                urls.extend(flatten_urls(item))
        elif isinstance(data, str):
            urls.append(data)
        return urls

    for category, content in categories.items():
        # Flatten content to get a list of URLs, handling potential nested subcategories
        urls = flatten_urls(content)
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        if urls:
             await process_urls(page, gender, category, urls, date_subfolder, successful_urls, failed_urls)
        else:
             logging.warning(f"  No URLs found for category: {category}")
    logging.info(f"India {gender} section complete.")

# Main function to run the script
async def get_product_data_main():
    start_time = time.time()
    logging.info(f"Script started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    today_str = date.today().strftime('%Y-%m-%d')
    country = 'India'
    logging.info(f'Now starting {country} products...')
    date_subfolder = Path(country) / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / 'Item_urls' / f'{country}_unique_product_urls.json'
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as json_file:
            urls_dict = json.load(json_file)
    except Exception as e:
        logging.error(f"Failed to load JSON file: {e}")
        return

    # Initialize tracking lists
    successful_urls = []
    failed_urls = []
    all_urls = []
    
    # Count total URLs
    def count_urls(data):
        """Recursively count all URL strings from nested dictionaries or lists."""
        urls = []
        if isinstance(data, dict):
            for value in data.values():
                urls.extend(count_urls(value))
        elif isinstance(data, list):
            for item in data:
                urls.extend(count_urls(item))
        elif isinstance(data, str):
            urls.append(data)
        return urls
    
    all_urls = count_urls(urls_dict)

    async with async_playwright() as p:
        # Launch browser once
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            for gender, categories in urls_dict.items():
                await process_gender_section(page, gender, categories, date_subfolder, successful_urls, failed_urls)
                
        except Exception as e:
            logging.error(f"An error occurred during execution: {e}")
        finally:
            await browser.close()
    
    # -------- SAVE DETAILED LOG -------- #
    log_dir = Path(f"{country}/{today_str}/Json_data/Logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    detailed_log_path = log_dir / f'{country.lower()}_scrape_log_detailed.json'
    detailed_log_data = {
        'scrape_date': today_str,
        'country': country,
        'total_urls_to_scrape': len(all_urls),
        'successful_scrapes': len(successful_urls),
        'failed_scrapes': len(failed_urls),
        'success_rate': f"{(len(successful_urls) / len(all_urls) * 100):.2f}%" if all_urls else "0%",
        'successful_urls': successful_urls,
        'failed_urls': failed_urls
    }
    
    with open(detailed_log_path, 'w', encoding='utf-8') as f:
        json.dump(detailed_log_data, f, indent=4, ensure_ascii=False)
    
    logging.info(f"Detailed log saved to: {detailed_log_path}")
    logging.info(f"Total URLs: {len(all_urls)}, Successful: {len(successful_urls)}, Failed: {len(failed_urls)}")

if __name__ == "__main__":
    # Run the script                
    asyncio.run(get_product_data_main())
