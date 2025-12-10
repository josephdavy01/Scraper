import os
import json
import time
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from seleniumbase import Driver

# --- Config ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
BASE_URL = "https://www.asics.com/"
LOAD_MORE_BTN = 'a[data-test="plp-load-more"]'
PRODUCT_CARD = '.productTile__root'
COOKIE_BTN = "button#onetrust-accept-btn-handler"

# 1. POPUP HANDLER
def dismiss_popups(driver):
    try:
        if driver.is_element_visible(COOKIE_BTN):
            driver.click(COOKIE_BTN)
            time.sleep(1)
            return
        
        if driver.is_element_visible('button[aria-label="Close dialog"]'):
            driver.click('button[aria-label="Close dialog"]')
            return

        if driver.is_element_visible('[role="dialog"]'):
            driver.click_at(driver.get_window_size()['width'] - 10, driver.get_window_size()['height'] - 10)
    except:
        pass

# 2. CORE SCRAPING & LOOP
def scrape_and_save(driver, url, output_file, gender, category):
    driver.open(url)
    driver.sleep(4) 
    
    full_data = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
            
    collected_urls = set(full_data.get(gender, {}).get(category, []))

    loop_active = True
    while loop_active:
        dismiss_popups(driver)
        
        # --- A. SAVE DATA ---
        soup = BeautifulSoup(driver.get_page_source(), 'html.parser')
        current_products = soup.select(PRODUCT_CARD)
        current_count = len(current_products)
        
        for link in current_products:
            href = link.get('href')
            if href:
                collected_urls.add(urljoin(BASE_URL, href))
        
        if gender not in full_data: full_data[gender] = {}
        full_data[gender][category] = list(collected_urls)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=2)
        
        logging.info(f"Saved {len(collected_urls)} URLs. Current page count: {current_count}")

        # --- B. FIND & CLICK LOAD MORE (UPDATED) ---
        button_found = False
        
        # Scroll to bottom to trigger button visibility
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5) 

        if driver.is_element_visible(LOAD_MORE_BTN):
            try:
                # 1. Get the element
                btn_element = driver.find_element(LOAD_MORE_BTN)
                
                # 2. Scroll element to CENTER of screen (Prevents Header/Footer overlap)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_element)
                time.sleep(1)

                # 3. JAVASCRIPT CLICK ignores whether another element is covering it
                driver.execute_script("arguments[0].click();", btn_element)
                
                logging.info("Clicked 'Load More' (via JS). Waiting strictly for new products...")
                
                # --- C. STRICT WAIT ---
                start_wait = time.time()
                while time.time() - start_wait < 60:
                    new_count = len(driver.find_elements(PRODUCT_CARD))
                    if new_count > current_count:
                        logging.info(f"Success: Count increased from {current_count} to {new_count}")
                        button_found = True
                        break
                    time.sleep(1)
                
                if not button_found:
                    logging.warning("Clicked button, but product count did not increase (Time out).")
                    loop_active = False 
            except Exception as e:
                logging.warning(f"JS Click failed: {e}")
                loop_active = False
        else:
            logging.info("Load More button not visible. End of list reached.")
            loop_active = False

# 3. MAIN CONTROLLER
def main():
    country = "UK"
    today_str = time.strftime('%Y-%m-%d')
    input_json = f'{country}/Data/{today_str}/Item_urls/{country}_category_urls.json'
    output_dir = f'{country}/Data/{today_str}/Item_urls'
    output_file = f'{output_dir}/{country}_product_urls.json'
    
    if not os.path.exists(input_json):
        print("Input file not found.")
        return

    os.makedirs(output_dir, exist_ok=True)

    with open(input_json, 'r', encoding='utf-8') as f:
        categories = json.load(f)

    for cat_name, url in categories.items():
        if any(x in cat_name for x in ['sports', 'gifts', 'shop_all']) or url.startswith("javascript"):
            continue

        logging.info(f"--- Processing: {cat_name} ---")

        # 🔹 Launch new browser for each category
        driver = Driver(headless=False)
        try:
            scrape_and_save(driver, url, output_file, gender=cat_name, category=cat_name)
        finally:
            driver.quit()   # 🔹 Close browser after finishing category
            logging.info(f"Closed browser for {cat_name}")

    logging.info("Scraping Finished.")

if __name__ == "__main__":
    main()