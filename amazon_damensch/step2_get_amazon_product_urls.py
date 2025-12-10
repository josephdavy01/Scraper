import os
import time
import json
import logging
from datetime import date
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.common.by import By

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def click_continue_shopping(driver):
    try:
        # The button is a <button> element, not an <input>
        continue_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Continue shopping')]")
        if continue_button:
            continue_button.click()
            logging.info("Clicked on 'Continue Shopping' button.")
            time.sleep(1)  # Wait for the page to load after clicking
    except Exception as e:
        logging.error(f"Error clicking 'Continue Shopping' button: {str(e)}")

def is_validation(soup):
    validation_tag = soup.find('form', {'action': '/errors/validateCaptcha'})
    if validation_tag:
        logging.warning("Validation page detected.")
        return True
    return False

def scroll_to_bottom_slowly(driver, pause_time=1, step=400):
    """Slowly scrolls to the bottom of the page to load all dynamic content."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        # Scroll in small increments
        for i in range(0, last_height, step):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(pause_time)
        # Final scroll to ensure we reach the bottom
        driver.execute_script(f"window.scrollTo(0, {last_height});")
        time.sleep(pause_time)
        # Check if new content has loaded (height increased)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # No more new content, exit loop
        last_height = new_height

def process_url(driver, url):
    # Get page source
    page_source = driver.get_page_source()
    soup = BeautifulSoup(page_source, 'html.parser')

    check_validation = is_validation(soup)
    if check_validation:
        click_continue_shopping(driver)

    product_links = []
    try:
        # Navigate to the URL
        logging.info(f"Navigating to: {url}")
        driver.uc_open_with_reconnect(url, reconnect_time=4)
        time.sleep(2)  # Wait for the page to load completely

        scroll_to_bottom_slowly(driver, pause_time=1)
        
        # Get page source
        page_source = driver.get_page_source()
        soup = BeautifulSoup(page_source, 'html.parser')

        ui_tag = soup.find('ul', {'class': 'ProductGrid__grid__f5oba'})
        if ui_tag:
            li_tags = ui_tag.find_all('li')
            if li_tags:
                for li_tag in li_tags:
                    product_link = 'https://www.amazon.in' + li_tag.find('a')['href'].split('?')[0]
                    product_links.append(product_link)
                logging.info(f"Found {len(product_links)} product links.")
            else:
                logging.warning("No <li> tags found in the navigation list.")
        else:
            logging.warning("No navigation list found on the page.")
        return product_links
    except Exception as e:
        logging.error(f"Error occurred while scraping: {str(e)}")
        return []

if __name__ == "__main__":
    # Create output directory based on today's date
    today_str = date.today().strftime('%Y-%m-%d')
    output_path = f'Data/{today_str}/Item_urls'
    os.makedirs(output_path, exist_ok=True)

    # Initialize driver with UC mode enabled (headless=False for debugging, set to True for production)
    driver = Driver(uc=True, headless=False)
    driver.maximize_window()
    driver.uc_open_with_reconnect('https://www.amazon.in/', reconnect_time=4)
    time.sleep(1)

    brands = ['damensch']

    try:
        for brand in brands:
            input_file = f'{output_path}/amazon_{brand}_category_urls.json'
            output_file = f'{output_path}/amazon_{brand}_product_urls.json'

            with open(input_file, 'r', encoding='utf-8') as f:
                categories = json.load(f)

            temp = {}
    
            for category, url in categories.items():
                temp[category] = process_url(driver, url)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(temp, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved product URLs to {output_file}")
    finally:
        # Close the browser and end the session
        driver.quit()

    
