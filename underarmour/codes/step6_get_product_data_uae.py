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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def save_json(gender, category, name, json_data, date_subfolder):
    try:
        json_path = date_subfolder / "Json_data" / gender / category
        json_path.mkdir(parents=True, exist_ok=True)
        with open(json_path / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error saving JSON file for product {name}: {e}")


def check_file(gender, category, name, date_subfolder):
    return (date_subfolder / "Json_data" / gender / category / f"{name}.json").exists()


async def process_urls(page, gender, category, urls, date_subfolder):
    for url in urls:
        name = url.split("/")[-1].replace(".html", "")
        if not check_file(gender, category, name, date_subfolder):
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                product_data = {"url": url}

                # product description JSON-LD
                script_tag = soup.find("script", type="application/ld+json")
                if script_tag:
                    raw_json = script_tag.get_text(strip=True)
                    try:
                        data = json.loads(raw_json)
                        product_data["json_ld"] = data
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON-LD on {url}")

                # color
                parent_color_tag = soup.find("div", class_="product-detail__general-attributes")
                if parent_color_tag:
                    child_tag = parent_color_tag.find(
                        "div", class_="product-detail__attributes attributes full-product-detail"
                    )
                    if child_tag:
                        sub_child = child_tag.find("div", class_="variantColor attribute__headline")
                        if sub_child:
                            color_vendor_tags = sub_child.find_all(
                                "span", class_="attribute__selected-color-vendor js-selected-color-vendor"
                            )
                            color_value_tags = sub_child.find_all(
                                "span", class_="attribute__selected-color-value js-selected-color-value"
                            )
                            colors = []
                            if color_vendor_tags:
                                colors.extend(tag.get_text(strip=True) for tag in color_vendor_tags)
                            if color_value_tags:
                                colors.extend(tag.get_text(strip=True) for tag in color_value_tags)
                            product_data["Color"] = " - ".join(colors) if colors else None
                        else:
                            product_data["Color"] = None
                    else:
                        product_data["Color"] = None
                else:
                    product_data["Color"] = None

                # specs (weight + composition)
                specs_section = soup.find("div", id="tab-content-categorylongDescription")
                weight_value = None
                composition_value = None
                if specs_section:
                    li_tags = specs_section.find_all("li")
                    for li in li_tags:
                        text = li.get_text(strip=True)
                        if text.startswith("Weight:"):
                            weight_value = text.replace("Weight:", "").strip()
                        if "%" in text and not composition_value:
                            composition_value = text.strip().replace("Body:", "")
                product_data["Weight"] = weight_value
                product_data["composition"] = composition_value

                # price
                price_section = soup.find("div", class_="product-detail__priceline")
                original_price = None
                sale_price = None

                if price_section:
                    # Look for original price (strike-through)
                    original = price_section.find("span", class_="strike-through list")
                    if original:
                        original_price = (
                            original.get_text(strip=True)
                            .replace("AED", "")
                            .replace("Price reduced from", "")
                            .replace("to", "")
                            .strip()
                        )

                    # Look for current sale price
                    sale = price_section.find("span", class_="price__regular")
                    if not sale:  # fallback if structure differs
                        sale = price_section.find("span", class_="sales") or price_section.find("span", class_="price__value")

                    if sale:
                        sale_price = (
                            sale.get_text(strip=True)
                            .replace("AED", "")
                            .replace("Now", "")
                            .strip()
                        )

                # Save into product data
                product_data["OriginalPrice"] = original_price
                product_data["SalePrice"] = sale_price


                # images
                images = set()  # use a set to avoid duplicates

                for picture in soup.find_all("picture", class_="js-primary-images-thumbnail"):
                    sources = picture.find_all("source")
                    for src in sources:
                        srcset = src.get("srcset") or src.get("data-srcset")
                        if not srcset:
                            continue
                        # srcset may contain multiple URLs separated by commas
                        for part in srcset.split(","):
                            url = part.split()[0]
                            if "sw=1400" in url:  #only keep 1400px images
                                images.add(url)

                product_data["Images"] = list(images)  # convert back to list for JSON

                sizes_list = []
                seen_sizes = set()

                # Find only UK shoes and Apparel containers
                size_containers = soup.find_all(
                    "div",
                    class_=lambda x: x and (
                        all(c in x.split() for c in [
                            "attribute__list",
                            "js-attribute-list",
                            "js-gtm-attr-vendorSize",
                            "d-none",
                            "shoe-size-attributes-UK"
                        ]) or
                        all(c in x.split() for c in [
                            "attribute__list",
                            "js-attribute-list",
                            "js-gtm-attr-vendorSize"
                        ])
                    )
                )

                for size_container in size_containers:
                    # Skip EU or US containers just in case
                    if "shoe-size-attributes-EU" in size_container.get("class", []):
                        continue
                    elif "shoe-size-attributes-US" in size_container.get("class", []):
                        continue

                    for btn in size_container.find_all("button", class_="size-attribute"):
                        span = btn.find(
                            "span",
                            class_=[
                                "vendorSize-value",
                                "swatch-value",
                                "js-size-value-option"
                            ]
                        )
                        if not span:
                            continue

                        size_text = span.get_text(strip=True)

                        # Skip duplicates
                        if size_text in seen_sizes:
                            continue
                        seen_sizes.add(size_text)

                        # Determine stock status
                        if "disabled" in span.get("class", []):
                            status = "Out of Stock"
                        elif "js-trigger-limited-stock" in btn.get("class", []):
                            status = "In Stock"
                        else:
                            status = "In Stock"

                        sizes_list.append({
                            "size": size_text,
                            "status": status
                        })

                # Attach only UK sizes to product data
                product_data["Sizes"] = sizes_list

                
                gender = None
                parent_gender_tag = soup.find("div",class_= "cart-and-ipay")
                add_to_cart_btn = parent_gender_tag.find("button", class_="add-to-cart btn btn-primary js-add-to-cart-btn js-add-to-cart-placeholder")
                if add_to_cart_btn:
                    data_attr = add_to_cart_btn.get("data-branch-add-to-cart-data")
                    if data_attr:
                        try:
                            product_data_json = json.loads(data_attr.replace("&quot;", '"'))
                            gender = product_data_json.get("gender")
                        except json.JSONDecodeError:
                            gender = None

                # Attach gender to product_data
                product_data["Gender"] = gender

                parent_div = soup.find(
                    'div',
                    class_='container product product-detail product-wrapper js-product-to-wishlist js-gtm-product-id js-product-detail'
                )

                # Default value
                division = None

                if parent_div:
                    input_element = parent_div.find(
                        "input",
                        attrs={"class": ["js-moe-pdpdata", "js-moe-wishlistdata"], "type": "hidden"}
                    )
                    
                    if input_element and input_element.has_attr('value') and input_element['value'].strip():
                        try:
                            data = json.loads(input_element['value'])
                            division = data.get('division', None)
                        except json.JSONDecodeError:
                            pass  # ignore JSON errors silently

                # Always safe to assign now
                product_data["Division"] = division


                                # Default value
                occasion = None

                if parent_div:
                    input_element = parent_div.find(
                        "input",
                        attrs={"class": ["js-moe-pdpdata", "js-moe-wishlistdata"], "type": "hidden"}
                    )
                    
                    if input_element and input_element.has_attr('value') and input_element['value'].strip():
                        try:
                            data = json.loads(input_element['value'])
                            occasion = data.get('sport', None)
                        except json.JSONDecodeError:
                            pass  # ignore JSON errors silently

                # Always safe to assign now
                product_data["occasion"] = occasion

                # find the parent container
                parent = soup.find("div", class_="product-detail__details")
                desc = parent.find("div", class_="product-detail__description").get_text(strip=True)
                product_data["extra description"] = desc

                # Save JSON with images
                save_json(gender, category, name, product_data, date_subfolder)

            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                continue


async def process_gender_section(page, gender, categories, date_subfolder):
    logging.info(f"Starting UAE {gender} section with {len(categories)} categories...")
    for category, urls in categories.items():
        logging.info(f"  Processing category: {category} ({len(urls)} URLs)")
        await process_urls(page, gender, category, urls, date_subfolder)
    logging.info(f"UAE {gender} section complete.")


async def limited_process_gender_section(p, gender, categories, date_subfolder, semaphore):
    async with semaphore:  # Semaphore limits concurrent gender sections
        logging.info(f"Semaphore acquired for gender {gender}")
        browser = await p.chromium.launch(channel="chrome",headless=False)
        page = await browser.new_page()
        try:
            await process_gender_section(page, gender, categories, date_subfolder)
        except Exception as e:
            logging.error(f"Error in gender section {gender}: {e}")
        finally:
            await browser.close()
            logging.info(f"Semaphore released for gender {gender}")


async def main():
    today_str = date.today().strftime("%Y-%m-%d")
    # today_str = '2025-11-19'
    country = "UAE"
    logging.info(f"Now starting {country} products...")
    date_subfolder = Path(country) / "Data" / today_str
    date_subfolder.mkdir(parents=True, exist_ok=True)

    file_path = date_subfolder / "Item_urls" / f"unique_product_urls.json"
    if not file_path.exists():
        logging.error(f"Product link JSON file not found at: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as json_file:
        urls_dict = json.load(json_file)

    semaphore = asyncio.Semaphore(3)  # allow 4 concurrent gender sections

    async with async_playwright() as p:
        tasks = [
            limited_process_gender_section(p, gender, categories, date_subfolder, semaphore)
            for gender, categories in urls_dict.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    logging.info(f"{country} products completed.")


if __name__ == "__main__":
    asyncio.run(main())
