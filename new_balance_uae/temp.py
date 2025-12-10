def scrape_product_details(page, product_url, category, subcategory):
    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        page.wait_for_selector('div.pdp-swatches__options', timeout=60000)
    except TimeoutError:
        print(f"Timeout loading {product_url}")
        return None

    soup = BeautifulSoup(page.content(), "html.parser")

    # Extract subcategory from pdp-collection
    pdp_collection = soup.select_one('h4.pdp-collection')
    extracted_subcategory = pdp_collection.text.strip() if pdp_collection else subcategory or "Uncategorized"

    product_data = {
        "Product Id": "",
        "Product Name": "",
        "Date of Scraping": datetime.today().strftime("%Y-%m-%d"),
        "Product Url": product_url,
        "Category": category,
        "Subcategory": extracted_subcategory,
        "Description": "",
        "Product Reference Code": "",
        "SKU": "",
        "Color Name": "",
        "Color ID": "",
        "Sizes": {"EU": [], "UK": [], "US": []},
        "Price": "",
        "Launch Price": "",
        "Availability": False,
        "Demand": "",
        "Images": [],
        "Variants": []
    }

    # Extract JSON-LD
    json_ld_script = soup.select_one('script[type="application/ld+json"][data-name="product"]')
    if json_ld_script:
        try:
            json_ld_data = json.loads(json_ld_script.string)

            # Fix for list/dict offers
            offers_data = json_ld_data.get("offers", [])
            if isinstance(offers_data, list) and offers_data:
                first_offer = offers_data[0]
            elif isinstance(offers_data, dict):
                first_offer = offers_data
            else:
                first_offer = {}

            product_data["Product Name"] = json_ld_data.get("name", "")
            product_data["SKU"] = json_ld_data.get("sku", "")
            product_data["Description"] = json_ld_data.get("description", "")
            product_data["Images"] = json_ld_data.get("image", [])
            price_value = first_offer.get("price", "")
            currency = first_offer.get("priceCurrency", "AED")
            product_data["Price"] = f"{currency} {price_value}" if price_value else ""
            product_data["Availability"] = first_offer.get("availability", "").lower() == "instock"
        except json.JSONDecodeError as e:
            print(f"JSON-LD parsing error for {product_url}: {e}")

    # Fallbacks
    if not product_data["Product Name"]:
        name_elem = soup.select_one('h1.pdp-product__title')
        product_data["Product Name"] = name_elem.text.strip() if name_elem else ""

    if not product_data["Description"]:
        desc_elem = soup.select_one('div.pdp-product__description--content')
        product_data["Description"] = desc_elem.text.strip() if desc_elem else ""

    ref_elem = soup.select_one('ul.pdp-product-description__attribute--castor_product_id span')
    product_data["Product Reference Code"] = ref_elem.text.strip() if ref_elem else ""

    if product_data["Product Reference Code"]:
        product_data["Product Id"] = product_data["Product Reference Code"]
    elif product_data["SKU"]:
        sku = product_data["SKU"]
        product_data["Product Id"] = sku.split('-')[0] if '-' in sku else sku

    color_label_elem = soup.select_one('div.pdp-swatches__field__label')
    if color_label_elem and 'Color:' in color_label_elem.text:
        product_data["Color Name"] = color_label_elem.text.split('Color: ')[1].strip()
    else:
        try:
            color_select = page.locator('select[aria-label="Color"]').first
            color_option = color_select.locator('option[selected]').first
            product_data["Color Name"] = color_option.text_content().strip() if color_option else ""
        except:
            product_data["Color Name"] = ""

    default_color_input = soup.select_one('div.pdp-swatches__options input[type="radio"][name="color"].dropin-text-swatch--selected')
    product_data["Color ID"] = default_color_input.get('id', '') if default_color_input else ""

    for size_type in ['us_size', 'eu_size', 'uk_size']:
        try:
            toggle = page.locator(f'span.size-toggle[data-attribute="{size_type}"]')
            if toggle.is_visible(timeout=5000):
                toggle.click(force=True)
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Failed to click {size_type} toggle for {product_url}: {e}")

    sizes = {"EU": [], "UK": [], "US": []}
    html_available = False
    for size_type, selector in [
        ("EU", 'div.size-eu.size_shoe_eu.eu_size.sizes-list'),
        ("UK", 'div.size-uk.size_shoe_uk.uk_size.sizes-list'),
        ("US", 'div.size-us.size_shoe_us.us_size.sizes-list')
    ]:
        size_elem = soup.select_one(selector)
        if size_elem:
            size_items = size_elem.select('label.dropin-text-swatch__label')
            for item in size_items:
                size_name = item.text.strip()
                size_ref = item.get('id', '')
                is_available = 'dropin-text-swatch__label--out-of-stock' not in item.get('class', [])
                if is_available:
                    html_available = True
                sizes[size_type].append({
                    "name": size_name,
                    "reference_code": size_ref,
                    "available": is_available
                })

    product_data["Sizes"] = sizes
    product_data["Availability"] = product_data["Availability"] or html_available

    if not product_data["Price"]:
        price_elem = soup.select_one('div.pdp-price__current span')
        product_data["Price"] = price_elem.text.strip() if price_elem else ""

    launch_price_elem = soup.select_one('span.dropin-price--strikethrough')
    if not launch_price_elem:
        launch_price_elem = soup.select_one('div.pdp-price__old span')
    product_data["Launch Price"] = launch_price_elem.text.strip() if launch_price_elem else product_data["Price"]

    product_data["Demand"] = "High" if product_data["Price"] != product_data["Launch Price"] else ""

    if not product_data["Images"]:
        image_elems = soup.select('div.product-gallery img, div.item-images img')
        for img in image_elems:
            src = img.get('src')
            if src:
                if src.startswith('/'):
                    src = "https://www.newbalance.co.ae" + src
                elif src.startswith('https://media.alshaya.com'):
                    src = src.split('?')[0]
                if src not in product_data["Images"]:
                    product_data["Images"].append(src)

    variant_elems = soup.select('div.pdp-swatches__options input[type="radio"][name="color"]')
    variants = []
    default_color = product_data["Color Name"].strip().lower()

    for variant_elem in variant_elems:
        variant_id = variant_elem.get('id', '')
        color_name = variant_elem.get('value', '')
        if not color_name:
            aria_label = variant_elem.get('aria-label', '')
            if aria_label.startswith('Color: '):
                color_name = aria_label.replace('Color: ', '').replace(' swatch', '').replace(' selected', '').strip()

        if not color_name or not variant_id or color_name.strip().lower() == default_color:
            continue

        try:
            page.wait_for_selector(f'input[type="radio"][id="{variant_id}"]', timeout=5000)
            page.locator(f'input[type="radio"][id="{variant_id}"]').click(force=True, timeout=10000)
        except:
            try:
                page.wait_for_selector(f'label[for="{variant_id}"]', timeout=5000)
                page.locator(f'label[for="{variant_id}"]').click(force=True, timeout=10000)
            except:
                continue

        page.wait_for_timeout(3000)
        soup = BeautifulSoup(page.content(), "html.parser")

        variant_data = {
            "Color Name": color_name,
            "Color ID": variant_id,
            "SKU": product_data["SKU"],
            "Sizes": {"EU": [], "UK": [], "US": []},
            "Price": product_data["Price"],
            "Availability": False,
            "Images": []
        }

        json_ld_script = soup.select_one('script[type="application/ld+json"][data-name="product"]')
        if json_ld_script:
            try:
                json_ld_data = json.loads(json_ld_script.string)
                variant_data["SKU"] = json_ld_data.get("sku", product_data["SKU"])

                offers_data = json_ld_data.get("offers", [])
                if isinstance(offers_data, list) and offers_data:
                    first_offer = offers_data[0]
                elif isinstance(offers_data, dict):
                    first_offer = offers_data
                else:
                    first_offer = {}

                price_value = first_offer.get("price", "")
                currency = first_offer.get("priceCurrency", "AED")
                variant_data["Price"] = f"{currency} {price_value}" if price_value else product_data["Price"]
                variant_data["Availability"] = first_offer.get("availability", "").lower() == "instock"
                variant_data["Images"] = json_ld_data.get("image", product_data["Images"])
            except:
                pass

        for size_type in ['us_size', 'eu_size', 'uk_size']:
            try:
                toggle = page.locator(f'span.size-toggle[data-attribute="{size_type}"]')
                if toggle.is_visible(timeout=5000):
                    toggle.click(force=True)
                    page.wait_for_timeout(1000)
            except:
                pass

        variant_available = False
        for size_type, selector in [
            ("EU", 'div.size-eu.size_shoe_eu.eu_size.sizes-list'),
            ("UK", 'div.size-uk.size_shoe_uk.uk_size.sizes-list'),
            ("US", 'div.size-us.size_shoe_us.us_size.sizes-list')
        ]:
            size_elem = soup.select_one(selector)
            if size_elem:
                size_items = size_elem.select('label.dropin-text-swatch__label')
                for item in size_items:
                    size_name = item.text.strip()
                    size_ref = item.get('id', '')
                    is_available = 'dropin-text-swatch__label--out-of-stock' not in item.get('class', [])
                    if is_available:
                        variant_available = True
                    variant_data["Sizes"][size_type].append({
                        "name": size_name,
                        "reference_code": size_ref,
                        "available": is_available
                    })

        variant_data["Availability"] = variant_data["Availability"] or variant_available

        if not variant_data["Images"]:
            image_elems = soup.select('div.product-gallery img, div.item-images img')
            for img in image_elems:
                src = img.get('src')
                if src:
                    if src.startswith('/'):
                        src = "https://www.newbalance.co.ae" + src
                    elif src.startswith('https://media.alshaya.com'):
                        src = src.split('?')[0]
                    if src not in variant_data["Images"]:
                        variant_data["Images"].append(src)

        variants.append(variant_data)

    product_data["Variants"] = variants if variants else []
    return product_data
